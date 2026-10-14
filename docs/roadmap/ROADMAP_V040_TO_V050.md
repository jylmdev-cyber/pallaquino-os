# Roadmap v0.4.0 → v0.5.0

Parte de lo medido en [BENCHMARK_RESULTS.md](../evaluation/BENCHMARK_RESULTS.md) y de los límites declarados en la documentación de arquitectura.

## Deuda técnica de v0.4.0

| Deuda | Impacto | Propuesta |
|---|---|---|
| Una transacción por transición y por evento | ~9 ms de sobrecarga por tarea; el scheduler no escala más allá de 4 workers | agrupar transición, tarea y evento en una sola transacción; objetivo < 3 ms/tarea |
| Búsqueda en memoria por palabras clave con LIKE | 13 ms de mediana sobre 1000 registros; lineal | índice FTS5 con respaldo LIKE; objetivo p95 < 5 ms sobre 10 000 registros |
| Checksums sin clave | quien escribe la base puede recalcularlos | HMAC con clave por proyecto fuera de la base, o cadena de hashes de eventos |
| Hilos que exceden el timeout no se pueden detener | su efecto puede ocurrir después del timeout (at-least-once) | ejecutar agentes y comandos en subprocesos con terminación forzada |
| Comandos permitidos con permisos del usuario | sin aislamiento | ejecución opcional en contenedor o worktree aislado por tarea, solo donde haya un entorno verificado |
| Herramientas gobernadas sin ejecutor | `deploy` o `release_publish` aprobados solo se delegan al agente | ejecutores explícitos con dry-run, plan y aprobación por objetivo |
| `npm test` y otros lanzadores `.cmd` en Windows | sin shell, `npm` no se resuelve y el ejecutor informa `not_configured` | resolver con `shutil.which` y ejecutar el `.cmd` explícitamente |
| Planificación basada en plantillas | dominios fuera de las 24 plantillas generan planes genéricos | plantillas por perfil de stack y planificación asistida por IA validada contra el mismo contrato |
| 46 agentes y 90 skills con contenido derivado | prompts de agente genéricos | curación progresiva priorizando los agentes más usados por el router |

## Funcionalidades para v0.5.0 (Extensibilidad, Fase 3)

1. **Ejecutor externo**: tareas que un agente activo, por ejemplo un asistente de código, toma con `pallaquino tasks claim` y entrega con
   `pallaquino tasks submit <json>`, validadas con el mismo contrato de resultado. Es la vía provider-neutral para usar PALLAQUINO con
   cualquier asistente sin API.
2. **Extension System**: manifiesto validado, versión y compatibilidad, permisos por herramienta, procedencia por hash y activar/desactivar.
   Ningún código de plugin se ejecuta sin una política de confianza.
3. **Adaptadores comerciales verificados** (Anthropic, OpenAI, Gemini), cada uno con pruebas de integración opcionales que exijan
   credenciales y nunca corran en CI por defecto. Precio por token configurable para estimar coste antes de ejecutar.
4. **MCP**: integración con servidores autorizados, distinguiendo autenticación STDIO y HTTP según la especificación vigente.
5. **Exportador OpenTelemetry opcional** sobre el JSONL actual.

## Criterios de aceptación de v0.5.0

- Los objetivos 1 a 4 de BENCHMARK_RESULTS.md, medidos en el mismo equipo.
- Un plugin sin política de confianza no se ejecuta (test adversarial).
- El escenario de referencia pasa con al menos un proveedor real autorizado, y se registra qué etapas fueron reales.
- Compatibilidad: los comandos y contratos v1 de 0.4.0 siguen válidos.
