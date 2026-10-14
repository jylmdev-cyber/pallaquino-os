# PALLAQUINO Academy

Portal educativo estático para aprender a instalar, usar y extender PALLAQUINO Autonomous Engineering OS.

Incluye:

- 9 rutas de aprendizaje con 46 lecciones y 10 evaluaciones;
- el tutorial completo de primera instalación;
- una terminal simulada con salidas reales grabadas;
- recorridos visuales del flujo, el DAG, los quality gates y los permisos;
- progreso local por niveles;
- referencia para desarrolladores generada del código;
- búsqueda local, modo oscuro y estructura multilingüe (español primero; inglés preparado).

Decisión de arquitectura: [ADR-0017](../docs/adr/ADR-0017-learning-academy-stack.md). Guías: [docs/learning/](../docs/learning/).

## Requisitos

- Node.js 22.12 o superior y npm.
- Python 3.11 o superior, solo para regenerar los datos y las transcripciones.

## Comandos

Desde `academy/`:

```bash
npm ci                 # instala dependencias exactas (package-lock.json)
npm run dev            # servidor local en http://localhost:4321/pallaquino-os/
npm run build          # sitio estático en dist/
npm run preview        # sirve dist/
npm run ci             # todo lo que ejecuta la CI (ver abajo)
```

| Script | Qué hace |
|---|---|
| `npm run data` | Regenera `src/data/generated/*.json` desde `pallaquino_cli` y el registro (determinista) |
| `npm run data:check` | Falla si los datos generados no coinciden con el código |
| `npm run transcripts` | Clona el repositorio en un directorio temporal y vuelve a grabar las salidas reales |
| `npm run check` | `astro check` y `vue-tsc` |
| `npm test` | Pruebas de la lógica y de los componentes (vitest, jsdom y axe-core) |
| `npm run validate:content` | Ids de lección, prerrequisitos y comandos de la CLI comparados con `cli.json`; ids de agentes, transcripciones y retos |
| `npm run validate:links` | Enlaces internos y anclas del sitio construido |
| `npm run validate:a11y` | axe-core sobre las páginas construidas |

## Estructura

```text
academy/
  astro.config.mjs        Starlight: locales, barra lateral, overrides, base configurable
  scripts/                generadores (Python) y validadores (Node, sin dependencias)
  src/content/docs/       lecciones y páginas (MDX); en/ para la edición inglesa
  src/components/         islas Vue (terminal, evaluaciones, simuladores) y componentes Astro
  src/lib/                lógica pura: progreso, simulador de terminal, retos, permisos
  src/data/               datos generados y transcripciones grabadas
  tests/                  pruebas vitest
```

## Privacidad

El progreso se guarda solo en el `localStorage` del navegador, bajo la clave `pallaquino-academy-progress-v1`. No incluye secretos ni
datos personales. No se envía a ningún servicio, y no hay analítica ni cookies de terceros.
