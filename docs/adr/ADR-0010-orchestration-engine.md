# ADR-0010: Motor de orquestación — contratos, máquina de estados y semántica de entrega

- Status: accepted (2026-10-14, v0.4.0)
- Confidence: high para contratos, estados y recuperación; medium para la calidad de planes en dominios no cubiertos por las plantillas
- Context: hasta 0.3.x el pipeline, el grafo de tareas y los agentes eran datos sin motor que los ejecutara. El pedido v0.4.0 exige transformar una
  solicitud en un plan verificable, ejecutarlo con varios agentes y recuperarlo tras una interrupción.
- Options: (a) un orquestador por LLM que decida en texto libre — no reproducible ni auditable; (b) dependencias externas (Celery, Airflow,
  Ray) — rompen "solo stdlib, offline"; (c) motor propio en la stdlib: planificación determinista sobre contratos v2, DAG validado, scheduler
  con hilos y persistencia SQLite.
- Decision: (c).
  - Código en subpaquetes de `pallaquino_cli` (`orchestration/`, `memory/`, `providers/`): preserva la importación pública `pallaquino_cli` y el
    empaquetado; la estructura de referencia del pedido (`core/`, `orchestration/` en la raíz) se adapta en lugar de duplicarse.
  - Contratos JSON versionados (`intent_result`, `task`, `plan`, `execution`, `handoff`) con validadores; el scheduler nunca consume texto libre.
  - `plan` y `run` son operaciones separadas: un plan no se ejecuta por existir, y solo un plan `PLANNED` con validación sin errores puede ejecutarse.
  - Máquina de estados formal (`TASK_TRANSITIONS`, `EXECUTION_TRANSITIONS`); toda transición se valida y se persiste antes de actuar.
  - Entrega **at-least-once**. Cada intento tiene token y dueño de locks propios. Las escrituras se registran antes de aplicarse (write-ahead);
    al reanudar, una tarea huérfana se completa por reconciliación si todos sus archivos ya tienen el contenido planificado y, si no, se
    reintenta con la misma clave de idempotencia. No se promete exactly-once.
  - Herramientas gobernadas (deploy, publicación, migraciones, infraestructura, push, secretos) solo se ejecutan con una aprobación registrada.
  - Bucle de calidad y delegación acotados (`max_review_rounds`, `max_delegation_depth`, presupuestos); una revisión que sigue pidiendo cambios
    al agotar las rondas **falla** y bloquea a sus dependientes.
- Consequences: el motor es reproducible y auditable offline. Las tareas de agente necesitan un proveedor; sin proveedor real solo existe la
  simulación, que se etiqueta `simulated` en cada tarea, handoff, métrica e informe.
- Reversal: el motor es aditivo; eliminar los subpaquetes y los comandos nuevos devuelve el comportamiento de 0.3.
