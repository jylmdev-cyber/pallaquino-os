#!/usr/bin/env python3
import argparse, json
from _bootstrap import ROOT
from pallaquino_cli.core import route_request

p = argparse.ArgumentParser(); p.add_argument("request"); a = p.parse_args()
print(json.dumps(route_request(ROOT, a.request), indent=2))

