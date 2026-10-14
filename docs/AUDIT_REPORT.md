# Informe de auditoría — PALLAQUINO 0.2.1 → 0.3.0

- Tarea: `PAL-005` (Fase 1: auditoría y estabilización del pedido `prompt-v03`)
- Fecha: 2026-10-13
- Base auditada: `8264eee` (rama `main`, versión 0.2.1)
- Entorno: Windows 11, Python 3.11.15, Git Bash; sin identidad Git local configurada
- Método: lectura completa del CLI y scripts, ejecución de la suite y de cada
  validador, sondas reproducibles sobre clasificadores, empaquetado e instalación.

Cada hallazgo cita la evidencia que lo reproduce. "CORREGIDO" significa que existe
un test de regresión que falla con el comportamiento 0.2.1 y pasa con 0.3.0.

## 1. Resumen

| Severidad | Total | Corregidos | Abiertos |
|---|---:|---:|---:|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 7 | 7 | 0 |
| MEDIUM | 9 | 7 | 2 |
| LOW | 4 | 2 | 2 |

No se encontraron secretos comprometidos ni vulnerabilidades explotables de forma
remota. Los HIGH afectan integridad (estado cruzado entre proyectos, generadores
destructivos), confiabilidad (CI y tests dependientes del reloj y del host) y
veracidad de las capacidades declaradas.

## 2. Verificación de capacidades declaradas

| Declaración (README 0.2.1) | Verificado | Observación |
|---|---|---|
| 59 agentes, 90 skills | Sí (conteo y rutas) | Cada archivo es una plantilla; el contenido único es una frase (misión o guía). Ver M-6. |
| 46 tecnologías, 6 perfiles | Sí | Todas `VERIFY_BEFORE_USE` salvo 11 del baseline. |
| CLI Python 3.11+ solo stdlib | Sí | Sin dependencias de runtime. |
| "tests: 18 passing" | **No en un clon limpio** | 15/18; ver H-1 y H-2. |
| "Security/fitness rules: 4 checked" (`TEST_STATUS.md`) | **No** | Solo 1 de 4 reglas tiene implementación. Ver H-5. |
| Pipelines, riesgos, checkpoints, handoffs | Parcial | Existen como datos y validadores; no hay motor que ejecute el pipeline. El handoff se generaba con contenido fijo. Ver M-4. |
| Empaquetado reproducible | **No** | Mismo contenido, distinto SHA-256. Ver H-6. |
| Compatibilidad multi-proveedor | Conceptual | No existe código de adaptadores de proveedor (planificado, Fase 2). |

## 3. Métricas de baseline y resultado

| Métrica | 0.2.1 (baseline) | 0.3.0 | Comando |
|---|---:|---:|---|
| Tests en clon sin identidad Git | 15/18 | 47/47 | `python -m unittest discover -s tests` |
| Duración de la suite | 6.5 s | 6–10 s (+29 tests) | ídem |
| Cobertura de sentencias `core.py` (in-process) | 88.5 % (355) | 92.1 % (509) | `trace` + `ast` stdlib (ver §6) |
| Cobertura `__main__.py` (in-process) | 0 % | 86.4 % | ídem |
| `validate_cli` | 1.68 s (15 procesos) | 0.14 s (1 proceso) | `time` en `core.VALIDATORS` |
| Reglas de fitness ejecutadas / declaradas | 1/4 (se reportaba 4) | 1/4 (se reporta 1 + 3 `not_enforced`) | `python scripts/architecture_fitness.py` |
| Falsos positivos de riesgo (casos dorados) | 3/5 | 0/5 | `evaluation/risk_golden.json` |
| SHA-256 estable entre builds del mismo contenido | No | Sí | `ArchiveReproducibilityTests` |

## 4. Hallazgos

### HIGH

**H-1 — CI con bomba de tiempo.** `test_stack_snapshot_is_current` fallaba en cuanto
el snapshot superaba 30 días (desde 2026-09-30). El último CI verde en `main` es del
2026-09-07; el siguiente push habría fallado sin ningún cambio de código.
Evidencia: `gh run list` y el fallo `age_days: 43, status: STALE`.
Archivos: `tests/test_core.py`, `pallaquino_cli/core.py::stack_status`.
Corrección: `stack_status(root, today=...)` es determinista; el test valida la
lógica de caducidad con fechas explícitas. `doctor` y `stack` siguen informando la
caducidad real (exit 1). **CORREGIDO.**

**H-2 — Suite acoplada a la identidad Git del mantenedor.** `test_all_validators_pass`
y `test_validate_json` fallan en cualquier clon sin `user.name=jimdev`, mientras
`CONTRIBUTING.md` pide a cada colaborador configurar *su propia* identidad.
Corrección: cada check se etiqueta `scope: integrity | environment`;
`validate --integrity-only` y `validate_all(include_environment=False)` excluyen los
checks del host. El check de autoría se prueba con un repositorio Git aislado. CI
sigue ejecutando la validación completa. **CORREGIDO** (la contradicción de política
queda como pregunta abierta Q-1).

**H-3 — `init` filtraba el estado de otro proyecto.** `init` copiaba la tarea
`PAL-004`, 5 checkpoints, 10 evidencias, `HANDOFF.json`, el grafo de tareas y rutas
absolutas de otra máquina. Un proyecto nuevo ejecutaba `resume` → `RECOVERED PAL-004`.
Evidencia: `pallaquino init --target <tmp>` + `resume --root <tmp>/.pallaquino`.
Corrección: `manifest.json#instance_state` declara el estado por proyecto; `init`
lo excluye y genera estado limpio; nuevo `--dry-run`. **CORREGIDO.**

**H-4 — Instalación no editable inutilizable.** Con `pip install .` el root por
defecto era `site-packages`; todos los comandos fallaban con `Errno 2`.
Corrección: resolución `--root` → `$PALLAQUINO_ROOT` → checkout del paquete →
`./.pallaquino` o directorio padre; error accionable con exit 2. CI añade un smoke
test de instalación no editable. **CORREGIDO.**

**H-5 — Capacidad de seguridad sobredeclarada.** `architecture_fitness.py` reportaba
`"rules": 4` pero solo ejecutaba una expresión regular de secretos.
Corrección: el reporte separa `enforced` y `not_enforced`; el escáner de secretos
reconoce claves privadas, AWS, GitHub, claves LLM, Google, Slack, JWT y asignaciones
de credenciales, sin incluir nunca el valor en la salida. **CORREGIDO.**

**H-6 — Archivo de release no reproducible.** El ZIP dependía de los `mtime` del
checkout: el mismo contenido producía hashes distintos, y el SHA publicado no podía
reconstruirse desde un clon. Además, `atomic_json` escribía CRLF en Windows.
Corrección: timestamps fijos (o `SOURCE_DATE_EPOCH`), permisos normalizados
(`0644`/`0755` por shebang) y escritura LF en todos los writers. **CORREGIDO.**

**H-7 — Generadores destructivos sin confirmación.** `scaffold_framework.py`
sobrescribe 163 archivos (políticas, registros y estado de continuidad) y
`expand_catalog.py` 120, sin confirmación; `init` los copia a cada proyecto.
**Reproducido durante esta misma sesión**: una ejecución accidental revirtió el
estado de continuidad y el grafo de tareas; se recuperó desde Git (`git checkout
HEAD -- <rutas>`) verificando que el código propio quedara intacto.
Corrección: ambos son dry-run por defecto y requieren `--write`. **CORREGIDO.**

### MEDIUM

- **M-1 — Clasificadores por subcadena.** `"prod"` coincidía con *product*/*reproduce*,
  `"auth"` con *authors*, `"rag"` con *storage*, `"pos"` con *compose*. Corrección:
  coincidencia por token con plural opcional; goldens nuevos. **CORREGIDO.**
- **M-2 — Locks sin TTL ni exclusión mutua.** `ttl_minutes` nunca se aplicaba,
  `release_lock` aceptaba rutas fuera del root, la lectura-modificación-escritura no
  era atómica entre procesos y las claves guardaban rutas absolutas del host.
  Corrección: expiración auditada, mutex `O_EXCL`, claves relativas y migración de
  claves heredadas. **CORREGIDO.**
- **M-3 — Evidencia sin redacción.** `evidence.py` persistía 4000 caracteres de
  salida y el comando sin filtrar. Corrección: `redact()` antes de persistir. **CORREGIDO.**
- **M-4 — Handoff con contenido fijo.** `missing: []` y `unverified: []` se escribían
  siempre, afirmando implícitamente que no faltaba nada. Corrección: se deriva del
  estado registrado; lo no registrado se marca `NOT_RECORDED`. **CORREGIDO.**
- **M-5 — El grafo de tareas aceptaba agentes/skills inexistentes.** **CORREGIDO.**
- **M-6 — Agentes y skills sin contrato operativo.** Faltan entradas/salidas,
  herramientas autorizadas, condiciones de activación, criterios de éxito y casos de
  prueba por agente. **PARCIAL**: contratos v2 implementados (ADR-0008, PAL-007-A) con contenido
  derivado; la curación y la alcanzabilidad de 20 agentes y 9 skills siguen abiertas (PAL-007-B).
- **M-7 — Snapshot tecnológico caducado** (verificado 2026-08-31, caducó 2026-09-30).
  Requiere verificación contra fuentes oficiales en modo `UPGRADE`. **ABIERTO** (`PAL-006`).
- **M-8 — Salida no JSON en modo humano.** `agents`/`skills` imprimían `repr` de
  Python. Corrección: tabla `id<TAB>category`; `--json` sin cambios. **CORREGIDO.**
- **M-9 — El recorrido de archivos divergía de `.gitignore`** (hallado durante la
  implementación). `build/`, `*.egg-info` y `.env.*` entraban en el ZIP, `init` y el
  escaneo tras un `pip install .`; además, las exclusiones se evaluaban sobre la ruta
  *absoluta*, de modo que un proyecto bajo una carpeta `build/` o `dist/` quedaba
  vacío. Corrección: exclusiones relativas alineadas con `.gitignore`. **CORREGIDO.**

### LOW

- **L-1 — Rutas absolutas del host en estado versionado** (`runtime/capabilities.json`
  contiene `D:\codex\...`, `C:\Users\jimdev-pc\...`). Ya no se copian a proyectos
  nuevos; el archivo del framework se conserva. **ABIERTO.**
- **L-2 — Binario de release versionado en Git** (aumenta el repositorio en cada
  release). Recomendado: publicarlo solo como asset de GitHub Release. **ABIERTO.**
- **L-3 — `validate_cli` lanzaba 15 subprocesos.** **CORREGIDO** (1 proceso, 12× más rápido).
- **L-4 — Lista de comandos de ayuda desactualizada en documentación.** **CORREGIDO.**

## 5. Decisiones del propietario (2026-10-13)

- **Q-1 — RESUELTA.** Se mantiene `jimdev <jylmdev@gmail.com>` como identidad de este
  repositorio y por defecto, y pasa a ser configurable por proyecto en
  `governance/git_identity.json` (`pallaquino identity`). Ver ADR-0007.
- **Q-2 — RESUELTA.** Se mantiene la prohibición de trailers de coautoría de IA.
- **Q-3 — APROBADA.** Publicar la rama, abrir el Pull Request y publicar el tag `v0.3.0`.

## 6. Reproducción

```bash
cd universal_ai_fullstack_orchestrator
python -m unittest discover -s tests -v
python -m pallaquino_cli validate --integrity-only --json
python scripts/architecture_fitness.py
python -m pallaquino_cli security audit --target .. --json
python -m pallaquino_cli risk "update product documentation" --json
python -m pallaquino_cli init --target /tmp/demo --dry-run --json
```

La cobertura se midió con un script auxiliar no versionado que ejecuta la suite bajo
`trace.Trace(count=1)` y cuenta sentencias con `ast`; los tests CLI por subproceso no
se cuentan, por eso `__main__.py` también tiene tests en proceso.
