"""0.5.0 foundations: bounded JSON Schema validator, SemVer ranges, tool contract and plugin manifest validation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pallaquino_cli.extensions.manifest import content_hash, parse_manifest, validate_manifest
from pallaquino_cli.extensions.semver import Version, satisfies
from pallaquino_cli.mcp import protocol as p
from pallaquino_cli.tools.contracts import derive_approval, new_tool, validate_tool
from pallaquino_cli.tools.schema import MAX_SUBSCHEMAS, SchemaError, check_schema, validate

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "pallaquino-example-plugin" / "src" / "pallaquino_example_plugin"


def manifest(**overrides) -> dict:
    data = {"manifest_version": 1,
            "plugin": {"id": "acme.tools", "name": "Acme", "description": "d", "author": "a", "version": "1.0.0", "type": "TOOL_PLUGIN"},
            "compatibility": {"pallaquino": ">=0.5.0,<0.6.0"}, "runtime": {"entrypoint": "acme_tools:plugin"}, "permissions": {"requested": ["FILE_READ"]},
            "tools": [{"name": "t", "description": "d", "capabilities": ["FILE_READ"], "operation": "READ_ONLY", "input_schema": {"type": "object"}}]}
    for path, value in overrides.items():
        node = data; keys = path.split(".")
        for key in keys[:-1]: node = node.setdefault(key, {})
        if value is None: node.pop(keys[-1], None)
        else: node[keys[-1]] = value
    return data


class SchemaValidatorTest(unittest.TestCase):
    def test_types_required_and_additional_properties(self):
        schema = {"type": "object", "required": ["a"], "additionalProperties": False, "properties": {"a": {"type": "integer", "minimum": 1}, "b": {"type": "string", "maxLength": 3}}}
        self.assertEqual(validate({"a": 2, "b": "abc"}, schema), [])
        errors = validate({"b": "abcd", "c": 1}, schema)
        self.assertTrue(any("missing required property 'a'" in e for e in errors)); self.assertTrue(any("longer than 3" in e for e in errors))
        self.assertTrue(any("additional property" in e for e in errors))
        self.assertTrue(validate({"a": True}, schema), "booleans are not integers")

    def test_composition_and_local_refs(self):
        schema = {"$defs": {"pos": {"type": "integer", "exclusiveMinimum": 0}}, "oneOf": [{"$ref": "#/$defs/pos"}, {"type": "string", "pattern": "^x"}]}
        self.assertEqual(validate(3, schema), []); self.assertEqual(validate("xy", schema), [])
        self.assertTrue(validate(0, schema)); self.assertTrue(validate("y", schema))
        self.assertEqual(validate([1, 2], {"type": "array", "items": {"type": "integer"}, "uniqueItems": True}), [])
        self.assertTrue(validate([1, 1], {"type": "array", "uniqueItems": True}))

    def test_remote_refs_and_unknown_keywords_are_rejected(self):
        self.assertTrue(any("never dereferenced" in e for e in check_schema({"$ref": "https://evil.example/schema.json"})))
        self.assertTrue(any("unsupported keyword" in e for e in check_schema({"type": "object", "dependentSchemas": {}})))
        self.assertTrue(check_schema({"$schema": "https://json-schema.org/draft/2019-09/schema"}))
        with self.assertRaises(SchemaError): validate({}, {"$ref": "http://169.254.169.254/latest"})

    def test_resource_bounds_stop_hostile_schemas(self):
        wide = {"anyOf": [{"type": "string"}] * (MAX_SUBSCHEMAS + 5)}
        self.assertTrue(any("more than" in e for e in check_schema(wide)))
        deep: dict = {"type": "object"}
        for _ in range(40): deep = {"properties": {"x": deep}}
        self.assertTrue(any("depth" in e for e in check_schema(deep)))
        with self.assertRaises(SchemaError): validate(1, {"$defs": {"a": {"$ref": "#/$defs/a"}}, "$ref": "#/$defs/a"})


class SemverTest(unittest.TestCase):
    def test_precedence_and_ranges(self):
        self.assertLess(Version("1.0.0-alpha"), Version("1.0.0")); self.assertLess(Version("1.0.0-alpha.1"), Version("1.0.0-alpha.beta"))
        self.assertTrue(satisfies("0.5.3", ">=0.5.0,<0.6.0")); self.assertFalse(satisfies("0.6.0", ">=0.5.0,<0.6.0"))
        self.assertTrue(satisfies("1.4.0", "^1.2")); self.assertFalse(satisfies("2.0.0", "^1.2")); self.assertFalse(satisfies("0.3.0", "^0.2.1"))
        self.assertTrue(satisfies("1.2.9", "~1.2.3")); self.assertFalse(satisfies("1.3.0", "~1.2.3"))
        with self.assertRaises(ValueError): Version("01.2.3")
        with self.assertRaises(ValueError): satisfies("1.0.0", "")


class ToolContractTest(unittest.TestCase):
    def test_policy_is_derived_and_cannot_be_weakened(self):
        tool = new_tool("mcp.x.deploy", description="d", source={"kind": "mcp", "id": "x", "trust": "untrusted"}, input_schema={"type": "object"},
                        capabilities=["DEPLOYMENT"], operation="EXTERNAL_SIDE_EFFECT")
        self.assertEqual((tool["approval"], tool["risk"]), ("per_call", "CRITICAL")); self.assertEqual(validate_tool(tool), [])
        weakened = {**tool, "approval": "contract", "risk": "LOW"}
        errors = validate_tool(weakened)
        self.assertTrue(any("weaker" in e for e in errors)); self.assertTrue(any("below the derived risk" in e for e in errors))
        self.assertTrue(validate_tool({**tool, "source": {"kind": "mcp", "id": "x", "trust": "builtin"}}))
        self.assertEqual(derive_approval("READ_ONLY", "builtin", ["FILE_READ"]), "contract")
        self.assertEqual(derive_approval("READ_ONLY", "untrusted", ["FILE_READ"]), "grant")
        self.assertEqual(derive_approval("WRITE_OPERATION", "trusted", ["SECRETS_ACCESS"]), "per_call")

    def test_writes_are_not_retried(self):
        tool = new_tool("core.x.write", description="d", source={"kind": "builtin", "id": "x", "trust": "builtin"}, input_schema={"type": "object"},
                        capabilities=["FILE_WRITE"], operation="WRITE_OPERATION")
        self.assertEqual(tool["retry"]["max_attempts"], 1)
        self.assertTrue(validate_tool({**tool, "retry": {"max_attempts": 3, "retry_on": ["timeout"]}}))


class ManifestTest(unittest.TestCase):
    def test_reference_plugin_manifest_is_valid(self):
        report = validate_manifest(parse_manifest((EXAMPLE / "plugin.toml").read_bytes()), base_dir=EXAMPLE, framework_version="0.5.0")
        self.assertTrue(report["ok"], report["errors"]); self.assertTrue(report["compatible"])
        self.assertEqual([t["name"] for t in report["normalized"]["tools"]], ["file_stats", "word_frequency"])

    def test_invalid_metadata_is_reported(self):
        cases = {"plugin.id": "Bad ID", "plugin.version": "1.0", "plugin.type": "ROOTKIT", "runtime.entrypoint": "no-colon", "manifest_version": 2}
        for path, value in cases.items():
            with self.subTest(path=path):
                self.assertFalse(validate_manifest(manifest(**{path: value}))["ok"])
        self.assertFalse(validate_manifest(manifest(**{"plugin.id": "core.evil"}))["ok"], "reserved prefixes")
        self.assertFalse(validate_manifest(manifest(**{"runtime.isolation": "in_process"}))["ok"], "only CORE_PLUGIN may run in process")
        undeclared = manifest(); undeclared["tools"][0]["capabilities"] = ["SECRETS_ACCESS"]
        self.assertTrue(any("does not declare" in e for e in validate_manifest(undeclared)["errors"]))
        duplicate = manifest(); duplicate["tools"].append(dict(duplicate["tools"][0]))
        self.assertTrue(any("duplicate tool" in e for e in validate_manifest(duplicate)["errors"]))
        bad_schema = manifest(); bad_schema["tools"][0]["input_schema"] = {"$ref": "https://x/y"}
        self.assertFalse(validate_manifest(bad_schema)["ok"])
        missing = manifest(**{"plugin.author": None})
        self.assertTrue(any("plugin.author" in e for e in validate_manifest(missing)["errors"]))

    def test_incompatible_framework_versions_are_flagged(self):
        report = validate_manifest(manifest(**{"compatibility.pallaquino": ">=0.7.0"}), framework_version="0.5.0")
        self.assertTrue(report["ok"]); self.assertFalse(report["compatible"])

    def test_content_hash_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            first = content_hash(root); (root / "__pycache__").mkdir(); (root / "__pycache__" / "a.pyc").write_bytes(b"\0")
            self.assertEqual(content_hash(root), first, "caches do not change the hash")
            (root / "a.py").write_text("x = 2\n", encoding="utf-8"); self.assertNotEqual(content_hash(root), first)


class ProtocolHelpersTest(unittest.TestCase):
    def test_header_value_encoding(self):
        self.assertEqual(p.encode_header_value("us-west1"), "us-west1")
        self.assertEqual(p.encode_header_value("Hello, 世界"), "=?base64?SGVsbG8sIOS4lueVjA==?=")
        self.assertEqual(p.encode_header_value(" padded "), "=?base64?IHBhZGRlZCA=?=")
        self.assertEqual(p.encode_header_value("=?base64?literal?="), "=?base64?PT9iYXNlNjQ/bGl0ZXJhbD89?=")
        self.assertEqual(p.encode_header_value(True), "true")
        self.assertEqual(p.decode_header_value("=?base64?SGVsbG8sIOS4lueVjA==?="), "Hello, 世界")

    def test_x_mcp_header_annotations(self):
        ok = {"type": "object", "properties": {"region": {"type": "string", "x-mcp-header": "Region"}, "q": {"type": "string"}}}
        self.assertEqual(p.header_values(p.header_parameters(ok), {"region": "us-west1", "q": "x"}), {"Mcp-Param-Region": "us-west1"})
        for bad in ({"type": "object", "properties": {"a": {"type": "number", "x-mcp-header": "A"}}},
                    {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "string", "x-mcp-header": "A"}}}},
                    {"type": "object", "properties": {"a": {"type": "string", "x-mcp-header": "A"}, "b": {"type": "string", "x-mcp-header": "a"}}},
                    {"type": "object", "properties": {"a": {"type": "string", "x-mcp-header": "bad name"}}}):
            with self.assertRaises(ValueError): p.header_parameters(bad)

    def test_result_type_rules(self):
        self.assertEqual(p.result_type({}, p.CORE_RESULT_TYPES), "complete", "absent resultType means complete")
        with self.assertRaises(p.ProtocolError): p.result_type({"resultType": "task"}, p.CORE_RESULT_TYPES)
        self.assertTrue(p.is_modern_error({"error": {"code": -32022, "data": {"supported": ["2026-07-28"]}}}))
        self.assertFalse(p.is_modern_error({"error": {"code": -32601}}))


if __name__ == "__main__":
    unittest.main()
