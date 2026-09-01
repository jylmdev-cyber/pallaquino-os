#!/usr/bin/env python3
import argparse, fnmatch, json
from _bootstrap import ROOT
from pallaquino_cli.core import read_json

p = argparse.ArgumentParser(); p.add_argument("files", nargs="+"); a = p.parse_args(); rules = read_json(ROOT / "quality/regression_scope.json")["rules"]
tests = sorted({test for file in a.files for rule in rules if fnmatch.fnmatch(file.replace("\\", "/"), rule["pattern"]) for test in rule["tests"]})
print(json.dumps({"files": a.files, "tests": tests}, indent=2))

