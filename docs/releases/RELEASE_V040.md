# PALLAQUINO v0.4.0 — candidato de release

Fecha: 2026-10-14. Estado: **candidato local**. No está publicado: no hay push, tag ni GitHub Release (sección 19 del pedido v0.4.0).

## A. Estado del proyecto

- **Versión encontrada**: 0.3.2 en `main`, no la 0.3.0 que esperaba el pedido. Incluye PAL-005 (estabilización), 0.3.1 (locks
  multiplataforma) y 0.3.2 (snapshot de versiones verificado).
- **Base de esta rama**: 0.3.2 más PAL-007-A (contratos v2, PR #5) y PAL-007-B (alcanzabilidad), aún sin fusionar en `main`.
- **Versión objetivo**: 0.4.0.

Diferencias entre lo anunciado y lo real, ya presentes en 0.3.x y documentadas:

- el pipeline y los quality gates eran datos más scripts, sin motor de ejecución;
- los agentes eran plantillas;
- no había memoria persistente ni adaptadores de proveedor.

v0.4.0 añade el motor, que antes no existía.

## B. Arquitectura

- **Componentes nuevos**:
  - `pallaquino_cli/orchestration/`: models, intent, routing, planning, scheduler, executors, observability;
  - `pallaquino_cli/memory/` (SQLite);
  - `pallaquino_cli/providers/`: base, mock, ollama, router;
  - `pallaquino_cli/cli_orchestration.py`.
- **Contratos versionados**: intent_result, task, plan, execution y handoff (v1); más la máquina de estados de tarea y de ejecución.
- **Decisiones**: ADR-0010 (motor), ADR-0011 (memoria) y ADR-0012 (proveedores).
- **Dependencias externas**: ninguna nueva; solo la stdlib (sqlite3, concurrent.futures, urllib).

## C. Implementación

Archivos nuevos:

- código: 13 módulos más 3 `__init__.py`;
- tests: 5 archivos (87 tests nuevos);
- `scripts/run_reference_scenario.py` y `scripts/benchmark_orchestration.py`;
- `evaluation/reference_scenario/` (fixture, guion y escenario);
- configuración: `governance/providers.json`, `governance/command_allowlist.json` y `governance/routing_preferences.json`;
- 13 documentos, los datos crudos del benchmark y 3 ADR.

Archivos modificados:

- `__main__.py`: comandos nuevos; las formas antiguas no cambian;
- `core.py`: `compute_repository_map` y exclusiones de `memory/` y `logs/`;
- `manifest.json`: `instance_state` incluye `memory/*` y `logs/*`;
- `pyproject.toml`: subpaquetes;
- `.gitignore`.

Migraciones:

- el esquema de memoria v1→v2 se aplica solo al abrir la base;
- no hay migraciones de proyectos.

## D. Calidad

- **Tests**: 154, todos en verde, en Windows con Python 3.11.15. Antes de esta versión había 67. Hubo un fallo intermitente de limpieza de
  directorios temporales en Windows, ya corregido; ver la evaluación.
- **Cobertura de sentencias**: 94,4 % en proceso, con trazado de hilos.
- **Evaluaciones**: los 7 escenarios adversariales exigidos están cubiertos (ver
  [MULTI_AGENT_EVALUATION.md](../evaluation/MULTI_AGENT_EVALUATION.md)).
- **Benchmarks**: ver [BENCHMARK_RESULTS.md](../evaluation/BENCHMARK_RESULTS.md).
- **Escenario de referencia**: la variante offline pasa. La variante con proveedor real **no se ejecutó**, porque no hay proveedor autorizado.
- **No verificado**: Linux, Python 3.14 y el comportamiento con un modelo real.

## E. Seguridad

- **Controles**: permisos por contrato con denegación por defecto; herramientas gobernadas solo con aprobación; confinamiento al workspace;
  rechazo de secretos; redacción en memoria y eventos; memoria y handoffs no confiables y marcados; fallback sin cruzar la frontera de
  privacidad; presupuestos; lease de runner; checksums.
- **Riesgos residuales**: los del [modelo de amenazas](../security/MULTI_AGENT_THREAT_MODEL.md) (sin HMAC, sin aislamiento de comandos,
  hilos que exceden el timeout).
- **Requieren aprobación**: deploy, infrastructure_apply, release_publish, git_push y database_migration_apply. secrets_access no se concede
  a ningún agente.

## F. Entrega

Código, documentación, ejemplos (escenario de referencia y tutoriales), changelog y guía de migración. El ZIP reproducible y su SHA-256 se
generan con `scripts/package_release.py`. El hash queda en el sidecar comprometido junto a esta versión.

## G. Siguiente versión

Ver [ROADMAP_V040_TO_V050.md](../roadmap/ROADMAP_V040_TO_V050.md): ejecutor externo, Extension System, adaptadores comerciales verificados,
MCP y optimización de la persistencia del scheduler.
