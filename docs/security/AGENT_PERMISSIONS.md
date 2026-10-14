# Permisos de agentes (v0.4.0)

Las herramientas se **deniegan por defecto**. Una tarea solo puede usar las herramientas que cumplen las tres condiciones: (1) el paso del plan
las declara, (2) el contrato v2 del agente las autoriza y (3) son de un nivel no gobernado o tienen una aprobación registrada.

| Nivel | Herramientas | Quién |
|---|---|---|
| read | read_repository, search_repository, read_registry | todos los agentes |
| execute | run_tests, run_linters, run_build, run_security_scan | todos los agentes; los comandos se limitan a `governance/command_allowlist.json` |
| network | network_read | categorías governance, release, integration, ai, platform |
| write | write_files, git_commit | agentes con `can_write_code` |
| governed | deploy, infrastructure_apply, release_publish, git_push, database_migration_apply, secrets_access | solo como `approval_required`, y solo para `can_deploy` (deploy, infraestructura), la categoría release (publicación, push) y los escritores de data (migraciones). **Ningún agente recibe `secrets_access`** |

## Controles en tiempo de ejecución

| Control | Dónde | Test |
|---|---|---|
| El plan rechaza herramientas no autorizadas por el contrato | `validate_plan` | `test_validation_rejects_cycles_unknown_dependencies_and_unauthorized_tools` |
| Herramienta gobernada → WAITING_APPROVAL hasta `pallaquino approve` | `validate_plan`, `Scheduler._promote` | `test_governed_task_waits_for_explicit_approval`, `test_approval_flow_and_waiting_exit_code` |
| El agente pide herramientas fuera de su concesión → FAILED + `security_violation` | `executors._agent` | `test_agent_cannot_expand_its_permissions` |
| Escritura fuera del workspace (absoluta, `..`, unidad) | `executors.confine` | `test_task_cannot_write_outside_the_workspace` |
| Contenido con forma de secreto no se escribe | `executors._agent` | `test_secrets_are_never_written` |
| Comando fuera de la lista permitida | `executors._command` | lista en `governance/command_allowlist.json` |
| La delegación no amplía permisos (intersección) ni crea ciclos | `Scheduler._delegate` | `test_delegation_is_bounded_and_cannot_cycle` |
| Un `.md` de agente alterado no se carga | `contracts.load_contract` | `test_edited_source_is_detected_and_refused` |
| Presupuestos de llamadas, tokens y coste | `providers.Budget` | `test_budget_exhaustion_stops_provider_calls`, `test_task_budget_is_not_reset_by_retries` |

## Aprobaciones

`pallaquino run --plan P --approve T05` o `pallaquino approve --execution E --task T05` registran
`{task_id, approved_by, at, scope}`. El campo `scope` contiene las herramientas gobernadas exactas. La aprobación vale solo para esa tarea
de esa ejecución (HUMAN_APPROVAL_POLICY).

Las herramientas gobernadas **no tienen ejecutor real** en v0.4.0: una tarea `deploy` aprobada se ejecuta por medio de un agente o proveedor y
no ejecuta despliegues por sí misma.
