"""Bounded JSON Schema validator (2020-12 subset, draft-07 compatible) for tool inputs and outputs, stdlib only.

MCP 2026-07-28 requires JSON Schema 2020-12 by default, forbids dereferencing network `$ref`s and asks for resource
bounds on composition keywords. This validator therefore resolves only local references (`#`, `#/$defs/...`,
`#/definitions/...`), rejects any other `$ref`, and caps schema depth, subschema count and validation steps so a
hostile server cannot turn its schema into a denial of service. Annotation keywords (`format`, `title`, `x-*`, ...)
are ignored, as 2020-12 allows; assertion keywords outside the supported set are reported by `check_schema`, never
silently treated as permissive.
"""
from __future__ import annotations

import math
import re
from typing import Any

DIALECTS = {None, "https://json-schema.org/draft/2020-12/schema", "http://json-schema.org/draft-07/schema#", "http://json-schema.org/draft-07/schema"}
MAX_DEPTH = 32
MAX_SUBSCHEMAS = 1000
MAX_STEPS = 50_000
MAX_ERRORS = 20
ANNOTATIONS = {"$schema", "$id", "$comment", "$anchor", "$defs", "definitions", "title", "description", "default", "examples", "format",
               "readOnly", "writeOnly", "deprecated", "contentMediaType", "contentEncoding", "contentSchema", "$vocabulary", "$dynamicAnchor"}
ASSERTIONS = {"type", "enum", "const", "properties", "required", "additionalProperties", "patternProperties", "propertyNames", "minProperties",
              "maxProperties", "dependentRequired", "items", "prefixItems", "minItems", "maxItems", "uniqueItems", "contains", "minLength",
              "maxLength", "pattern", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "anyOf", "oneOf", "allOf",
              "not", "if", "then", "else", "$ref"}
SUBSCHEMA_MAPS = ("properties", "patternProperties", "$defs", "definitions")
SUBSCHEMA_SINGLE = ("additionalProperties", "propertyNames", "items", "contains", "not", "if", "then", "else")
SUBSCHEMA_LISTS = ("prefixItems", "anyOf", "oneOf", "allOf")
TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


class SchemaError(ValueError):
    """The schema itself is invalid, unsupported or exceeds the resource bounds."""


def _children(schema: dict[str, Any]):
    for key in SUBSCHEMA_MAPS:
        value = schema.get(key)
        if isinstance(value, dict): yield from value.values()
    for key in SUBSCHEMA_SINGLE:
        value = schema.get(key)
        if isinstance(value, (dict, bool)): yield value
    for key in SUBSCHEMA_LISTS:
        value = schema.get(key)
        if isinstance(value, list): yield from value


def check_schema(schema: Any) -> list[str]:
    """Return problems with the schema itself: dialect, remote refs, bounds, malformed keywords, unknown assertions."""
    if schema is True or schema is False: return []
    if not isinstance(schema, dict): return ["schema must be an object or a boolean"]
    errors: list[str] = []
    if schema.get("$schema") not in DIALECTS: errors.append(f"unsupported JSON Schema dialect {schema.get('$schema')!r}")
    count = 0
    stack: list[tuple[Any, int, str]] = [(schema, 0, "#")]
    while stack:
        node, depth, where = stack.pop(); count += 1
        if count > MAX_SUBSCHEMAS: return errors + [f"schema has more than {MAX_SUBSCHEMAS} subschemas"]
        if depth > MAX_DEPTH: return errors + [f"schema nesting exceeds depth {MAX_DEPTH} at {where}"]
        if isinstance(node, bool): continue
        if not isinstance(node, dict): errors.append(f"{where}: subschema must be an object or a boolean"); continue
        ref = node.get("$ref")
        if ref is not None and (not isinstance(ref, str) or not (ref == "#" or ref.startswith("#/"))):
            errors.append(f"{where}: $ref {ref!r} is not a local reference; network and external references are never dereferenced")
        declared = node.get("type")
        for t in (declared if isinstance(declared, list) else [declared] if declared is not None else []):
            if t not in TYPES: errors.append(f"{where}: unknown type {t!r}")
        if "pattern" in node:
            try: re.compile(node["pattern"])
            except (re.error, TypeError): errors.append(f"{where}: invalid pattern {node['pattern']!r}")
        if "required" in node and not (isinstance(node["required"], list) and all(isinstance(r, str) for r in node["required"])):
            errors.append(f"{where}: required must be a list of strings")
        for key in node:
            if key not in ASSERTIONS and key not in ANNOTATIONS and not key.startswith("x-"): errors.append(f"{where}: unsupported keyword {key!r}")
        for child in _children(node): stack.append((child, depth + 1, f"{where}/*"))
    return errors


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer": return isinstance(value, int) and not isinstance(value, bool) or isinstance(value, float) and value.is_integer()
    if expected == "number": return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return {"object": dict, "array": list, "string": str, "boolean": bool}.get(expected, type(None)) is type(value) if expected != "null" else value is None


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool): return type(a) is type(b) and a == b
    return a == b


class _Validator:
    def __init__(self, root: Any):
        self.root = root; self.steps = 0; self.errors: list[str] = []

    def resolve(self, ref: str) -> Any:
        if ref == "#": return self.root
        node: Any = self.root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or part not in node: raise SchemaError(f"unresolvable local $ref {ref!r}")
            node = node[part]
        return node

    def fail(self, path: str, message: str) -> bool:
        if len(self.errors) < MAX_ERRORS: self.errors.append(f"{path or '$'}: {message}")
        return False

    def valid(self, value: Any, schema: Any, path: str, depth: int = 0) -> bool:
        self.steps += 1
        if self.steps > MAX_STEPS: raise SchemaError(f"validation exceeded {MAX_STEPS} steps")
        if depth > MAX_DEPTH * 4: raise SchemaError("validation recursion is too deep (recursive $ref?)")
        if schema is True: return True
        if schema is False: return self.fail(path, "no value is allowed here")
        ok = True
        if "$ref" in schema: ok &= self.valid(value, self.resolve(schema["$ref"]), path, depth + 1)
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_type_ok(value, t) for t in types): return self.fail(path, f"expected type {' or '.join(types)}, got {type(value).__name__}")
        if "enum" in schema and not any(_equal(value, e) for e in schema["enum"]): ok = self.fail(path, f"value is not one of {schema['enum'][:10]}")
        if "const" in schema and not _equal(value, schema["const"]): ok = self.fail(path, f"value must equal {schema['const']!r}")
        if isinstance(value, dict): ok &= self.object(value, schema, path, depth)
        elif isinstance(value, list): ok &= self.array(value, schema, path, depth)
        elif isinstance(value, str): ok &= self.string(value, schema, path)
        elif isinstance(value, (int, float)) and not isinstance(value, bool): ok &= self.number(value, schema, path)
        for sub in schema.get("allOf", []): ok &= self.valid(value, sub, path, depth + 1)
        if "anyOf" in schema and not any(self.quiet(value, s, path, depth) for s in schema["anyOf"]): ok = self.fail(path, "value matches none of anyOf")
        if "oneOf" in schema:
            matches = sum(self.quiet(value, s, path, depth) for s in schema["oneOf"])
            if matches != 1: ok = self.fail(path, f"value matches {matches} oneOf subschemas, expected exactly 1")
        if "not" in schema and self.quiet(value, schema["not"], path, depth): ok = self.fail(path, "value matches a forbidden (not) schema")
        if "if" in schema:
            branch = schema.get("then") if self.quiet(value, schema["if"], path, depth) else schema.get("else")
            if branch is not None: ok &= self.valid(value, branch, path, depth + 1)
        return bool(ok)

    def quiet(self, value: Any, schema: Any, path: str, depth: int) -> bool:
        saved = list(self.errors)
        try: return self.valid(value, schema, path, depth + 1)
        finally: self.errors = saved

    def object(self, value: dict[str, Any], schema: dict[str, Any], path: str, depth: int) -> bool:
        ok = True; props = schema.get("properties", {}); patterns = schema.get("patternProperties", {})
        for name in schema.get("required", []):
            if name not in value: ok = self.fail(path, f"missing required property {name!r}")
        for name, required in schema.get("dependentRequired", {}).items():
            if name in value: ok &= all(r in value or self.fail(path, f"{name!r} requires {r!r}") for r in required)
        if "minProperties" in schema and len(value) < schema["minProperties"]: ok = self.fail(path, f"needs at least {schema['minProperties']} properties")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]: ok = self.fail(path, f"allows at most {schema['maxProperties']} properties")
        for key, item in value.items():
            child = f"{path}.{key}" if path else key; matched = False
            if "propertyNames" in schema: ok &= self.valid(key, schema["propertyNames"], child, depth + 1)
            if key in props: matched = True; ok &= self.valid(item, props[key], child, depth + 1)
            for pattern, sub in patterns.items():
                if re.search(pattern, key): matched = True; ok &= self.valid(item, sub, child, depth + 1)
            if not matched and "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                ok &= self.fail(child, "additional property is not allowed") if extra is False else self.valid(item, extra, child, depth + 1)
        return bool(ok)

    def array(self, value: list[Any], schema: dict[str, Any], path: str, depth: int) -> bool:
        ok = True; prefix = schema.get("prefixItems", [])
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            if index < len(prefix): ok &= self.valid(item, prefix[index], child, depth + 1)
            elif "items" in schema and isinstance(schema["items"], (dict, bool)): ok &= self.valid(item, schema["items"], child, depth + 1)
        if "minItems" in schema and len(value) < schema["minItems"]: ok = self.fail(path, f"needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]: ok = self.fail(path, f"allows at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for item in value:
                if any(_equal(item, s) for s in seen): ok = self.fail(path, "items must be unique"); break
                seen.append(item)
        if "contains" in schema and not any(self.quiet(item, schema["contains"], path, depth) for item in value): ok = self.fail(path, "no item matches contains")
        return bool(ok)

    def string(self, value: str, schema: dict[str, Any], path: str) -> bool:
        ok = True
        if "minLength" in schema and len(value) < schema["minLength"]: ok = self.fail(path, f"shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]: ok = self.fail(path, f"longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value): ok = self.fail(path, f"does not match pattern {schema['pattern']!r}")
        return ok

    def number(self, value: float, schema: dict[str, Any], path: str) -> bool:
        ok = True
        if "minimum" in schema and value < schema["minimum"]: ok = self.fail(path, f"below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]: ok = self.fail(path, f"above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and isinstance(schema["exclusiveMinimum"], (int, float)) and value <= schema["exclusiveMinimum"]: ok = self.fail(path, f"must be > {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and isinstance(schema["exclusiveMaximum"], (int, float)) and value >= schema["exclusiveMaximum"]: ok = self.fail(path, f"must be < {schema['exclusiveMaximum']}")
        if schema.get("multipleOf") and not math.isclose(value / schema["multipleOf"], round(value / schema["multipleOf"]), abs_tol=1e-9): ok = self.fail(path, f"not a multiple of {schema['multipleOf']}")
        return ok


def validate(value: Any, schema: Any) -> list[str]:
    """Return validation errors (empty when valid). Raises SchemaError when the schema is unusable."""
    problems = check_schema(schema)
    if problems: raise SchemaError("; ".join(problems[:5]))
    checker = _Validator(schema)
    checker.valid(value, schema, "")
    return checker.errors
