# PALLAQUINO Agent Routing Engine

Estado: **IMPLEMENTADO** (`pallaquino_cli/orchestration/routing.py`). Usa los contratos v2 (ADR-0008) y el registro real; nunca inventa agentes.

## Puntuación (0–100, reproducible)

| Componente | Peso | Fuente |
|---|---:|---|
| Cobertura de capacidades | 40 | `agents.json#capabilities` ∩ capacidades requeridas |
| Dominio | 25 | `agents.json#domains` ∩ dominios de la tarea o de la solicitud |
| Tecnología | 15 | `activation.technologies` del contrato (vía `agent_skill_coverage.json`; los agentes no declaran tecnologías propias) |
| Señal de routing | 10 | el agente aparece en una regla de `routing_rules.json` que coincide con la solicitud |
| Preferencia del proyecto | +5 | `governance/routing_preferences.json#prefer` |
| Coste de contexto | −`context_weight` | hoy todos los agentes pesan 3: el término es uniforme |
| Historial | ±5 | solo con ≥5 ejecuciones verificadas y no simuladas; si no, "insufficient verified history" y no puntúa |

**Filtros duros** (con motivo en `rejected`): agente deprecado, sin contrato, excluido por el proyecto, `risk_limit` menor que el riesgo de la tarea, skills requeridos inexistentes o deprecados.

## Selección

Las capacidades se cubren una a una, en orden fijo. Si un agente ya elegido tiene la capacidad, la cubre él. Si no, gana, en este orden:

1. el candidato cuyos dominios coinciden con los de la tarea o con la pista de la capacidad (`design`→arquitectura, `schema`→base de datos…);
2. el que tiene menos dominios especialistas ajenos (un especialista móvil o ERP no gana trabajo genérico);
3. la mayor puntuación;
4. el ID menor.

El tamaño del conjunto depende del alcance: 1 agente en tareas simples, hasta 3 en tareas relacionadas y hasta 6 en tareas complejas.
Los candidatos descartados se informan como `redundant`.

**Capacidades sin cubrir**: se listan en `missing_capabilities`, con `fallback` (alternativas parciales, sugerencia de descomposición y aviso de
que añadir una capacidad requiere una ampliación aprobada del registro). El planificador marca esas tareas como error de validación.

## Roles del pipeline

Los pasos con etapa (`discover`→REPOSITORY_ANALYSIS, `code_review`→CODE_REVIEW, `docs`→DOCUMENTATION) se asignan al rol declarado en
`pipeline_definition.json` (ADR-0009), no al router.

## Comprobado por tests

- Dominios que separan a `backend_engineer` de `frontend_engineer`, que tienen capacidades idénticas.
- Reproducibilidad, filtros de riesgo y de exclusión.
- Capacidad inexistente reportada en lugar de inventada.
- El historial simulado nunca puntúa.
