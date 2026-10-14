"""Plugin tests with the SDK harness: the plugin runs isolated, exactly as PALLAQUINO runs it."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))  # framework root (only needed when PALLAQUINO is not installed)

from pallaquino_cli.sdk.testing import PluginHarness  # noqa: E402


class TextStatsTest(unittest.TestCase):
    def test_tools_run_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "notes.txt").write_text("one two three\nfour five\n", encoding="utf-8")
            with PluginHarness(HERE / "src" / "pallaquino_example_plugin", workspace=Path(tmp)) as harness:
                self.assertEqual(sorted(harness.tools()), ["file_stats", "word_frequency"])
                stats = harness.call("file_stats", {"path": "notes.txt"})
                self.assertEqual((stats["lines"], stats["words"]), (2, 5))
                self.assertIn(["alpha", 2], harness.call("word_frequency", {"text": "alpha beta alpha"})["top"])

    def test_paths_outside_the_workspace_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp, PluginHarness(HERE / "src" / "pallaquino_example_plugin", workspace=Path(tmp)) as harness:
            result = harness.call_raw("file_stats", {"path": "../outside.txt"})
            self.assertTrue(result["is_error"]); self.assertIn("escapes the workspace", result["text"])


if __name__ == "__main__":
    unittest.main()
