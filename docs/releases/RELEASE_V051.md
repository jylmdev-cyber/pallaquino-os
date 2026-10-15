# PALLAQUINO 0.5.1

Fecha: 2026-10-14. Versión de corrección sobre 0.5.0, compatible: no cambian comandos, contratos, esquemas ni la memoria.

## Corrección

- **Identidad Git no ASCII en Windows (H-6).** `identity --apply-local` con un nombre como `Ana Pérez` aplicaba la identidad, pero la
  comparación devolvía `"matches": false`. Además, `validate_git_authorship` fallaba siempre.
  - Causa: `core.run_git` y `scripts/configure_git_identity.py` decodificaban la salida UTF-8 de Git con la página de códigos local.
  - Ahora la leen como UTF-8. El test de regresión `tests/test_git_identity.py::test_non_ascii_identity_round_trips` falla sin la
    corrección.

## Incluido también

- **PALLAQUINO Academy**, un portal educativo estático publicado en https://jylmdev-cyber.github.io/pallaquino-os/. Detalles en
  ADR-0017 y `docs/learning/`. No forma parte del ZIP del framework.
- `CITATION.cff`, la checklist de release y el README del framework actualizados (se habían quedado en 0.4.0).

## Verificación

- 243 tests del framework, la demo end-to-end, la integridad del ZIP reproducible y la CI en Linux (Python 3.11 y 3.14).
- La evidencia está en `universal_ai_fullstack_orchestrator/evidence/` y el registro en `releases/0.5.1.json`.

## Migración

Ninguna. Ver `MIGRATION_GUIDE.md` (0.5.0 → 0.5.1).
