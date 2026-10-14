# ADR-0002: Coincidencia por token en los clasificadores de riesgo y routing

- Status: accepted (2026-10-13, PAL-005)
- Confidence: high
- Context: la coincidencia por subcadena elevaba a HIGH "update product
  documentation" (`prod`) y "fix typo in authors" (`auth`), y activaba la regla RAG
  con "storage". Un riesgo inflado exige gates innecesarios y erosiona la confianza.
- Options: (a) listas de exclusión — frágiles; (b) embeddings — dependencia externa,
  no determinista; (c) regex con límites de palabra y plural opcional (`s|es`).
- Decision: (c), con `re` de la stdlib y caché de patrones. Se añadió
  `authentication`/`autenticación` a la regla `django_auth` para conservar recall.
- Consequences: el riesgo puede bajar para solicitudes que antes eran falsos
  positivos (documentado en MIGRATION_GUIDE). Los términos con raíz deben listarse
  explícitamente. `evaluation/risk_golden.json` fija el comportamiento.
- Reversal: volver a `term in normalized` en `contains_term`.
