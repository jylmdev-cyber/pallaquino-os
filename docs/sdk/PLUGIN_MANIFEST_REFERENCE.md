# Referencia del manifiesto `plugin.toml` (v1)

Validador: `pallaquino_cli/extensions/manifest.py::validate_manifest`. Tamaño máximo: 256 KiB.

```toml
manifest_version = 1                         # obligatorio, = 1

[plugin]
id = "acme.text_tools"                       # 2-4 segmentos [a-z][a-z0-9_]; prefijos reservados: core, mcp, plugin, pallaquino
name = "Text tools"                          # obligatorio
description = "..."                          # obligatorio, ≤ 2000
author = "Ana"                               # obligatorio
version = "1.2.0"                            # SemVer completo MAJOR.MINOR.PATCH
type = "TOOL_PLUGIN"                         # uno de los 11 tipos
license = "MIT"                              # opcional

[compatibility]
pallaquino = ">=0.5.0,<0.6.0"                # obligatorio; operadores >= <= > < == != ^ ~, separados por coma
python = ">=3.11"                            # informativo

[runtime]
entrypoint = "acme_text_tools:plugin"        # obligatorio si el tipo aporta herramientas: módulo:atributo (instancia de sdk.Plugin)
isolation = "process"                        # "in_process" solo para CORE_PLUGIN
timeout_seconds = 30                         # (0, 600]
source_root = "src"                          # ruta relativa; si plugin.toml está dentro del paquete, se usa su directorio padre

[capabilities]
provides = ["text_statistics"]               # informativo, a nivel de plugin

[permissions]
requested = ["FILE_READ"]                    # capacidades del contrato tool v1; deben cubrir las de cada herramienta

[[tools]]
name = "file_stats"                          # ^[a-z][a-z0-9_]{0,63}$, único
description = "..."
capabilities = ["FILE_READ"]                 # no vacío
operation = "READ_ONLY"                      # READ_ONLY | WRITE_OPERATION | SENSITIVE_OPERATION | DESTRUCTIVE_OPERATION | EXTERNAL_SIDE_EFFECT
provides = ["file_stats"]                    # etiquetas para el router (opcional)
input_schema = { type = "object", properties = { path = { type = "string" } }, required = ["path"] }   # o "schemas/x.json"
output_schema = { type = "object" }          # opcional; si existe, el resultado se valida
timeout_seconds = 20                         # opcional

[dependencies]
plugins = { "acme.base" = ">=1.0.0" }        # deben estar registradas, en versión compatible y habilitadas
python_packages = ["regex>=2024"]            # se declaran, nunca se instalan automáticamente (aviso)

[configuration]
methods = ["file"]
schema = { type = "object", additionalProperties = false, properties = { max_bytes = { type = "integer" } } }

[trust]
level = "trusted"                            # solo informativo (trust_requested); la confianza la decide plugin_trust.json
```

## Tipos

CORE_PLUGIN, AGENT_PLUGIN, SKILL_PLUGIN, TOOL_PLUGIN, MCP_CONNECTOR, PROVIDER_ADAPTER, DATABASE_CONNECTOR, DEVOPS_CONNECTOR,
OBSERVABILITY_PLUGIN, QUALITY_GATE_PLUGIN y PROJECT_TEMPLATE_PLUGIN.

Pueden exponer herramientas CORE, TOOL, MCP_CONNECTOR, DATABASE_CONNECTOR, DEVOPS_CONNECTOR y QUALITY_GATE.

## Esquemas

JSON Schema 2020-12 (o draft-07 si se declara `$schema`), dentro del subconjunto acotado de `tools/schema.py`:

- `$ref` solo local;
- profundidad máxima 32;
- 1000 subesquemas como máximo;
- las palabras clave de aserción no soportadas son un error;
- las de anotación (`format`, `title`, `x-*`…) se ignoran.
