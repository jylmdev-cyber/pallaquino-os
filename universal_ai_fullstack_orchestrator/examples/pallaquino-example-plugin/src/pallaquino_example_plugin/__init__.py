"""Reference PALLAQUINO plugin: read-only text statistics, built with `pallaquino_cli.sdk`."""
from __future__ import annotations

import re
from collections import Counter

from pallaquino_cli.sdk import Plugin, ToolCall


class TextStats(Plugin):
    def initialize(self, context: dict) -> None:
        super().initialize(context)
        self.max_bytes = int(self.config.get("max_bytes", 262_144))


plugin = TextStats()


@plugin.tool("file_stats")
def file_stats(args: dict, call: ToolCall) -> dict:
    path = call.resolve(args["path"])  # confined to the workspace the host granted
    data = path.read_bytes()[: plugin.max_bytes].decode("utf-8", errors="replace")
    return {"path": args["path"], "lines": len(data.splitlines()), "words": len(data.split()), "characters": len(data)}


@plugin.tool("word_frequency")
def word_frequency(args: dict, call: ToolCall) -> dict:
    words = re.findall(r"[^\W\d_]{3,}", args["text"].casefold())
    return {"top": Counter(words).most_common(args.get("top", 10)), "distinct": len(set(words))}
