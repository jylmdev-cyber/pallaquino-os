# pallaquino-example-plugin

Reference plugin for the PALLAQUINO Extension Development Kit (`pallaquino_cli.sdk`). It exposes two read-only
tools, `file_stats` and `word_frequency`, and runs in its own process; PALLAQUINO talks to it over MCP stdio.

```text
pallaquino-example-plugin/
├── pyproject.toml                      # entry point pallaquino.plugins -> pallaquino_example_plugin:plugin
├── src/pallaquino_example_plugin/
│   ├── plugin.toml                     # manifest: tools, schemas, capabilities, operation classes
│   └── __init__.py                     # implementation with @plugin.tool(...)
├── tests/test_text_stats.py            # runs the plugin isolated through PluginHarness
└── examples/run_file_stats.py
```

```bash
python -m unittest discover -s tests -v
python examples/run_file_stats.py
```

See `docs/tutorials/CREATE_FIRST_PLUGIN.md` for installing, trusting and enabling it in a project.
