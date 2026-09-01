#!/usr/bin/env python3
import json
from _bootstrap import ROOT
from pallaquino_cli.core import read_json, validate_task_graph

print(json.dumps({"validation": validate_task_graph(ROOT), "graph": read_json(ROOT / "planning/task_graph.json")}, indent=2))

