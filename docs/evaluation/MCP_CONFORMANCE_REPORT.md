# Informe de conformidad MCP 2026-07-28 (v0.5.0)

- Fecha: 2026-10-14.
- Especificación: https://modelcontextprotocol.io/specification/2026-07-28 (changelog, versioning, transports stdio y Streamable HTTP,
  server/discover, tools, resources, prompts, MRTR, cancellation y authorization) y el esquema de la extensión Tasks
  (`modelcontextprotocol/ext-tasks`, `schema/2026-07-28/schema.ts`).
- SDK oficial: `mcp` 2.3.0 en PyPI (2026-10-02), línea v2, que habla 2026-07-28. En este equipo está instalado `mcp` 1.26.0, que solo
  soporta hasta 2025-11-25.
- Contraparte de las pruebas: el servidor de referencia de PALLAQUINO (`pallaquino_cli/mcp/server.py`). Comparte con el cliente la misma
  lectura de la especificación, así que estas pruebas demuestran coherencia interna y cobertura de reglas, no interoperabilidad con
  terceros.

## Requisitos del cliente

| Requisito (2026-07-28) | Estado | Prueba |
|---|---|---|
| `_meta` por petición con `protocolVersion` y `clientCapabilities` (+ `clientInfo`) | cumple | `test_streamable_http_with_required_headers`, `test_server_validation_rules` |
| Sin `initialize` ni `Mcp-Session-Id` en modo moderno | cumple | `test_discover_negotiates_2026_without_initialize`, cabecera ausente en el test HTTP |
| `server/discover` y selección de versión; reintento ante -32022 | cumple | `test_version_mismatch_retries_or_fails_clearly` |
| Compatibilidad legacy: sondeo de discover y fallback a `initialize` (stdio y HTTP, solo `mode=auto`) | cumple | `test_legacy_server_falls_back_…`, `test_version_mismatch_…` |
| `resultType`: ausente se trata como `complete`; desconocido es inválido | cumple | `test_result_type_rules` |
| Cabeceras HTTP `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` y centinela base64 | cumple | `test_streamable_http_with_required_headers`, `test_header_value_encoding` |
| `x-mcp-header`: reflejo en `Mcp-Param-*` y exclusión de definiciones inválidas | cumple | `test_x_mcp_header_mirroring_…`, `test_x_mcp_header_annotations` |
| `Accept: application/json, text/event-stream`; respuesta JSON o SSE | cumple | `test_progress_over_sse_…` |
| Cancelación: `notifications/cancelled` (stdio) y cierre del stream (HTTP) | cumple | `test_cancellation_and_timeout`, `test_progress_over_sse_…` |
| Timeouts por petición | cumple | `test_cancellation_and_timeout` |
| Paginación (cursor) y caché `ttlMs` | cumple (caché con tope de 1 h) | `test_pagination_and_catalog_cache` |
| MRTR: `inputRequests`, `requestState` devuelto tal cual, ID nuevo en cada reintento, máximo de rondas | cumple | `test_multi_round_trip_input_is_denied_unless_authorized` |
| Esquemas JSON Schema 2020-12; sin `$ref` remotos; límites de composición | cumple (subconjunto declarado) | `SchemaValidatorTest` |
| Validación de `structuredContent` contra `outputSchema` | cumple | `test_tools_resources_prompts_…`, `test_malformed_and_oversized_responses` |
| Anotaciones no confiables | cumple | `test_lifecycle_review_pin_…` |
| Extensión Tasks: `CreateTaskResult`, polling de `tasks/get`, `tasks/cancel` | cumple | `test_tasks_extension_polls_to_completion` |
| stdio: un mensaje por línea, stderr como log y no como error, cierre escalonado | cumple | `test_non_protocol_stdout_…`, `StdioTransport.close` |
| Trace context (`traceparent`) en `_meta` | cumple | `test_streamable_http_with_required_headers` |
| Autorización: RFC 9728, RFC 8414/OIDC en orden, `issuer` exacto, PKCE S256, `resource`, `iss` (RFC 9207), step-up y credenciales por emisor | cumple contra el stub | `tests/test_oauth.py` |
| `subscriptions/listen` | **no implementado** | — |
| Roots, Sampling, Logging (en desuso) | no implementados, por decisión | — |
| Elicitación con URL y formulario a través del usuario | no implementado: el manejador por defecto deniega | — |

## Requisitos del servidor de referencia

Origin → 403; GET y DELETE → 405; peticiones sin cabeceras o con valores que no coinciden → 400 con -32020; versión → 400 con -32022 y
`supported`; método desconocido → 404 con -32601; petición sin `_meta` → 400 con -32602; `tools/list` en orden determinista con `ttlMs` y
`cacheScope`; `resultType` en todos los resultados; `serverInfo` en `_meta`; notificaciones → 202; no responde a peticiones canceladas.

## Interoperabilidad con terceros

| Contraparte | Resultado |
|---|---|
| SDK oficial `mcp` ≥ 2 (stdio, modo moderno y legacy) | **NO EJECUTADO**. `tests/test_mcp_interop_official_sdk.py` existe y se omite porque en este equipo está `mcp` 1.26.0. Ejecutarlo requiere instalar `mcp>=2` en un entorno aislado (descarga de PyPI), y eso queda pendiente de autorización |
| Servidores públicos o comerciales | no ejecutado: requiere credenciales y una autorización que no existen |
| Proveedor de identidad real | no ejecutado: solo stub local |

Hasta que la prueba contra el SDK oficial pase, la interoperabilidad con terceros se considera **no verificada**.
