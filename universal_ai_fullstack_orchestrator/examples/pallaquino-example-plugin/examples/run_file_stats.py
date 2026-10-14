"""Run the example plugin through the SDK harness against this example's README."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))
from pallaquino_cli.sdk.testing import PluginHarness  # noqa: E402

with PluginHarness(HERE / "src" / "pallaquino_example_plugin", workspace=HERE) as harness:
    print(json.dumps(harness.call("file_stats", {"path": "README.md"}), indent=2))
