# Guía de migración

## 0.5.0 → 0.5.1

Versión de corrección, sin cambios de comandos, contratos, esquemas ni memoria. No requiere acciones.

- Si en Windows usas una identidad de commits con tildes o eñes y `identity --apply-local` devolvía `"matches": false`, vuelve a
  ejecutar `pallaquino identity --apply-local --json`: ahora devuelve `"matches": true`.
- Para actualizar un proyecto ya inicializado, sustituye el paquete `pallaquino_cli` de su `.pallaquino/` por el de 0.5.1, o reinstala
  el paquete si lo instalaste con pip.

## 0.4.0 → 0.5.0

0.5.0 es aditiva. Los comandos, contratos v1 y planes de 0.4.0 siguen funcionando, y el núcleo funciona sin plugins ni conexiones MCP.

| Área | Cambio | Acción |
|---|---|---|
| Comandos nuevos | `plugins`, `plugin`, `mcp`, `tools`, `permissions` | ninguna |
| Códigos de salida | `tools run` puede devolver 3 (aprobación pendiente) y 5 (denegado); `PermissionError` de cualquier comando da 5 | revisa scripts que trataban todo lo distinto de 0 como 1 |
| Store | migración 3 (`platform_docs`, `tool_calls`), aplicada automáticamente al abrir | ninguna; haz copia de `memory/` si quieres poder volver a 0.4.0 con historial |
| Estado de instancia | `plugins/` y `governance/plugin_trust.json` son por proyecto | si versionas `.pallaquino/`, añádelos a `.gitignore` |
| Configuración nueva | `governance/integrations.json` (GitHub deshabilitado) y `governance/TOOL_AND_EXTENSION_POLICY.md` | en instalaciones existentes, cópialos desde el framework |
| Planes | las solicitudes de descubrimiento que mencionan Git, calidad o informe añaden pasos `git_inspect`, `quality_scan` y `report`, ejecutados con herramientas reales en lugar del paso simulado `explore` | ninguna; las demás solicitudes producen el mismo plan que en 0.4.0 |
| Ejecutor | nuevo tipo `tool` en `EXECUTOR_KINDS` | ninguna |
| Empaquetado | subpaquetes `pallaquino_cli.tools`, `.mcp`, `.extensions`, `.integrations` y `.sdk` | reinstala el paquete (`pip install -e .`) |
| Raíz | con una instalación editable, la raíz por defecto sigue siendo el checkout del paquete (ADR-0004) | en proyectos, usa `--root .pallaquino` o `PALLAQUINO_ROOT` |

Rollback: vuelve a `v0.4.0`. Un store migrado a la versión 3 sigue abriéndose con 0.4.0, porque las tablas nuevas se ignoran.

## 0.3.x → 0.4.0

0.4.0 es aditiva: los comandos y formatos JSON de 0.3 siguen iguales. `plan`, `status`, `resume`, `agents` y `skills` sin argumentos nuevos
devuelven lo mismo que antes.

| Área | Cambio | Acción |
|---|---|---|
| Comandos nuevos | `plan "<solicitud>"`, `run`, `status/resume --execution`, `pause`, `cancel`, `approve`, `agents match`, `memory`, `providers`, `executions` | ninguna |
| Estado de ejecución | `memory/pallaquino.db` y `logs/` dentro de `.pallaquino/`; son estado de instancia (Git, `init` y el ZIP los excluyen) | si versionas `.pallaquino/`, añade `memory/` y `logs/` a tu `.gitignore` |
| Configuración nueva | `governance/providers.json` (mock por defecto, Ollama deshabilitado, `privacy.local_only: true`), `governance/command_allowlist.json` y `governance/routing_preferences.json` | `init` los copia a proyectos nuevos; en instalaciones existentes, cópialos desde el framework |
| Contratos v2 | `registry/agent_contracts.json` y `registry/skill_contracts.json` son obligatorios (`validate_contracts`) | instalaciones existentes: copia los dos archivos o ejecuta `python scripts/build_contracts.py --write` |
| Pipeline | las etapas pueden declarar `agents` (roles por etapa) | ninguna |
| Generadores | `scaffold_framework.py` y `expand_catalog.py` con `--write` solo crean archivos ausentes; `--overwrite` reemplaza | añade `--overwrite` si regenerabas registros a propósito |
| Empaquetado | subpaquetes `pallaquino_cli.orchestration`, `.memory` y `.providers` | reinstala el paquete (`pip install -e .` o `pip install .`) |

Simulación: sin un proveedor real, las tareas de agente las responde `mock` y quedan marcadas `simulated: true`. Los informes muestran
qué etapas fueron reales.

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
