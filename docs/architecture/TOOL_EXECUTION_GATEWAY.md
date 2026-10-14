# PALLAQUINO Tool Execution Gateway (v0.5.0)

Estado: **IMPLEMENTADO**. Código: `pallaquino_cli/tools/` (contracts, schema, registry, permissions, gateway, routing) y
`pallaquino_cli/platform.py`. Decisión: [ADR-0015](../adr/ADR-0015-tool-registry-and-execution-gateway.md).

## Flujo de una llamada (`ToolGateway.call`)

| # | Paso | Implementación | Evidencia en `checks` |
|---|---|---|---|
| 1 | recibir | ID de llamada; evento `tool_execution_requested` | `request received` |
| 2 | resolver | `ToolRegistry.entry`; un ID desconocido da `not_found` | `resolved <id> from <fuente> (trust …)` |
| 3 | disponibilidad | sonda de la fuente (conexión, proceso del plugin, catálogo) | `available` |
| 4 | validar argumentos | tamaño (`max_input_bytes`) + JSON Schema acotado | `arguments valid` |
| 5 | identificar | principal (agente o humano) y proyecto | `principal …` |
| 6–7 | permisos y aprobación | `PermissionGateway.evaluate`: contrato del agente, `contract` / `grant` / `per_call` | grant o aprobación usada |
| 8 | restricciones | registro write-ahead, idempotencia, timeout, cancelación | `risk …` |
| 9 | ejecutar | adaptador en un hilo con fecha límite; reintento solo en lecturas | `executed in N attempt(s)` |
| 10 | normalizar | `outputSchema`, `max_output_bytes`, redacción, marcas de inyección | `output matches schema`… |
| 11 | registrar | `tool_calls` + eventos `tool_execution_*`, `permission_*`, `policy_violation` | — |
| 12 | evidencia | resultado `{status, checks, result, trust, redacted, suspicious_instructions, traceparent}` | — |

Estados de salida: `COMPLETED`, `FAILED`, `DENIED` (exit 5 en la CLI) y `APPROVAL_REQUIRED` (exit 3).

## Integración con agentes

- **Planner**: los pasos `git_inspect`, `quality_scan` y `report` aparecen en solicitudes de descubrimiento que mencionan Git, calidad o
  informe. Cada requisito declara capacidades y una etiqueta `provides`, y `resolve_tools` elige la herramienta con el router, evaluando los
  permisos del agente asignado. Si no hay una herramienta permitida, usa un fallback declarado (por ejemplo `code_search`) y lo anota como
  aviso del plan.
- **Executor `tool`**: llama a la pasarela como `{"kind": "agent", "id": <agente>}` con el grant de tarea del contrato v2. Los resultados
  pasan a findings con la evidencia `tool call <id>`; si contienen instrucciones sospechosas se degradan a `hypothesis`.
- **Executor `technical_report`**: consolida los handoffs en Markdown dentro de `logs/reports/` (estado de instancia, fuera de Git) con un
  gate: el informe falla si ninguna sección cita evidencia.
- **Memoria**: guarda resúmenes de lecturas no sospechosas (`execution/tool_result`), hallazgos por tarea (`project/tool_findings`) y el
  informe (`project/technical_report`).

## Métricas (`pallaquino tools metrics`)

Plugins registrados y activos; conexiones configuradas y sanas; herramientas registradas y disponibles; ejecuciones correctas y fallidas;
timeouts; denegaciones; errores de autorización; violaciones de política; latencia por herramienta (número de llamadas, máxima, media) y
contadores de eventos `plugin_*`, `mcp_*`, `tool_*`, `permission_*` y `policy_*`.

## OpenTelemetry

- Cada llamada lleva un `traceparent` W3C: una traza por ejecución y un span por llamada. Se propaga en el `_meta` de las peticiones MCP
  (clave reservada por 2026-07-28).
- El JSONL de `executions export` ya usa nombres de campo de los logs de OpenTelemetry.
- No hay dependencia de OpenTelemetry: integrarlo sigue siendo opcional.
