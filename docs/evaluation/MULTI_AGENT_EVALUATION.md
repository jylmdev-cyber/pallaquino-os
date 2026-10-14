# Evaluación multiagente (v0.4.0)

Medido el 2026-10-14 en Windows 11, con Python 3.11.15. Todas las pruebas son offline: los proveedores son simulados o un stub HTTP local.

## Suite

| Archivo | Tests | Qué demuestra |
|---|---:|---|
| `test_orchestration_planning.py` | 19 | intención simple, compleja y ambigua; la IA asistida no puede bajar el riesgo ni conceder permisos; el router separa por dominio, informa capacidades faltantes, es reproducible y no usa historial simulado; planes acíclicos para las 14 intenciones y sus pares; validación de ciclos, dependencias y herramientas; máquina de estados |
| `test_scheduler.py` | 30 | orden por dependencias, concurrencia ≤ límite, dry-run, reintentos con backoff, fallos y bloqueo transitivo, timeouts, `--retry-failed`, cancelación y pausa desde otro controlador, aprobación, lease de runner, reconciliación tras crash, estado corrupto, reinicio de proceso, bucle de revisión acotado, adversariales |
| `test_memory.py` | 12 | ranking y límites, aislamiento entre proyectos, obsolescencia, redacción en disco, marcas de inyección, manipulación, base corrupta, confirmación de borrado, migración v1→v2, reinicio de proceso |
| `test_providers.py` | 15 | Ollama contra stub: disponible, sin configurar, auth, rate limit con Retry-After, 5xx, JSON inválido, timeout, uso desconocido, endpoint remoto; fallback permitido, denegado, entre fronteras, por privacidad y por tipo de error; presupuestos; configuración |
| `test_reference_scenario.py` | 11 | escenario de referencia por CLI; variante real informada sin simulación; compatibilidad de comandos 0.3; flujo plan→run→status→report→export→memoria; aprobación y códigos de salida; CLI en proceso |
| Suites anteriores | 67 | 0.3.x y PAL-007 (núcleo 12, CLI 8, estabilización 28, contratos 17, identidad 2) |
| **Total** | **154** | en verde en 5 ejecuciones (47–63 s en Windows) |

Un gate TEST registrado (`evidence/test-2026-10-14T16-15-04+00-00.json`) falló: un test heredado de 0.2.x no pudo borrar su directorio
temporal (`WinError 145`, carrera de Windows con archivos recién escritos). No es un fallo del producto. Se corrigió la infraestructura
de tests (`TemporaryDirectory(ignore_cleanup_errors=True)` en todos los tests) y el gate pasó en los dos reintentos siguientes. El
registro fallido se conserva.

## Escenarios adversariales exigidos

| Escenario | Test | Resultado |
|---|---|---|
| Prompt injection en documento recuperado | `test_injected_memory_is_returned_as_untrusted_data` | marcado; nunca llega al rol de sistema |
| Agente que intenta ampliar permisos | `test_agent_cannot_expand_its_permissions` | FAILED + `security_violation`; sin escritura |
| Handoff con información maliciosa | `test_malicious_handoff_is_flagged_and_changes_nothing` | marcado; permisos sin cambios |
| Delegación circular | `test_delegation_is_bounded_and_cannot_cycle` | rechazada con evento |
| Tarea que intenta salir del workspace | `test_task_cannot_write_outside_the_workspace` | 3 variantes rechazadas; nada escrito |
| Ejecución con presupuesto agotado | `test_budget_exhaustion_stops_provider_calls`, `test_task_budget_is_not_reset_by_retries` | `budget_exceeded`, sin reintento |
| Modificación concurrente del mismo archivo | `test_concurrent_tasks_on_one_resource_are_serialized`, `test_write_conflict_is_detected` | exclusión medida dentro de la sección protegida; conflicto detectado |

## Cobertura de sentencias

Medida con `trace` de la stdlib en proceso, trazando también los hilos del scheduler. Los subprocesos del CLI no se cuentan.

**Total: 94,4 %** (1841 de 1951 sentencias).

| Módulo | Cobertura |
|---|---:|
| `orchestration/scheduler.py` | 97,0 % |
| `orchestration/routing.py` | 97,3 % |
| `orchestration/intent.py` | 97,4 % |
| `orchestration/models.py` | 97,3 % |
| `orchestration/observability.py` | 95,5 % |
| `orchestration/executors.py` | 94,3 % |
| `orchestration/planning.py` | 93,2 % |
| `memory/store.py` | 96,4 % |
| `providers/router.py` | 98,6 % |
| `providers/mock.py` | 96,3 % |
| `providers/base.py` | 94,4 % |
| `providers/ollama.py` | 91,9 % |
| `cli_orchestration.py` | 91,5 % |
| `__main__.py` | 90,1 % |
| `core.py` | 91,9 % |
| `contracts.py` | 96,8 % |

Todos los módulos nuevos superan el objetivo de 90 % fijado en el roadmap. Una de dos mediciones con trazado registró un error
intermitente atribuible a la sobrecarga de instrumentación (unas 10 veces más lento) en un test sensible a tiempos. Sin trazado, la suite
pasó 3 de 3 veces.

## Escenario de referencia

`python scripts/run_reference_scenario.py` recorre el CLI real en subprocesos sobre una copia temporal del proyecto de prueba.

| Variante | Resultado |
|---|---|
| offline | **COMPLETED**, 5/5 comprobaciones (ejecución completa, funcionalidad presente, tests reales con salida 0, memoria persistida, traza completa). Ejecutado de verdad: `discover`, `verify`. Simulado: `design`, `backend`, `tests`, `code_review`, `docs` |
| real_provider | **No ejecutada**: no hay Ollama ni credenciales autorizadas en este equipo. No se simuló nada en su lugar |

## Qué no está evaluado

- Calidad de agentes con modelos reales (no hay proveedor real disponible).
- Linux y Python 3.14 en local (los cubre el CI del PR).
- Carga más allá de 100 tareas por ejecución y de 10 ejecuciones seguidas.
