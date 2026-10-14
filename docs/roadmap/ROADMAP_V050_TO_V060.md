# Roadmap v0.5.0 → v0.6.0 (Autonomous Project Factory)

0.6.0 genera proyectos: scaffolding full stack, arquitecturas, selección de stack, plantillas, API, modelos de datos, autenticación, tests,
Docker, CI/CD, documentación y preparación del despliegue. 0.5.0 no implementa nada de eso; solo deja preparados los puntos de extensión.

## Puntos de extensión ya disponibles

| Necesidad de 0.6.0 | Punto de extensión en 0.5.0 |
|---|---|
| Plantillas reutilizables | tipo `PROJECT_TEMPLATE_PLUGIN` (se valida y registra; falta el cargador) |
| Generadores como herramientas | `TOOL_PLUGIN` con `provides` (por ejemplo `scaffold_api`), enrutado por el planner igual que `quality_scan` |
| Escritura gobernada | `core.files.write` con grant, `expected_sha256` y `create_only` |
| Agentes y skills nuevos | tipos `AGENT_PLUGIN` y `SKILL_PLUGIN` (contratos v2 de 0.4.0 como formato de carga) |
| Bases de datos | protocolo `DatabaseAdapter` |
| Verificación | ejecutor `command` con allowlist y pasos `verify`, y gate del informe |

## Deuda técnica de 0.5.0

| Deuda | Propuesta |
|---|---|
| La interoperabilidad con el SDK oficial MCP v2 se verificó en local, pero no en CI | job opcional de CI que instale `mcp>=2` y ejecute `tests/test_mcp_interop_official_sdk.py` |
| Sin `subscriptions/listen` | cliente de subscripción con reconexión y re-review automático al recibir `tools/list_changed` |
| Plugins sin sandbox del sistema operativo | contenedor opcional o Job Objects/AppContainer en Windows y namespaces en Linux, solo donde exista un entorno verificado |
| Vault en archivo sin cifrar | keyring por defecto si está disponible; cifrado con una clave de keyring |
| Timeouts cooperativos en adaptadores builtin | ejecutar los adaptadores lentos en un subproceso |
| Tipos de plugin sin cargador | cargadores para AGENT, SKILL y PROJECT_TEMPLATE |
| Deuda de 0.4.0 (transacción por transición, FTS, HMAC) | sigue en ROADMAP_V040_TO_V050 |

## Criterios de entrada para 0.6.0

- CI en Linux en verde para 0.5.0.
- Interop con el SDK oficial ejecutada al menos una vez: hecho el 2026-10-14 (5/5 con `mcp` 2.3.0).
- Ningún criterio de la sección 23 de 0.5.0 en regresión.
