# Tutorial: memoria y recuperación

## Qué se guarda

Cada ejecución persiste en `memory/pallaquino.db` (dentro de `.pallaquino/`):

- el plan, la ejecución y cada tarea, con historial de transiciones;
- los eventos;
- los locks;
- el resultado por agente.

Al terminar añade memoria consultable:

| Categoría | Contenido |
|---|---|
| project | mapa del repositorio |
| execution | resumen de la ejecución |
| quality | resultado de cada comando de tests |
| decision | ADR producidas por tareas `decision` |

```bash
python -m pallaquino_cli memory status --json
python -m pallaquino_cli memory search repository --category project --json
python -m pallaquino_cli memory inspect --id 1 --json
```

Lo recuperado siempre viene como `trust: untrusted`, con aviso, y con `suspicious_instructions: true` si el texto parece una instrucción
inyectada.

## Interrupción y reanudación

Si el proceso muere a mitad de una ejecución (cierre de terminal, reinicio), vuelve a ejecutar:

```bash
python -m pallaquino_cli resume --execution <execution_id> --json
```

1. Si otro runner sigue vivo (lease vigente), `resume` se niega con `ExecutionLocked`. Usa `--force` solo si sabes que ese proceso murió.
2. Las tareas que quedaron `RUNNING` se **reconcilian**:
   - si su intención de escritura (registrada antes de escribir) coincide por SHA-256 con los archivos actuales, pasan a COMPLETED sin
     repetirse;
   - si no, se reintentan con la misma clave de idempotencia.
3. El resto continúa respetando dependencias y aprobaciones.

Para volver a intentar tareas FAILED (por ejemplo, después de corregir el entorno):

```bash
python -m pallaquino_cli resume --execution <execution_id> --retry-failed --json
```

## Integridad

```bash
python -m pallaquino_cli memory verify --json
```

Si un plan, una ejecución o una tarea fueron editados fuera de PALLAQUINO, su checksum no coincide. En ese caso:

- `resume` falla con `MemoryCorrupted` en lugar de continuar sobre un estado no fiable;
- los registros de memoria manipulados se excluyen de las búsquedas y se informan.

## Retención y borrado (requieren confirmación)

```bash
python -m pallaquino_cli memory purge --expired --yes --json
python -m pallaquino_cli memory purge --older-than 90 --yes --json
python -m pallaquino_cli memory delete --id 12 --yes --json
```

Sin `--yes` la operación se rechaza con código 1. Cada borrado queda registrado como evento.
