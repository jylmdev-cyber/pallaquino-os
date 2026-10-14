# Permisos de herramientas (v0.5.0)

## Matriz de decisión

| Operación \ Fuente | builtin | plugin confiable | MCP (sin clasificar) | MCP clasificada por un humano |
|---|---|---|---|---|
| READ_ONLY | `contract`: basta el grant de tarea del agente | `grant` | — (por defecto EXTERNAL_SIDE_EFFECT) | `grant` |
| WRITE_OPERATION | `grant` | `grant` | — | `grant` |
| SENSITIVE / DESTRUCTIVE / EXTERNAL_SIDE_EFFECT | `per_call` | `per_call` | `per_call` | `per_call` |
| capacidades SECRETS_ACCESS, DEPLOYMENT, CLOUD_MANAGEMENT, DATABASE_WRITE, NETWORK_WRITE | `per_call` | `per_call` | `per_call` | `per_call` |

Un agente también necesita que su grant de tarea (contratos v2) cubra cada capacidad (`CAPABILITY_GRANTS`):

| Capacidad | Herramienta abstracta |
|---|---|
| FILE_READ, GIT_READ, DATABASE_READ | `read_repository` / `search_repository` |
| FILE_WRITE | `write_files` |
| GIT_WRITE | `git_commit` |
| CODE_EXECUTION | `run_tests`, `run_linters`, `run_build`, `run_security_scan` |
| NETWORK_READ | `network_read` |
| DATABASE_WRITE, CLOUD_MANAGEMENT, DEPLOYMENT, SECRETS_ACCESS | gobernadas: `database_migration_apply`, `infrastructure_apply`, `deploy`, `secrets_access` (siempre `per_call`) |
| NETWORK_WRITE | ninguna: solo con aprobación humana |

## Comandos

```bash
pallaquino permissions grant mcp.quality.quality_scan --principal project_analyzer --operation READ_ONLY --days 1 --reason "auditoría"
pallaquino permissions list [--all]
pallaquino permissions inspect <grant-id|approval-id>
pallaquino permissions revoke <grant-id>
pallaquino permissions history
pallaquino tools run mcp.quality.echo --args '{"message":"hola"}' --approve   # aprobación de esta llamada exacta
```

## Reglas

- **Deny by default.** Sin grant ni aprobación, la pasarela devuelve `DENIED` (exit 5) o `APPROVAL_REQUIRED` (exit 3).
- **Alcance.** Un grant se limita al proyecto (siempre), a un principal (o `*`), a una herramienta o espacio de nombres (`mcp.quality.*`;
  nunca `*`) y a las clases de operación indicadas.
- **Caducidad.** Un grant dura como máximo 90 días y puede tener `max_uses`. Una aprobación caduca en 60 minutos y se usa una sola vez.
- **No implícito.** Los grants rechazan operaciones SENSITIVE, DESTRUCTIVE y EXTERNAL_SIDE_EFFECT, y no cubren herramientas `per_call`
  aunque coincida el patrón.
- **Ligado a los argumentos.** Una aprobación vale solo para el digest exacto de `[tool_id, argumentos]`.
- **Historial.** Cada decisión deja evento `permission_granted`, `permission_denied`, `permission_grant_created`, `permission_revoked` o
  `permission_approval_created`. Las comprobaciones en seco (`tools check`, router) no generan eventos.
