# ADR-0009: Roles por etapa del pipeline y generadores que solo crean

- Status: accepted (2026-10-14, PAL-007-B)
- Confidence: high
- Context: el informe de contratos (ADR-0008) mostró 20 agentes y 9 skills que nada
  podía seleccionar. Trece de esos agentes solo dependían del skill genérico
  `risk_analysis_expert`, mientras sus especialidades (`release_management_expert`,
  `dependency_governance_expert`, `saas_tenancy_expert`…) existían sin conectar. Varios
  son roles del propio pipeline (`project_analyzer`, `risk_analyst`,
  `execution_coordinator`…) que no deben activarse por palabras de la solicitud.
  Además, `scaffold_framework.py` y `expand_catalog.py` reescribían los registros
  completos con sus copias embebidas, revirtiendo cualquier curación.
- Options: (a) reglas de routing para todos — activaría roles de pipeline por
  coincidencias léxicas; (b) roles declarados por etapa en
  `pipeline_definition.json` más reglas de routing solo para especialistas que dependen
  de la solicitud; (c) eliminar los agentes huérfanos — pierde capacidad sin migración.
- Decision: (b). Las etapas pueden declarar `agents` (validado por
  `validate_pipeline`); los contratos registran `pipeline_stages` como fuente de
  activación y `evaluation/pipeline_stages/golden.json` como casos de prueba. Diez
  reglas nuevas cubren release, dependencias, gobierno de APIs, CI/CD, recuperación ante
  desastres, rendimiento, documentación, SaaS multi-tenant, ingeniería de IA y
  decisiones de arquitectura, cada una con goldens positivos y negativos. Los skills
  especializados se conectan a sus agentes (versión menor +1). Los generadores, con
  `--write`, solo crean archivos ausentes; reemplazar existentes exige `--overwrite`.
- Consequences: 0 agentes y 0 skills inalcanzables; agentes sin caso de prueba
  42 → 19 y skills 67 → 52. Trece contratos de rol quedan curados a mano. Regenerar con
  `--overwrite` sigue siendo posible pero es destructivo por diseño.
- Reversal: quitar el campo `agents` de las etapas y las diez reglas; restaurar el
  comportamiento de escritura previo de los generadores.
