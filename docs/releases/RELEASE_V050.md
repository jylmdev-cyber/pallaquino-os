# PALLAQUINO v0.5.0: candidato de release

- **Fecha**: 2026-10-14.
- **Estado**: **candidato local**. No está publicado: no hay push, tag, GitHub Release ni PyPI (secciones 24 y 26 del pedido).
- **Rama**: `feat/v0.5.0-extensions`, sobre `main` en `4ffde70` (v0.4.0 publicada el 2026-10-14).

## A. Estado del proyecto

- **Versión base verificada**: 0.4.0, igual que `main` y el tag `v0.4.0`. Las capacidades heredadas que el pedido esperaba existen y se
  comprobaron ejecutando la suite (154/154) antes de empezar.
- **Dependencias pendientes de 0.4.0**: ninguna bloqueaba los plugins ni MCP. La deuda técnica de 0.4.0 (persistencia del scheduler, FTS,
  HMAC) sigue abierta y no forma parte de este pedido.
- **Defecto heredado encontrado y corregido**: el ZIP publicado de 0.4.0 no contiene `pallaquino_cli/memory/`. `create_archive` excluía
  el estado de instancia `memory/` a cualquier profundidad. Al extraer ese ZIP, `pallaquino memory status` falla con `ModuleNotFoundError`
  (reproducido el 2026-10-14). El repositorio y el tag `v0.4.0` no están afectados. Corregido en 0.5.0, con un test de regresión; el ZIP
  de 0.5.0 se verificó ejecutando la suite y la demo desde el archivo extraído.
- **Hallazgo técnico**:
  - el SDK MCP instalado en el entorno del framework (1.26.0) no soporta 2026-07-28;
  - el SDK oficial que sí lo soporta (2.x) añade un árbol grande de dependencias;
  - de ahí sale ADR-0014.

## B. Arquitectura

- **Componentes nuevos** en `pallaquino_cli/`:
  - `tools/`: contratos, esquema, registro, permisos, pasarela y router;
  - `mcp/`: protocolo, transportes, cliente, servidor de referencia, conexiones, auth y política de red;
  - `extensions/`: manifiesto, SemVer, descubrimiento y gestor;
  - `integrations/`: filesystem, git, database y github;
  - `sdk/`: API, runner, harness y scaffolding;
  - `platform.py` y `cli_platform.py`.
- **Organización**: la estructura conceptual del pedido (sección 18) se adapta como subpaquetes de `pallaquino_cli`, igual que en ADR-0010.
  No se duplicaron componentes ni se movieron rutas públicas.
- **Decisiones**:
  - ADR-0013: extensiones;
  - ADR-0014: cliente MCP;
  - ADR-0015: registro y pasarela;
  - ADR-0016: credenciales, OAuth y red.
- **Dependencias externas**: ninguna nueva. Solo la stdlib (`tomllib`, `importlib.metadata`, `http.client`, `ssl`, `hashlib`, `secrets`,
  `sqlite3`).
- **Documentación**:
  - [PLUGIN_ARCHITECTURE](../architecture/PLUGIN_ARCHITECTURE.md), [MCP_CLIENT_ARCHITECTURE](../architecture/MCP_CLIENT_ARCHITECTURE.md),
    [TOOL_EXECUTION_GATEWAY](../architecture/TOOL_EXECUTION_GATEWAY.md) y [EXTENSION_CONTRACTS](../architecture/EXTENSION_CONTRACTS.md);
  - seguridad, integraciones, SDK y tutoriales en sus carpetas de `docs/`.

## C. Implementación

- **Código**: 26 módulos nuevos (incluidos los `__init__.py`). Cambian `core.py` (versión, estado de instancia, política, exclusiones del
  ZIP), `memory/store.py` (migración 3), `orchestration/` (ejecutor `tool`, pasos nuevos, planner con herramientas) y `__main__.py`.
- **Tests**: 8 archivos y 88 tests nuevos, más una aserción de regresión del archivo en `test_core.py`.
- **Ejemplos**:
  - `examples/pallaquino-example-plugin/` (pyproject, manifiesto, implementación, tests y ejemplo);
  - `examples/mcp_servers/quality_server.py`;
  - `scripts/run_codebase_analysis_demo.py`.
- **Migraciones**: store v2 → v3, automática. Un store v3 se sigue abriendo con 0.4.0 (comprobado con el código del tag `v0.4.0`).

## D. Calidad

- **Tests**:
  - Windows, Python 3.11.15, con `mcp` 2.3.0 en un venv aislado: 242 ejecutados, todos en verde, 1 omitido (enlaces simbólicos: el host
    no puede crearlos).
  - Windows, Python 3.11.15 sin el SDK: 242 en verde con 6 omitidos (enlaces simbólicos y los 5 de interop).
  - Windows, Python 3.12.10: en verde, con las omisiones anteriores más la instalación pip offline (no hay setuptools).
  - Desde el ZIP extraído (sin `.git`): la suite pasa, con el test de `git ls-files` omitido, y la demo da `ok`.
  - Error intermitente heredado: la limpieza de archivos WAL de SQLite en Windows (`test_scheduler`, WinError 32) falla de vez en cuando;
    queda vigilado (ver KNOWN_ISSUES).
- **Cobertura de sentencias** (Python 3.12, en proceso): 93 % del paquete. Por encima del 90 %: `tools/*`, `integrations/*` salvo github
  (90 %), `mcp/client`, `mcp/protocol`, `mcp/auth`, `mcp/connections` y `extensions/manager`, `manifest` y `semver`. El runner del SDK
  (30 %) y parte del servidor de referencia (82 %) se ejecutan en subprocesos que `coverage` no mide; sus tests los ejercitan de verdad.
- **Conformidad MCP**: ver [MCP_CONFORMANCE_REPORT.md](../evaluation/MCP_CONFORMANCE_REPORT.md). La interoperabilidad con el SDK oficial 2.3.0
  **pasa en las dos direcciones** (cliente y servidor de PALLAQUINO, stdio y Streamable HTTP, moderno y legacy).
- **Demo end-to-end**: `scripts/run_codebase_analysis_demo.py` pasa sus 12 comprobaciones offline en unos 2,3 s:
  - conexión 2026-07-28;
  - catálogo fijado;
  - grant con alcance;
  - router con herramientas Git y MCP;
  - ejecución sin simulación;
  - herramienta MCP ejecutada a través de la pasarela;
  - informe con gate superado;
  - memoria;
  - escritura no autorizada bloqueada;
  - repositorio analizado sin modificar.
- **Tutoriales**: sus comandos se ejecutaron en un proyecto temporal y las salidas documentadas son las obtenidas.

## E. Seguridad

Ver [MCP_THREAT_MODEL](../security/MCP_THREAT_MODEL.md), [PLUGIN_SECURITY_MODEL](../security/PLUGIN_SECURITY_MODEL.md) y
[TOOL_PERMISSIONS](../security/TOOL_PERMISSIONS.md). Los 12 escenarios de la sección 19.3 del pedido tienen tests:

- herramienta no autorizada;
- plugin malicioso;
- acceso fuera del workspace;
- token incorrecto o scope insuficiente;
- fuga de credenciales;
- prompt injection;
- tool poisoning;
- SSRF;
- permiso caducado;
- escalada;
- operación destructiva sin aprobación.

Riesgos residuales declarados:

- un plugin confiable no está en un sandbox del sistema operativo;
- el vault de credenciales en archivo no está cifrado;
- los checksums del store no tienen clave;
- el timeout de los adaptadores builtin es cooperativo.

## F. Criterios de aceptación (sección 23)

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Descubre plugins por metadatos | ✅ | `test_entry_point_distribution_…`, `test_real_pip_installation_…`, `test_discovery_reads_metadata_without_importing` |
| 2 | Valida manifiestos | ✅ | `ManifestTest` |
| 3 | Rechaza incompatibles | ✅ | `test_invalid_incompatible_and_duplicate_plugins` |
| 4 | Habilita y deshabilita extensiones confiables | ✅ | `test_full_lifecycle_with_isolated_execution` |
| 5 | Cliente MCP funcional | ✅ | `tests/test_mcp.py` (18) |
| 6 | Conexión STDIO | ✅ | `StdioTest` |
| 7 | Conexión Streamable HTTP | ✅ (contra el servidor de referencia) | `HttpTest` |
| 8 | Descubre herramientas MCP reales de servidores de prueba | ✅ | `quality_server.py` en un subproceso real |
| 9 | Valida entradas y salidas | ✅ | cliente y pasarela |
| 10 | Operaciones vía Permission Gateway | ✅ | `PermissionTest` |
| 11 | Bloquea operaciones no autorizadas | ✅ | exit 5, `DENIED` |
| 12 | Evidencia adversarial | ✅ | ver E |
| 13 | Registro consistente | ✅ | `RegistryTest` (conflictos, contratos, disponibilidad) |
| 14 | El motor de agentes usa una herramienta autorizada | ✅ | `test_planned_tool_tasks_run_as_the_agent_through_the_gateway` |
| 15 | Plugin funcional creado con el SDK | ✅ | plugin de ejemplo y `plugin create/test` |
| 16 | Registros de auditoría | ✅ | `tool_calls` y eventos |
| 17 | Ejemplo end-to-end | ✅ | `DemoTest` |
| 18 | Sin regresiones críticas conocidas | ✅ en Windows, py3.11 y 3.12 | los 154 tests de 0.4.0; Linux y py3.14 pendientes de CI |
| 19 | La documentación describe el comportamiento real | ✅ | tutoriales ejecutados |
| 20 | Empaquetado verificable | ✅ | ZIP reproducible y SHA-256 (sección G) |

**Clasificación**: candidato completo frente a los 20 criterios. La interoperabilidad con el SDK oficial MCP v2 está verificada; el CI en
Linux con py3.11 y 3.14 se ejecuta en el pull request de publicación.

## G. Entrega

- Código, contratos, SDK, cliente MCP, registro, pasarela, adaptadores, tests, ejemplos, documentación, changelog, informe de seguridad
  y guía de migración.
- El ZIP reproducible y su SHA-256 se generan con `scripts/package_release.py`; el hash queda en el sidecar comprometido.
- No se publica nada automáticamente.

## H. Siguiente versión

Ver [ROADMAP_V050_TO_V060.md](../roadmap/ROADMAP_V050_TO_V060.md).
