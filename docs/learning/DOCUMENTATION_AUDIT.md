# Auditoría de documentación y aprendizaje (PAL-012)

- Fecha: 2026-10-14. Versión auditada: PALLAQUINO 0.5.0 (`main` d4a2af3).
- Entorno de verificación: Windows 11, Python 3.11.15, Git. Clon limpio del repositorio y proyectos de prueba en un directorio temporal.
- Método:
  - cada comando que enseña la academia se ejecutó o se capturó de un clon limpio (`academy/scripts/capture_transcripts.py`);
  - los datos de referencia se generan del código (`academy/scripts/generate_data.py`);
  - `academy/scripts/validate-content.mjs` comprueba los 133 comandos citados contra el analizador real de la CLI.
- Alcance: `README.md`, `universal_ai_fullstack_orchestrator/QUICK_START.md`, `AI_ENTRYPOINT.md`, `docs/` (tutoriales, arquitectura,
  seguridad, SDK) y `CONTRIBUTING.md`.

## 1. Matriz de funcionalidades

| Área | Documentación existente | Verificado en PAL-012 | Lecciones |
|---|---|---|---|
| Instalación y diagnóstico | README, QUICK_START | Sí: clon limpio, `doctor`, `validate`, `--integrity-only` | Ruta 2 |
| Instalación en un proyecto (`init`) | README, QUICK_START, DEMO | Sí: `init --dry-run` y `init` real en un repositorio nuevo | 2.4 |
| Identidad de commits | QUICK_START, ADR-0007 | Sí; defecto H-6 de 0.5.0, corregido en PAL-013 | 2.4 |
| Riesgo, análisis, auditoría de secretos | README, DEMO | Sí | Ruta 3 |
| Checkpoint, handoff, resume | DEMO, protocolos de continuidad | Sí, en un proyecto inicializado | 3.4, 6.3 |
| Agentes, skills, contratos, enrutamiento | AGENT_ROUTING, ADR-0008/0009 | Sí: `agents match`, `contracts --id` | Ruta 4 |
| Plan, run, approve, resume, executions | FIRST_MULTI_AGENT_EXECUTION, ORCHESTRATION_ENGINE | Sí: proyecto de ejemplo y flujo `WAITING_APPROVAL` → `approve` → `resume` | Ruta 5, 8.1 |
| Memoria | MEMORY_AND_RECOVERY, MEMORY_ENGINE | Sí: `status`, `search`, `inspect`, `verify`, rechazo sin `--yes` | Ruta 6 |
| Pasarela de herramientas y permisos | EXECUTE_TOOL_SAFELY, TOOL_PERMISSIONS | Sí: `tools check`, `list`, `grant` | 7.1, 7.2 |
| MCP | CONNECT_MCP_SERVER, MCP_CLIENT_ARCHITECTURE | Sí: `add`, `test`, `tools`, `pin`, `grant` | 7.3 |
| Plugins | CREATE_FIRST_PLUGIN, guía y referencia del SDK | Sí: ciclo completo hasta `COMPLETED` | 7.4 |
| Proveedores | PROVIDER_ABSTRACTION | Sí: `providers list` y `doctor` | 7.5 |
| Demo end-to-end | README | Sí: `run_codebase_analysis_demo.py`, 12/12 comprobaciones | 8.2 |
| Project Factory (0.6.0), Control Center (0.7.0) | ROADMAP | No aplica: planificado | Presentado como futuro |
| Proyectos Django / Nuxt de principio a fin | — | **No verificado**: sin tutoriales; solo una matriz honesta | 8.3 |

## 2. Hallazgos

| Id | Severidad | Hallazgo | Evidencia | Tratamiento |
|---|---|---|---|---|
| H-1 | Media | `doctor` y `validate --json` terminan con código 1 en un clon recién descargado. El único fallo es `validate_git_authorship` (entorno), y el inicio rápido del README no lo advierte. | Transcripciones `doctor` y `validate-json` | La academia lo explica y enseña `--integrity-only`. Propuesta: una línea en el README. |
| H-2 | Media | `init` copia `governance/git_identity.json` del mantenedor, así que el proyecto espera la identidad `jimdev`. QUICK_START lo menciona, pero el README no. | `init` + `identity --json` en un proyecto nuevo | Lección 2.4 con el procedimiento `identity --name/--email` y `--apply-local`. |
| H-3 | Baja | `analyze` reescribe `repository/REPOSITORY_MAP.json` y `.md`, que están versionados, y el inicio rápido no lo advierte. | `git status` tras `analyze` en un clon limpio | Aviso en las lecciones y cómo descartarlo con `git checkout -- repository/`. |
| H-4 | Baja | `--json` y `--root` son opciones de cada subcomando: escritas antes de él, argparse responde `unrecognized arguments` (código 2). | `python -m pallaquino_cli --json validate` | Explicado en los errores frecuentes. |
| H-5 | Baja | Sin instalar el paquete, `python -m pallaquino_cli` solo funciona desde `universal_ai_fullstack_orchestrator` o `.pallaquino`. Con el paquete instalado, la raíz por defecto es el checkout del paquete (ADR-0004), no el proyecto. | `No module named pallaquino_cli` desde la raíz de un proyecto | Lecciones 2.3 y 2.4 con las dos formas de trabajar. |
| H-6 | **Media (defecto de código)** | En Windows, una identidad no ASCII (`Ana Pérez`) se aplica con `identity --apply-local`, pero devuelve `"matches": false` y `validate_git_authorship` sigue fallando. Causa: `run_git` (`pallaquino_cli/core.py`, línea 190) usa `text=True` sin `encoding`, así que la salida UTF-8 de Git se decodifica con cp1252. | Reproducido en un repositorio nuevo. Con un nombre ASCII, `doctor` termina con código 0. | **Corregido en PAL-013** (fuera del alcance de PAL-012): `run_git` y `scripts/configure_git_identity.py` decodifican en UTF-8. Test de regresión en `tests/test_git_identity.py`, que falla sin la corrección. Las lecciones lo indican para quien siga usando 0.5.0. |
| H-7 | Baja | La detección automática del comando de tests solo reconoce `tests/test*.py` (unittest) y `package.json` con script `test`. Proyectos como Django con `app/tests.py` obtienen el aviso `no test command detected`. No está documentado fuera del código. | `planning.detect_test_command`; plan de una solicitud Django en un repositorio vacío | Lección 8.3 (matriz de compatibilidad). |
| H-8 | Baja | `docs/DEMO.md` está fechado en 0.3.0 y sus cifras ya no son las actuales (`"planned": 307` frente a 383 en 0.5.0). Está etiquetado con su versión, pero puede confundir. | `init --dry-run` en 0.5.0 | Propuesta: actualizarlo o marcarlo como histórico. |
| H-9 | Baja | Los tutoriales de `docs/tutorials/` usan rutas POSIX (`/tmp/calc`, `cp -r`) sin la alternativa para PowerShell. | FIRST_MULTI_AGENT_EXECUTION | La academia ofrece pestañas por sistema operativo. |
| H-10 | Informativo | `agents match` sin `--json` también imprime JSON. | Ejecución directa | Sin impacto. No se documenta como diferencia. |
| H-11 | Baja (externo) | En la academia, el botón de búsqueda de Starlight muestra la pista `Ctrl K` fuera de su nombre accesible (`Buscar`). axe-core lo marca como `label-content-name-mismatch` en escritorio; el atajo sí se expone con `aria-keyshortcuts`. | Barrido de axe en el navegador (`evidence/accessibility_browser-2026-10-14T23-20-00+00-00.json`) | Se mantiene el componente de Starlight. Candidato a reportar al proyecto Starlight. |

Los tutoriales de `docs/tutorials/` (MCP, plugins, herramientas, memoria) se reprodujeron paso a paso con 0.5.0 y coinciden con el
comportamiento real, incluidos los códigos de salida 1, 3 y 5 que anuncian.

## 3. Lo que la academia no afirma

- No hay resultados de pruebas con usuarios: el protocolo está en [UX_TEST_PROTOCOL.md](UX_TEST_PROTOCOL.md) y no se ha ejecutado.
- No hay videos: solo guiones (`academy/src/content/docs/videos/`).
- No hay tutoriales de Django ni de Nuxt de principio a fin.
- La edición en inglés no está traducida.
- El sitio no está desplegado: el workflow existe, pero solo se ejecuta manualmente y con aprobación.
