# ADR-0003: Estado por proyecto declarado en el manifiesto

- Status: accepted (2026-10-13, PAL-005)
- Confidence: high
- Context: `init` copiaba la continuidad, evidencia y checkpoints del propio framework
  a cada proyecto; `resume` en un proyecto nuevo recuperaba la tarea de otro. Esto
  viola el aislamiento de contexto entre proyectos.
- Options: (a) excluir por lista fija en código; (b) mover el estado a otro árbol —
  rompe rutas documentadas; (c) declarar patrones en `manifest.json#instance_state`
  y generar estado limpio.
- Decision: (c), con valor por defecto en `core.DEFAULT_INSTANCE_STATE`. Los archivos
  existentes nunca se sobrescriben. `--dry-run` informa sin escribir.
- Consequences: instalaciones existentes no se modifican; limpiarlas es un paso
  manual documentado en MIGRATION_GUIDE. La futura Project Memory usará la misma lista.
- Reversal: eliminar el filtrado en `init_target`.
