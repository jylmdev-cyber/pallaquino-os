# Changelog

Los cambios relevantes de este proyecto se documentan aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) y el versionado sigue
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Las claves de lock tratan `\` como separador en todos los sistemas: en Linux y
  macOS, `src.py` (enviado por un agente en Windows) generaba una clave distinta de
  `src/a.py` y permitía reservar dos veces el mismo archivo. Presente en `v0.3.0`;
  candidato a 0.3.1.

### Planned

- Fase 1.1: re-verificación del snapshot tecnológico (`PAL-006`).
- Fase 2: contratos v2, motor de orquestación, Project Memory y adaptadores de
  proveedor (ver `docs/ROADMAP.md`).
- Publicación en PyPI y firma de artefactos.

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

[0.3.0]: universal_ai_fullstack_orchestrator/releases/0.3.0.json
[0.2.1]: universal_ai_fullstack_orchestrator/releases/0.2.1.json
[0.2.0]: universal_ai_fullstack_orchestrator/releases/0.2.0.json
[0.1.0]: universal_ai_fullstack_orchestrator/releases/0.1.0.json
[Unreleased]: https://github.com/jylmdev-cyber/pallaquino-os/compare/v0.3.0...HEAD
