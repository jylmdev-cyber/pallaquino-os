# Changelog

Los cambios relevantes de este proyecto se documentan aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el versionado sigue
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- 0.6.0, Autonomous Project Factory (ver `docs/roadmap/ROADMAP_V050_TO_V060.md`).
- Arrastrado desde la Fase 3: ejecutor externo para asistentes sin API, adaptadores comerciales verificados, `subscriptions/listen`
  y optimización de la persistencia del scheduler.
- Publicación en PyPI y firma de artefactos.

## [0.5.0] - 2026-10-14

Ecosistema de plugins, cliente MCP 2026-07-28, registro unificado de herramientas y gobernanza (pedido v0.5.0).
Ver `docs/releases/RELEASE_V050.md`, ADR-0013 a ADR-0016 y `MIGRATION_GUIDE.md`.

### Added

- Universal Plugin Manager (`extensions/`):
  - manifiesto `plugin.toml` v1 con 11 tipos;
  - SemVer y compatibilidad;
  - descubrimiento por entry points `pallaquino.plugins` y `plugins/` sin importar código;
  - ciclo de vida con 11 estados;
  - política de confianza ligada al hash (`governance/plugin_trust.json`) y cuarentena;
  - instalación desde un directorio o un ZIP con SHA-256 sin ejecutar scripts;
  - actualización con rollback y desinstalación acotada.
- Ejecución aislada de plugins: subproceso `python -I` con entorno saneado que sirve el plugin como servidor MCP stdio; el catálogo vivo
  se compara con el manifiesto.
- Plugin Development SDK (`sdk/`): `Plugin`, `ToolCall`, `ToolResult`, runner aislado, `PluginHarness` y scaffolding (`pallaquino plugin
  create`). Plugin de ejemplo `examples/pallaquino-example-plugin`, instalable con pip.
- MCP Integration Engine (`mcp/`), cliente y servidor de referencia con la stdlib para la revisión 2026-07-28:
  - `server/discover`, `_meta` por petición y negociación de versión;
  - fallback legacy a `initialize` en stdio y HTTP;
  - tools, resources, prompts, MRTR, Tasks, progreso y cancelación;
  - cabeceras `Mcp-Method`, `Mcp-Name` y `Mcp-Param-*`;
  - paginación y caché `ttlMs`;
  - validación de esquemas y de tamaños.
- Connection Registry: estados, diagnóstico, revisión y fijación del catálogo con digest (detección de rug pull y de tool poisoning),
  clasificación humana de herramientas (`--classify`) y puente al registro.
- OAuth 2.1 y Credential Manager:
  - RFC 9728, RFC 8414/OIDC en el orden especificado, `issuer` exacto, PKCE S256, `resource` (RFC 8707) e `iss` (RFC 9207);
  - flujo loopback, refresh, revocación y step-up;
  - credenciales por referencia (`env:`/`vault:`) ligadas a un servidor y un emisor.
- Política de red anti-SSRF: solo HTTPS, sin direcciones privadas, loopback ni link-local, IP fijada y sin redirecciones.
- Unified Tool Registry, contrato `tool` v1: 12 capacidades, 5 clases de operación, riesgo y aprobación derivados (no se pueden debilitar)
  y etiquetas `provides`.
- Zero-Trust Tool Governance:
  - deny by default;
  - políticas `contract`, `grant` (alcance, caducidad, usos, revocación) y `per_call` (ligada al digest de los argumentos y de un solo uso);
  - puente con los grants de tarea de los contratos v2.
- Tool Execution Gateway, flujo de 12 pasos:
  - write-ahead, idempotencia, timeout y cancelación;
  - validación de la salida, redacción y detección de inyección;
  - auditoría (`tool_calls` y eventos) y `traceparent` W3C.
- Tool Router: local primero, permisos en seco, exclusión de remotos con datos sensibles e historial auditado; nunca inventa herramientas.
- Adaptadores builtin:
  - filesystem, con confinamiento, archivos sensibles y escrituras gobernadas;
  - Git, de solo lectura más `stage` gobernado;
  - SQLite, de solo lectura en tres capas;
  - GitHub, de solo lectura y deshabilitado por defecto.
- Orquestación: ejecutor `tool` y pasos `git_inspect`, `quality_scan` y `report`. El planner resuelve las herramientas con el router y el
  informe técnico tiene quality gate.
- CLI: `plugins`, `plugin`, `mcp`, `tools` y `permissions` (exit 3 si falta aprobación, 5 si se deniega).
- Demo end-to-end offline `scripts/run_codebase_analysis_demo.py` y servidor de prueba `examples/mcp_servers/quality_server.py`.
- Store: migración 3 (`platform_docs`, `tool_calls`).
- `governance/TOOL_AND_EXTENSION_POLICY.md` y `governance/integrations.json`.

### Changed

- Versión 0.5.0. `pyproject.toml` incluye los subpaquetes `tools`, `mcp`, `extensions`, `integrations` y `sdk`.
- `plugins/*` y `governance/plugin_trust.json` son estado de instancia (`init`, Git y el ZIP los excluyen).

### Security

- 84 tests nuevos, con escenarios adversariales: prompt injection, tool poisoning, rug pull, SSRF, credential leakage, path traversal,
  confused deputy, escalada, permiso caducado, operación destructiva sin aprobación, plugin malicioso y ZIP con traversal.

### Not included

- Interoperabilidad verificada con el SDK oficial MCP v2: la prueba existe y no se ejecutó.
- `subscriptions/listen`; adaptadores Docker y cloud; drivers de PostgreSQL y MySQL; sandbox del sistema operativo para plugins.

## [0.4.0] - 2026-10-14

Motor de orquestación multiagente, memoria persistente y capa de proveedores (pedido v0.4.0).
Ver `docs/releases/RELEASE_V040.md`, ADR-0010 a ADR-0012 y `MIGRATION_GUIDE.md`.

### Added

- Intelligent Intent Analyzer (`orchestration/intent.py`): 14 intenciones, multi-intención, tecnologías,
  alcance, permisos y criterios de aceptación; modo determinista offline y modo asistido por IA validado
  (el modelo nunca fija riesgo ni permisos).
- Agent Routing Engine (`orchestration/routing.py`): puntuación explicable y reproducible por capacidad,
  dominio, tecnología, señal de routing, preferencias, coste e historial verificado; capacidades faltantes
  con fallback; `pallaquino agents match`.
- Task Planning Engine (`orchestration/planning.py`): 24 pasos componibles, DAG con niveles paralelos y ruta
  crítica, detección de ciclos, validación contra contratos v2 y marcas de aprobación.
- Multi-Agent Scheduler (`orchestration/scheduler.py`): máquina de estados formal, concurrencia limitada,
  locks de recurso y archivo, reintentos con backoff, timeouts, pausa, cancelación, aprobaciones, lease de
  runner, reconciliación tras crash (at-least-once con write-ahead), bucle de revisión y delegación acotados.
- Ejecutores: internos (análisis de repositorio), comandos permitidos (`governance/command_allowlist.json`)
  y agentes vía proveedor, con confinamiento al workspace, rechazo de secretos y detección de conflictos.
- Project Memory Engine (`memory/store.py`): SQLite por proyecto con migraciones, búsqueda acotada,
  obsolescencia, redacción, checksums, confirmación de borrado y retención.
- Provider Abstraction Layer (`providers/`): contrato, errores normalizados, uso verificado frente a no
  verificado, presupuestos, router con privacidad y fallback autorizado; adaptadores `mock` y `ollama`.
- Observabilidad: métricas, traza completa y exportación JSONL compatible con OpenTelemetry.
- CLI: `plan <request>`, `run`, `status|resume|pause|cancel --execution`, `approve`, `memory`, `providers`,
  `executions`; códigos de salida estables.
- Escenario de referencia (`scripts/run_reference_scenario.py`), benchmark reproducible
  (`scripts/benchmark_orchestration.py`) y 87 tests nuevos (154 en total).
- Contratos v2 de agentes y skills (ADR-0008): `registry/agent_contracts.json` y
  `registry/skill_contracts.json` con entradas, salidas, dependencias, herramientas
  autorizadas con denegación por defecto, activación, criterios de éxito, casos de
  prueba y digest de la fuente. Generador `scripts/build_contracts.py` (dry-run salvo
  `--write`), validador `validate_contracts` y comando `pallaquino contracts [--id]`
  con carga controlada.
- Roles por etapa del pipeline (`agents` en `pipeline_definition.json`) y diez reglas
  de routing nuevas con sus goldens (ADR-0009): ningún agente ni skill queda
  inalcanzable (antes 20 y 9). Trece contratos de rol curados a mano.

### Changed

- Los skills especializados que existían sin conectar ahora son dependencias de sus
  agentes (versión menor +1 en 11 agentes).
- `scaffold_framework.py` y `expand_catalog.py` con `--write` solo crean archivos
  ausentes; reemplazar registros existentes exige `--overwrite`.

## [0.3.2] - 2026-10-14

### Changed

- Snapshot tecnológico re-verificado el 2026-10-14 contra fuentes oficiales (`PAL-006`):
  Python 3.14.8, Node.js 24.21.0 LTS, .NET 10.0.13 / SDK 10.0.402, Django 5.2.18 LTS,
  Nuxt 4.6.1, Docker Engine 29.9.0 y Compose 5.6.0; PostgreSQL 18.6 y Ubuntu 26.04.1
  siguen vigentes. TypeScript se mantiene en 6.0.3 con justificación actualizada.
  Python 3.15.0 y .NET 11 quedan fuera: el primero aún no lo declara Django y el
  segundo es release candidate.

### Fixed

- `scaffold_framework.py --write` ya no sobrescribe ni re-fecha el snapshot
  verificado: la semilla solo se escribe si el registro no existe.

## [0.3.1] - 2026-10-14

### Fixed

- Las claves de lock tratan `\` como separador en todos los sistemas: en Linux y
  macOS, `src\a.py` (enviado por un agente en Windows) generaba una clave distinta de
  `src/a.py` y permitía reservar dos veces el mismo archivo. Detectado por el CI de
  Linux tras publicar `v0.3.0`.
- Se eliminó un carácter de control (BEL) del CHANGELOG; un test impide que vuelvan
  a entrar caracteres de control en archivos de texto versionados.

## [0.3.0] - 2026-10-13

Fase 1 (auditoría y estabilización) del pedido v0.3. Detalle y evidencia en
`docs/AUDIT_REPORT.md`; cambios de comportamiento en `MIGRATION_GUIDE.md`.

### Added

- `pallaquino security [audit] --target <dir>`: escaneo de secretos de solo lectura
  que informa ruta, línea y tipo, nunca el valor.
- Identidad de commit configurable por proyecto en `governance/git_identity.json`
  (jimdev por defecto) y comando `pallaquino identity [--name --email] [--apply-local]`.
- `init --dry-run`, `validate --integrity-only` y `handoff --next-action/--missing/--unverified`.
- Resolución del root por `$PALLAQUINO_ROOT` y descubrimiento de `./.pallaquino`.
- `manifest.json#instance_state` y estado limpio para proyectos nuevos.
- `evaluation/risk_golden.json` y 29 tests nuevos (47 en total).
- CI: escaneo de secretos del repositorio y smoke test de instalación no editable.
- `docs/AUDIT_REPORT.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/adr/`,
  `docs/DEMO.md` y `MIGRATION_GUIDE.md`; ADR-0001 a ADR-0007.
- Sección pública para apoyar voluntariamente el proyecto mediante PayPal.

### Changed

- Los clasificadores de riesgo y routing coinciden por token completo.
- Cada validador declara `scope` (`integrity` o `environment`).
- `scaffold_framework.py` y `expand_catalog.py` son dry-run salvo `--write`.
- `validate_cli` usa un único subproceso (1.68 s → 0.14 s).
- `agents`/`skills` sin `--json` imprimen una tabla legible.
- `handoff` se deriva del estado registrado y marca `NOT_RECORDED` lo que falta.

### Fixed

- CI y tests dependientes del reloj (snapshot caducado) y de la identidad Git local.
- `init` copiaba la tarea, checkpoints y evidencia del framework a cada proyecto.
- La instalación no editable no encontraba sus datos.
- Falsos positivos de riesgo (`product`, `authors`, `reproduce`) y de routing.
- ZIP de release no reproducible y escritura CRLF en Windows.
- Locks: TTL ignorado, liberación fuera del root, carrera entre procesos y rutas
  absolutas del host en el estado versionado.
- `architecture_fitness.py` declaraba 4 reglas comprobadas cuando ejecutaba 1.
- `evidence.py` podía persistir secretos presentes en la salida de comandos.

### Security

- Ver `SECURITY.md` (modelo de amenazas y controles de 0.3.0).

## [0.2.1] - 2026-08-31

### Added

- README público detallado con badges, arquitectura, stack y perfiles.
- Archivos comunitarios, política de seguridad y plantillas de GitHub.
- CI para Python 3.11/3.14, Dependabot y release notes.
- Configurador seguro y reusable de identidad Git local.

### Changed

- Documentación de release y artefacto distribuible actualizados.

## [0.2.0] - 2026-08-31

### Added

- 24 agentes especializados, 60 skills y 46 tecnologías catalogadas.
- Seis perfiles de stack, siete domain packs y catorce gates condicionales.
- Evaluaciones de routing para web, enterprise, eventos, móvil e IA/RAG.

## [0.1.0] - 2026-08-31

### Added

- Framework inicial, CLI, pipeline, gobernanza, continuidad y empaquetado.

[0.4.0]: universal_ai_fullstack_orchestrator/releases/0.4.0.json
[0.3.2]: universal_ai_fullstack_orchestrator/releases/0.3.2.json
[0.3.1]: universal_ai_fullstack_orchestrator/releases/0.3.1.json
[0.3.0]: universal_ai_fullstack_orchestrator/releases/0.3.0.json
[0.2.1]: universal_ai_fullstack_orchestrator/releases/0.2.1.json
[0.2.0]: universal_ai_fullstack_orchestrator/releases/0.2.0.json
[0.1.0]: universal_ai_fullstack_orchestrator/releases/0.1.0.json
[Unreleased]: https://github.com/jylmdev-cyber/pallaquino-os/compare/v0.4.0...HEAD
