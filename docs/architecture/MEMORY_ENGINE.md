# PALLAQUINO Project Memory Engine

Estado: **IMPLEMENTADO** (`pallaquino_cli/memory/store.py`, ADR-0011). Los embeddings y las bases vectoriales son una extensión **PLANIFICADA**,
nunca una dependencia.

## Almacenamiento

- Archivo `memory/pallaquino.db` dentro de la instalación del proyecto (`.pallaquino/`). Es estado de instancia: lo ignoran Git, `init`
  y el ZIP.
- Modo WAL, con `busy_timeout` de 30 s. Al abrir ejecuta `PRAGMA quick_check`, y una base corrupta lanza `MemoryCorrupted`.
- Migraciones en `schema_migrations`. La versión actual es la 2, que añade la columna `redacted`; una base v1 se actualiza al abrirla.

| Tabla | Contenido |
|---|---|
| records | memoria categorizada: project, execution, decision, quality, agent_performance |
| plans, executions, tasks | estado del motor (los checkpoints); cuerpo JSON con checksum |
| events | log estructurado y redactado: ts, execution, task, agent, tipo, severidad, duración, resultado |
| locks | locks de recurso y de archivo con lease |
| agent_runs | resultado por agente con marcas `verified` y `simulated` |

## Recuperación contextual

`search(query, category, kind, since, limit, max_chars, include_stale)`:

- coincidencia por palabras clave, ordenada por número de coincidencias y luego por recencia;
- respeta `limit` y `max_chars`;
- devuelve `excluded` (registros corruptos y obsoletos que coincidían), con un aviso de datos no confiables, y en cada elemento `trust`,
  `stale` y `suspicious_instructions`.

Un registro es obsoleto si su TTL venció o si otro con la misma clave lo reemplazó.

Los agentes reciben la memoria dentro de `retrieved_memory` en el mensaje de usuario, con ese aviso. **Nunca en el rol de sistema.**

## Seguridad

| Requisito | Implementación |
|---|---|
| Separar proyectos | columna `project` en todas las tablas y en cada consulta. El identificador por defecto es el SHA-256 de la ruta del root |
| Secretos | `redact()` sobre contenido, resumen y eventos antes de escribir. Un test verifica que el token no llega al archivo |
| Integridad | checksum por documento: lo manipulado se excluye o se refusa y se informa en `memory verify` |
| Eliminación | `delete_record` y `purge` exigen `confirm` (`--yes`) y quedan auditados |
| Retención | `purge --expired` y `--older-than N` |
| Contaminación de contexto | marcas de inyección y no confiabilidad. El historial de agentes solo cuenta ejecuciones reales verificadas |

## CLI

```bash
pallaquino memory status
pallaquino memory search arquitectura --category decision
pallaquino memory inspect --id 12
pallaquino memory verify
pallaquino memory purge --expired --yes
```
