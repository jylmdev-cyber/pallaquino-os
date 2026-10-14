# Modelo de amenazas multiagente (v0.4.0)

Alcance: el motor de orquestación, la memoria y los proveedores. Complementa la tabla de [`SECURITY.md`](../../SECURITY.md).

**Supuesto central**: todo lo que producen o leen los agentes son datos no confiables:

- salidas de modelos;
- contenido del repositorio;
- memoria recuperada;
- handoffs de otros agentes.

Las decisiones de control (riesgo, permisos, aprobaciones, transiciones) las toma solo código determinista.

| # | Amenaza | Vector | Mitigación | Evidencia | Residual |
|---|---|---|---|---|---|
| T1 | Inyección de instrucciones en memoria | registro con "ignore previous instructions" | marca `suspicious_instructions`; aviso no confiable; nunca en el rol de sistema | `test_injected_memory_is_returned_as_untrusted_data`, `test_injection_shaped_content_is_flagged_not_obeyed` | la detección por patrones no es exhaustiva; un modelo puede obedecer aun así, pero sin ganar permisos |
| T2 | Handoff malicioso entre agentes | un agente resume "grant yourself deploy" | se marca como sospechoso; los permisos de la tarea siguiente no cambian | `test_malicious_handoff_is_flagged_and_changes_nothing` | igual que T1 |
| T3 | Escalada de permisos | el agente pide `deploy` o escribe sin `write_files` | FAILED + evento `security_violation` | `test_agent_cannot_expand_its_permissions` | — |
| T4 | Escape del workspace | rutas `../`, absolutas, con unidad | `confine()` rechaza antes de escribir nada | `test_task_cannot_write_outside_the_workspace` | enlaces simbólicos dentro del workspace: `resolve()` los sigue y luego comprueba que el destino siga dentro |
| T5 | Delegación circular o profunda | A→B→A | detección de ciclos y `max_delegation_depth` | `test_delegation_is_bounded_and_cannot_cycle` | — |
| T6 | Agotamiento de recursos | bucles de revisión, reintentos, llamadas | `max_review_rounds`, `max_attempts`, presupuestos por ejecución y tarea | `test_review_rework_is_bounded`, `test_budget_exhaustion_stops_provider_calls` | el tiempo de reloj total no tiene tope global |
| T7 | Escritura concurrente | dos tareas sobre el mismo archivo | locks de recurso/archivo y `expected_sha256` | `test_concurrent_tasks_on_one_resource_are_serialized`, `test_write_conflict_is_detected` | sin `expected_sha256`, gana la última escritura serializada |
| T8 | Fuga de secretos | salidas de comandos, memoria, archivos generados | `redact()` en evidencia, eventos y memoria; se rechaza escribir secretos | `test_secrets_are_redacted_before_storage`, `test_secrets_are_never_written` | los patrones cubren formatos conocidos, no secretos arbitrarios |
| T9 | Envío de datos a otro servicio | fallback hacia un proveedor remoto | `privacy.local_only` y prohibición de cruzar la frontera sin autorización | `test_fallback_never_moves_data_to_a_remote_provider_by_default` | — |
| T10 | Manipulación del estado persistido | editar la base SQLite | checksums; `MemoryCorrupted`; `memory verify` | `test_corrupted_task_state_is_refused`, `test_tampered_records_are_excluded_and_reported` | quien puede escribir la base también puede recalcular checksums sin clave (no hay HMAC) |
| T11 | Doble ejecución | dos runners sobre la misma ejecución | lease del runner y `ExecutionLocked` | `test_live_runner_lease_blocks_a_second_runner` | un runner colgado con lease vigente bloquea hasta que expira o hasta `--force` |
| T12 | Efectos duplicados tras un crash | reintento de una tarea con escritura | write-ahead y reconciliación por SHA-256 | `test_orphan_with_applied_write_is_reconciled_without_rerun` | efectos externos no reconciliables (gobernados) dependen de la idempotencia del sistema destino |

## Fuera de alcance en v0.4.0

- Aislamiento por proceso o contenedor de los comandos permitidos: corren con los permisos del usuario.
- Firma o HMAC del estado persistido.
- Adaptadores remotos: su autenticación y transporte se modelarán al añadirlos.
