# Tutorial: primera ejecución multiagente

Partirás de un proyecto Python mínimo y harás que PALLAQUINO planifique, asigne agentes, ejecute, pruebe, recuerde y entregue un informe.
Todo funciona offline.

> **Qué es real y qué es simulado.** Sin un proveedor de IA real, las tareas de agente las responde el proveedor `mock`: con un guion,
> si configuras uno; si no, sin cambios. Esas tareas quedan marcadas `simulated: true`. El descubrimiento del repositorio y la ejecución de
> tests sí son reales.

## 1. Preparar un proyecto

Usa el proyecto de ejemplo incluido:

```bash
cd universal_ai_fullstack_orchestrator
cp -r evaluation/reference_scenario/fixture /tmp/calc
python -m pallaquino_cli init --target /tmp/calc --json
cd /tmp/calc/.pallaquino
```

`init` crea `/tmp/calc/.pallaquino` con estado limpio e incluye el paquete `pallaquino_cli`, así que los comandos siguientes funcionan desde
ese directorio sin instalar nada. Si instalaste el paquete con `pip install -e ./universal_ai_fullstack_orchestrator`, puedes usar el comando
`pallaquino` en lugar de `python -m pallaquino_cli`.

## 2. Usar respuestas con guion (opcional)

Para una simulación determinista, apunta el proveedor `mock` al guion del escenario de referencia. Edita `governance/providers.json`:

```json
"mock": {"enabled": true, "responses_file": "evaluation/reference_scenario/responses.json"}
```

## 3. Planificar

```bash
python -m pallaquino_cli plan "add a multiply function to the calculator module with tests" --workspace /tmp/calc --json
```

La salida es un contrato `plan` con:

- `tasks`: cada una con `agent`, `routing.method` y `routing.reasons`, `permissions` y `dependencies`;
- `dag.levels`: las tareas de un mismo nivel pueden ejecutarse en paralelo;
- `dag.critical_path`;
- `validation`;
- `approvals_required`.

Planificar **no ejecuta nada**. Guarda el `plan_id`.

## 4. Revisar sin ejecutar y luego ejecutar

```bash
python -m pallaquino_cli run --plan <plan_id> --dry-run --json
python -m pallaquino_cli run --plan <plan_id> --json
```

| Código de salida | Significado |
|---:|---|
| 0 | COMPLETED |
| 1 | FAILED |
| 3 | esperando aprobación o en pausa |
| 4 | CANCELLED |

Si el plan incluye herramientas gobernadas (por ejemplo `release_publish`), la ejecución se detiene en `WAITING_APPROVAL` hasta que las apruebes:

```bash
python -m pallaquino_cli approve --execution <execution_id> --task T05 --json
python -m pallaquino_cli resume --execution <execution_id> --json
```

## 5. Inspeccionar

```bash
python -m pallaquino_cli status --execution <execution_id> --json
python -m pallaquino_cli executions report <execution_id> --json
python -m pallaquino_cli executions export <execution_id> --json
python -m pallaquino_cli memory search multiply --json
```

- `report` reconstruye solicitud → plan → agente → ejecución → validación → resultado.
- `export` escribe `logs/<execution_id>.jsonl` con campos compatibles con OpenTelemetry.
- En la traza, `verify` incluye la evidencia real del comando de tests (`exit_code`).

## 6. Controlar ejecuciones largas

Desde otra terminal:

```bash
python -m pallaquino_cli pause --execution <execution_id> --json
python -m pallaquino_cli cancel --execution <execution_id> --json
```

## Siguiente

- Memoria y recuperación: [MEMORY_AND_RECOVERY.md](MEMORY_AND_RECOVERY.md).
- Proveedor local real (Ollama): [PROVIDER_ABSTRACTION.md](../architecture/PROVIDER_ABSTRACTION.md#ollama).
