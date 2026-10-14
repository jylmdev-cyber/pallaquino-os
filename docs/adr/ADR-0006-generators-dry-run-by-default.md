# ADR-0006: Generadores en modo simulación por defecto

- Status: accepted (2026-10-13, PAL-005)
- Confidence: high
- Context: `scaffold_framework.py` y `expand_catalog.py` sobrescriben 163 y 120
  archivos sin confirmación y se distribuyen dentro de cada proyecto. En esta misma
  sesión una ejecución accidental revirtió el estado de continuidad (recuperado con Git).
- Options: (a) eliminarlos — pierde la regeneración declarativa; (b) prompt
  interactivo — inutilizable por agentes; (c) dry-run por defecto y `--write` explícito.
- Decision: (c), alineado con la distinción análisis / simulación / ejecución del
  pedido v0.3 y con `DESTRUCTIVE_ACTION_POLICY.md`.
- Consequences: quien regeneraba el catálogo debe añadir `--write`.
- Reversal: `WRITE = True` por defecto.
