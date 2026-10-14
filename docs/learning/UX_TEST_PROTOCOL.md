# Protocolo de pruebas con usuarios

> **Estado:** preparado, **no ejecutado**. No existen resultados de pruebas con usuarios. Este documento no debe citarse como evidencia de
> usabilidad hasta que haya sesiones registradas.

## Objetivo

Comprobar que una persona que programa pero no conoce PALLAQUINO puede:

1. explicar qué es PALLAQUINO después de la ruta 1;
2. completar el tutorial de primera instalación en su equipo sin ayuda;
3. encontrar en la referencia las opciones de un comando;
4. superar la evaluación de la ruta 3.

## Participantes

Entre 5 y 8 personas: al menos 2 que usen Windows, 2 con Linux o macOS, y 1 que use lector de pantalla o solo teclado.

## Tareas y métricas

| Tarea | Éxito | Métricas |
|---|---|---|
| Instalar con el tutorial | `validate --integrity-only --json` devuelve `"ok": true` en su equipo | Tiempo, pasos con dudas, errores encontrados |
| Encontrar las opciones de `memory purge` | Encuentra `--expired`, `--older-than` y `--yes` | Tiempo, camino seguido (búsqueda o navegación) |
| Completar el reto guiado de la terminal | Reto completado | Pasos con «Ver comando» |
| Evaluación de la ruta 3 | 70 % o más | Puntuación al primer intento |
| Navegar solo con teclado por una lección y su evaluación | Completa la evaluación | Puntos donde se pierde el foco |

## Registro

Por cada sesión: fecha, sistema operativo, navegador, tecnología de apoyo, resultado de cada tarea, citas literales (con permiso) y
problemas observados con su severidad. No se graban datos personales sin consentimiento escrito.

## Después

Los hallazgos se convierten en Issues con la etiqueta `academy`. Los cambios aplicados se registran en el CHANGELOG.
