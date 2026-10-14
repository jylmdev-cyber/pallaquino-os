# ADR-0008: Contratos v2 de agentes y skills

- Status: accepted (2026-10-14, PAL-007-A)
- Confidence: high para el esquema y la validación; medium para el contenido derivado
- Context: cada agente y skill era una plantilla Markdown cuyo único contenido propio
  es una frase. El registro no declaraba entradas, salidas, herramientas autorizadas,
  condiciones de activación, criterios de éxito ni casos de prueba, y nada impedía
  cargar un `.md` modificado. El análisis mostró además que 20 de 59 agentes y 9 de 90
  skills no pueden seleccionarse nunca y que 42 agentes no tienen ningún caso de prueba.
- Options: (a) redactar a mano 149 contratos — lento y vuelve a producir texto sin
  verificar; (b) JSON Schema con dependencia externa — rompe "solo stdlib";
  (c) contratos derivados de hechos del registro, validados con stdlib, con los campos
  redactados marcados como `derived` hasta que alguien los cure.
- Decision: (c). `registry/agent_contracts.json` y `registry/skill_contracts.json`
  (`contract_version: 2`) se generan con `scripts/build_contracts.py` (dry-run salvo
  `--write`). Se derivan de hechos: activación (reglas de routing, perfiles, domain
  packs, cobertura tecnológica, agentes que requieren la skill), casos de prueba
  (goldens que exigen el elemento), dependencias, versión, capacidades y
  `source_digest` (SHA-256 del `.md`). Las herramientas siguen denegación por defecto
  en cuatro niveles (`read`, `execute`, `network`, `write`) más `governed`, que solo
  puede figurar en `approval_required` y solo en agentes autorizados (`can_deploy`,
  categoría `release`, escritores de `data`); ningún agente recibe `secrets_access`.
  Entradas, salidas y criterios de éxito salen de plantillas por categoría y llevan
  `curation: "derived"`; al regenerar se conservan los campos de contratos `curated`.
- Consequences: `validate_contracts` (integridad) falla ante deriva entre registro y
  contrato, referencias rotas, herramientas no autorizadas o un `.md` modificado.
  `load_contract` rechaza fuentes alteradas y entradas deprecadas. `pallaquino
  contracts` informa elementos inalcanzables y sin pruebas. Editar un `.md` exige
  regenerar y revisar los contratos.
- Reversal: eliminar los dos archivos de contratos y `validate_contracts` de
  `VALIDATORS`; el registro v1 no cambia.
