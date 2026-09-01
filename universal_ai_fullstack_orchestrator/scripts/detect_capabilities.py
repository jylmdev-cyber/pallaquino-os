#!/usr/bin/env python3
import json
from _bootstrap import ROOT
from pallaquino_cli.core import detect_capabilities

print(json.dumps(detect_capabilities(ROOT), indent=2))

