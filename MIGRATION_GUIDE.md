# Guía de migración

## 0.2.1 → 0.3.0

0.3.0 es compatible hacia atrás en comandos, flags y formatos JSON existentes. Los
cambios de comportamiento son correcciones; revisa esta lista antes de actualizar.

### Cambios de comportamiento

| Área | 0.2.1 | 0.3.0 | Acción |
|---|---|---|---|
| Clasificación de riesgo | Subcadenas (`product` → HIGH) | Tokens completos con plural | Algunas solicitudes bajan de nivel. Si dependías de una raíz (p. ej. `auth`), añade el término completo a `registry/routing_rules.json`. |
| `init` | Copiaba estado, checkpoints y evidencia del framework | Genera estado limpio; nuevo `--dry-run` | Ninguna para proyectos nuevos. Para proyectos existentes, ver abajo. |
| Root por defecto | Siempre el checkout del paquete | `--root` → `$PALLAQUINO_ROOT` → checkout → `./.pallaquino` o un padre | Ninguna en instalaciones editables. `pip install .` ahora funciona dentro de un proyecto inicializado. |
| Root inválido | Error `Errno 2`, exit 1 | Mensaje accionable, **exit 2** | Ajusta scripts que comprueben exit 1 para este caso. |
| `validate` | Todos los checks | Igual; cada check incluye `scope`. `--integrity-only` omite los de entorno | Ninguna. |
| `agents`/`skills` sin `--json` | `repr` de Python | Tabla `id<TAB>category` | Usa `--json` para automatización (sin cambios). |
| `handoff` | `missing`/`unverified` siempre `[]` | Derivado del estado; `NOT_RECORDED` si falta; `--next-action`, `--missing`, `--unverified` | Pasa los valores reales al generar un handoff. |
| `scripts/scaffold_framework.py`, `scripts/expand_catalog.py` | Escribían siempre | Dry-run; requieren `--write` | Añade `--write` tras revisar la lista de archivos. |
| `scripts/architecture_fitness.py` | `rules: 4` | Además `enforced` y `not_enforced` | Lee `enforced` para saber qué se comprobó realmente. |
| `scripts/evidence.py` | Guardaba salida sin filtrar | Redacta secretos en comando y salida | Ninguna. |
| `execution/file_locks.json` | Claves absolutas; TTL ignorado | Claves relativas; los locks expiran | Las claves antiguas se migran al primer acceso. |
| ZIP de release | SHA dependiente de `mtime` | Determinista | El SHA de 0.3.0 no es comparable con el de 0.2.1. |

### Proyectos ya inicializados con 0.2.1

`init` nunca sobrescribe archivos, así que una instalación existente conserva el
estado heredado del framework (tarea `PAL-004`, checkpoints de 2026-09-01). Para
comprobarlo:

```bash
python -m pallaquino_cli resume --root .pallaquino --json
```

Si devuelve `"task": "PAL-004"`, ese estado no pertenece a tu proyecto. Limpieza
recomendada (revisa antes de borrar; Git conserva todo si `.pallaquino/` está versionado):

```bash
# 1. Simula una instalación limpia en un directorio temporal para obtener el estado nuevo
python -m pallaquino_cli init --target /tmp/pallaquino-clean --json

# 2. Revisa qué archivos de estado heredado tiene tu instalación
ls .pallaquino/continuity/checkpoints .pallaquino/evidence .pallaquino/changes

# 3. Tras revisarlos, reemplaza solo los patrones listados en manifest.json#instance_state
#    copiando sus equivalentes desde /tmp/pallaquino-clean/.pallaquino
```

PALLAQUINO no automatiza este borrado: es una acción destructiva sujeta a
`governance/DESTRUCTIVE_ACTION_POLICY.md`.

### Identidad de commit

La identidad esperada ya no está fija en el código: se lee de
`governance/git_identity.json` y, si no existe, sigue siendo `jimdev <jylmdev@gmail.com>`.
En un proyecto propio, define la tuya y aplícala solo a la configuración local:

```bash
python -m pallaquino_cli identity --name "Tu Nombre" --email "tu@example.com" --root .pallaquino
python -m pallaquino_cli identity --apply-local --root .pallaquino
```

### Contribuidores de este repositorio

La identidad del repositorio sigue siendo jimdev. Si tu identidad local es otra, usa
`python -m pallaquino_cli validate --integrity-only`; CI ejecuta la validación completa.
No modifiques `governance/git_identity.json` en un Pull Request.
