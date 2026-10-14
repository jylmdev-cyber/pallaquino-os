# Arquitectura de la academia

Decisión y alternativas: [ADR-0017](../adr/ADR-0017-learning-academy-stack.md).

## Flujo de datos

```text
pallaquino_cli + registry/ + pipeline/ ──generate_data.py──▶ src/data/generated/*.json ──┐
clon temporal del repositorio ──capture_transcripts.py──▶ src/data/transcripts.json ─────┤
                                                          src/data/plan_example.json ─────┤
src/content/docs/**/*.mdx (lecciones con frontmatter `lesson`) ───────────────────────────┤
                                                                                          ▼
                                     astro build (Starlight + islas Vue) ──▶ dist/ (HTML estático + Pagefind)
```

Ningún dato de la referencia se escribe a mano:

- **comandos**: el analizador `argparse` real, recorrido con sus acciones, opciones, `choices` y valores por defecto;
- **agentes y skills**: `registry/*.json` y los contratos v2;
- **pipeline**: `pipeline/pipeline_definition.json`;
- **herramientas**: el registro builtin de los adaptadores.

## Páginas y componentes

| Pieza | Tipo | Notas |
|---|---|---|
| `overrides/PageTitle.astro` | Override de Starlight | Migas de pan y la tarjeta de lección (nivel, duración, estado, versión, objetivos y prerrequisitos enlazados) |
| `PathCards.astro`, `ProgressPanel.astro`, `Transcript.astro` | Astro (sin JS) | Calculados en el build a partir de la colección y de los datos |
| `InteractiveTerminal.vue` | Isla | Usa `lib/terminal.ts`: tokenizador, bloqueo de comandos y operadores, reproducción exacta de salidas grabadas, errores de argparse y autocompletado desde `cli.json` |
| `QuizPlayer.vue`, `CheckList.vue`, `LessonComplete.vue`, `LearningProgress.vue` | Islas | Progreso local mediante `lib/progress.ts` |
| `FlowDiagram.vue`, `DagPlayer.vue`, `QualityGates.vue`, `PermissionSimulator.vue` | Islas | Recorridos con datos reales (plan grabado, etapas y reglas de `lib/permissions.ts`, probadas contra `tools.json`) |
| `AgentExplorer.vue`, `CommandExplorer.vue` | Islas | Búsqueda y filtros sobre los datos generados |

Las islas se hidratan con `client:load` cuando son el contenido principal de la página y con `client:visible` cuando están más abajo.
Sin JavaScript, todo el contenido de texto, las tablas y las salidas grabadas siguen siendo legibles.

## Progreso

`ProgressStore` (en `lib/progress.ts`):

- guarda `completed`, `quizzes` (mejor resultado, con aprobado al 70 %), `checks` y `challenges`;
- valida el esquema al cargar y al importar (límite de 200 KB);
- si `localStorage` no está disponible, usa memoria;
- emite el evento `pallaquino-progress` para que todas las islas de la página se sincronicen.

| Nivel | Lecciones completadas |
|---|---|
| Explorer | 0 % |
| Developer | 25 % |
| Advanced Developer | 60 % |
| PALLAQUINO Contributor | 90 % |

## Seguridad

- El sitio es estático: no hay backend, ni shell, ni `eval` de entradas del usuario.
- La terminal solo compara la entrada con transcripciones grabadas. Los comandos del sistema, los operadores de shell y las entradas de
  más de 500 caracteres se rechazan.
- No hay scripts de terceros, analítica ni cookies. Las dependencias están fijadas y `npm audit` informaba 0 vulnerabilidades el
  2026-10-14.

## Internacionalización

- Locales: `root` (español, `lang="es"`) y `en`.
- Las cadenas de interfaz propias están en `src/content/i18n/<lang>.json`.
- Una página traducida se crea en `src/content/docs/en/` con la misma ruta; mientras no existe, Starlight muestra la versión en español
  con un aviso.
