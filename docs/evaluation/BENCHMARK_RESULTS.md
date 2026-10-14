# Resultados de benchmark — línea base v0.4.0

Comando: `python scripts/benchmark_orchestration.py`. Datos crudos: [`benchmark_baseline_v040.json`](benchmark_baseline_v040.json).

- Equipo: Windows 11 (10.0.26300), AMD64, Python 3.11.15, 2026-10-14.
- Proveedores simulados, sin red ni APIs comerciales. Las cifras solo son comparables en el mismo equipo y la misma versión de Python.
- No hay una versión anterior con la que comparar: el motor no existía en 0.3.x. Por eso no se informan porcentajes de mejora.

## Planificación (análisis de intención + router + validación con carga verificada de contratos)

| Solicitud | Mediana | p95 | Tareas |
|---|---:|---:|---:|
| Autenticación y roles en Nuxt + PostgreSQL | 37,1 ms | 44,5 ms | 10 |
| Migración de base de datos | 40,3 ms | 43,1 ms | 11 |
| Optimización de rendimiento | 24,8 ms | 26,3 ms | 7 |
| Bug fix | 17,3 ms | 19,9 ms | 5 |
| Preparación de release | 17,1 ms | 19,1 ms | 5 |

## Router

`select_agents` con 3 capacidades, un dominio, una tecnología y riesgo HIGH, sobre 59 contratos.

| Medida | Valor |
|---|---:|
| Mediana | 1,48 ms |
| p95 | 3,22 ms |
| Muestras | 200 |

## Memoria (SQLite, WAL)

| Medida | Valor |
|---|---:|
| Escribir 1000 registros, cada uno en su transacción | 1004 ms (1,0 ms/registro) |
| Búsqueda por palabras clave sobre 1000 registros, mediana | 13,1 ms (p95 19,9 ms) |
| Tamaño en disco con WAL | 4,4 MB |

## Scheduler (100 tareas independientes, cada una con 10 ms simulados)

| Workers | Duración | Tareas/s |
|---:|---:|---:|
| 1 | 2,67 s | 37,4 |
| 4 | 1,19 s | 83,8 |
| 8 | 1,24 s | 80,9 |

Con un trabajo de 10 ms por tarea, el máximo teórico con 4 workers sería unas 400 tareas/s. La sobrecarga medida es de unos 9 ms por tarea, y
añadir workers por encima de 4 no ayuda: la persistencia de cada transición y de cada evento en SQLite se serializa tras el lock del store.

## Carga pequeña y recuperación

| Medida | Valor |
|---|---|
| 10 ejecuciones seguidas del escenario de referencia (7 tareas, un `unittest` real cada una) | 10/10 completadas (100 %), 4,25 s; pico de heap Python 2,5 MB |
| Recuperación de 50 tareas huérfanas tras un crash simulado | COMPLETED; 50 reconciliaciones; 0,83 s |

## Objetivos para v0.5.0 (fijados sobre esta medición)

1. Sobrecarga del scheduler por debajo de 3 ms/tarea con 4 workers, agrupando escrituras de transición y evento en una sola transacción. Hoy es ~9 ms.
2. Escritura de memoria por debajo de 0,3 ms/registro en lotes (`put_records`), con la misma garantía de checksum.
3. Búsqueda en memoria con FTS5 (disponible: SQLite 3.53) por debajo de 5 ms en p95 sobre 10 000 registros, con respaldo LIKE si FTS5 no existe.
4. Mantener la planificación por debajo de 100 ms en p95 y el router por debajo de 5 ms en p95.
