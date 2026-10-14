# Contratos de extensión (v0.5.0)

Todos los contratos son JSON o TOML versionados y tienen su validador. Ninguno se acepta como texto libre.

## `tool` v1 (`tools/contracts.py`)

| Campo | Regla |
|---|---|
| `tool_id`, `namespace`, `name` | `core.*` (builtin), `plugin.<id>.*`, `mcp.<servidor>.*`; un mismo ID desde otra fuente es un conflicto |
| `source` | `{kind: builtin\|plugin\|mcp, id, trust: builtin\|trusted\|untrusted}`; solo los builtin tienen confianza builtin |
| `input_schema`, `output_schema` | JSON Schema 2020-12, subconjunto acotado; `$ref` solo local |
| `capabilities` | FILE_READ, FILE_WRITE, CODE_EXECUTION, GIT_READ, GIT_WRITE, DATABASE_READ, DATABASE_WRITE, NETWORK_READ, NETWORK_WRITE, CLOUD_MANAGEMENT, DEPLOYMENT, SECRETS_ACCESS |
| `operation` | READ_ONLY, WRITE_OPERATION, SENSITIVE_OPERATION, DESTRUCTIVE_OPERATION, EXTERNAL_SIDE_EFFECT |
| `risk`, `approval` | derivados (`derive_risk`, `derive_approval`); no se pueden debilitar |
| `provides` | etiquetas funcionales (`git_status`, `code_search`, `quality_scan`…) asignadas por una fuente revisada |
| `timeout_seconds`, `retry`, `limits` | (0, 3600] s; solo READ_ONLY se reintenta; límites de entrada y salida en bytes |
| `classification` | `builtin`, `reviewed_manifest`, `human` o `pallaquino_default` |
| `annotations` | pistas no confiables; se muestran, nunca deciden |
| `definition_sha256` | digest de la definición MCP fijada (detección de rug pull) |

## Manifiesto de plugin v1 (`plugin.toml`)

Referencia completa en [PLUGIN_MANIFEST_REFERENCE.md](../sdk/PLUGIN_MANIFEST_REFERENCE.md).

## Conexión MCP (`connection`)

`connection_id`, `transport` (`stdio` con `command` y `env` solo con referencias `env:`, o `http` con `url`, `network`, `credential_ref` e
`issuer`), `mode` (`auto`/`modern`/`legacy`), `timeout_seconds`, `trust`, `tool_policies` (clasificación humana por herramienta:
`operation`, `capabilities`, `provides`, `enabled`) y `extensions`.

## Grant y aprobación

- **Grant**: `grant_id`, `tool_pattern` (un ID, o `espacio.*`), `principal` (agente o `*`), `operations` (nunca SENSITIVE, DESTRUCTIVE ni
  EXTERNAL_SIDE_EFFECT), `project`, `expires_at` (máximo 90 días), `max_uses`, `uses`, `revoked_at` y `granted_by`.
- **Aprobación**: `approval_id`, `tool_id`, `args_digest` (SHA-256 de `[tool_id, argumentos]`), `principal`, `expires_at` (60 min por
  defecto) y `used_at` (un solo uso).

## Tarea con ejecutor `tool` (extensión del contrato `task` v1)

`executor = {kind: "tool", requirements: [{provides, capabilities, arguments, fallback?}], resolved: [{tool_id, arguments, fallback, needs_approval, reasons}]}`.

Los argumentos admiten `{workspace}`, que se sustituye en tiempo de ejecución. Los contratos v1 de 0.4.0 no cambian: `tool` se añade a
`EXECUTOR_KINDS`.

## Puntos de extensión para 0.6.0 (Project Factory)

- Tipos `PROJECT_TEMPLATE_PLUGIN`, `AGENT_PLUGIN` y `SKILL_PLUGIN`: ya se validan y registran; falta su cargador.
- `DatabaseAdapter` (Protocol) para conectores PostgreSQL y MySQL.
- `provides` en el planner: un generador de scaffolding se enruta igual que `quality_scan`.
