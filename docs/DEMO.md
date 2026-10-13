# Demostración reproducible (0.3.0)

Salidas observadas el 2026-10-13 en Windows 11 con Python 3.11.15, recortadas a los
campos relevantes. Las rutas absolutas se omiten.

## 1. Instalación y verificación

```bash
python -m pip install -e ./universal_ai_fullstack_orchestrator
cd universal_ai_fullstack_orchestrator
pallaquino --version                         # pallaquino 0.3.0
pallaquino validate --integrity-only --json  # {"ok": true, ...} con 9 checks
python -m unittest discover -s tests         # OK
```

## 2. Clasificación de riesgo por token completo

```bash
pallaquino risk "update product documentation" --json
# {"level": "LOW", "matched_factors": []}            (0.2.1: HIGH por "prod")

pallaquino risk "delete production database" --json
# {"level": "CRITICAL", "required_gates": ["ALL_TESTS", "SECURITY_AUDIT",
#   "MIGRATION_SAFETY", "ROLLBACK_READINESS", "HUMAN_APPROVAL"]}
```

## 3. Instalación aislada en un proyecto

```bash
pallaquino init --target ../app --dry-run --json
# {"copied": 0, "planned": 307, "excluded_source_state": 41, "dry_run": true}
# (no se escribe nada)

pallaquino init --target ../app --json
# {"copied": 307, "excluded_source_state": 41, ...}
```

`excluded_source_state` cuenta los archivos de estado del framework (tarea,
checkpoints, evidencia, grafo) que **no** se copian. El proyecto recibe estado limpio.

## 4. Continuidad dentro del proyecto

```bash
cd ../app                                # pallaquino descubre ./.pallaquino
pallaquino resume --json                 # {"status": "RECONSTRUCTED"}  (0.2.1: RECOVERED PAL-004)
pallaquino checkpoint --task DEMO-1 --json   # {"task": "DEMO-1", "stage": "REQUEST"}
pallaquino resume --json                 # {"status": "RECOVERED", "task": "DEMO-1"}
```

## 5. Auditoría de secretos

Con un `config.py` que contiene un token de GitHub de prueba:

```bash
pallaquino security audit --target . --json ; echo $?
# {"ok": false, "findings": [
#   {"path": "config.py", "line": 1, "kind": "github_token"},
#   {"path": "config.py", "line": 1, "kind": "credential_assignment"}]}
# 1
```

El valor del token no aparece en la salida (verificado con `grep`).

## 6. Errores accionables

```bash
pallaquino status --root ./nope ; echo $?
# pallaquino: .../nope is not a PALLAQUINO root (expected manifest.json and registry/)
# 2
```

## 7. Generadores protegidos

```bash
python scripts/scaffold_framework.py   # DRY RUN: 163 file(s) would be overwritten; ...
python scripts/expand_catalog.py       # DRY RUN: 120 file(s) would be overwritten; ...
```

Ambos requieren `--write` para escribir.

## 8. Release reproducible

```bash
python scripts/package_release.py
python scripts/verify_zip_integrity.py   # {"ok": true, "sidecar_ok": true, ...}
```

Dos builds del mismo contenido producen el mismo SHA-256
(`ArchiveReproducibilityTests` en `tests/test_stabilization.py`).
