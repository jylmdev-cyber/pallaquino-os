# Publicación de la academia

> **Estado:** preparado, **no publicado**. Publicar es una acción externa que requiere la aprobación explícita del propietario del
> repositorio.

## Opción preparada: GitHub Pages (gratuita)

El workflow `.github/workflows/academy.yml` tiene dos trabajos:

- **`verify`**: se ejecuta en cada pull request y en cada push que toca `academy/`, `universal_ai_fullstack_orchestrator/` o el propio
  workflow. Corre `npm run ci` (datos, tipos, pruebas, contenido, build, enlaces y accesibilidad). No publica nada.
- **`deploy`**: solo se ejecuta con **`workflow_dispatch`** (botón *Run workflow*) y con la entrada `deploy: true`. Construye y publica
  `dist/` en GitHub Pages.

Pasos para la primera publicación (los hace el propietario):

1. En *Settings → Pages* del repositorio, elegir **Source: GitHub Actions**.
2. En *Actions → Academy*, ejecutar *Run workflow* con `deploy` activado.
3. Comprobar `https://jylmdev-cyber.github.io/pallaquino-os/`.

La URL depende de dos variables:

- `ACADEMY_SITE` (por defecto `https://jylmdev-cyber.github.io`);
- `ACADEMY_BASE` (por defecto `/pallaquino-os/`).

Para un dominio propio, define `ACADEMY_SITE=https://tu-dominio` y `ACADEMY_BASE=/`, y añade `public/CNAME`.

## Alternativas gratuitas

Cualquier hosting estático sirve `dist/` sin cambios, por ejemplo Cloudflare Pages o Netlify. Comando de build:
`npm ci && npm run build` en `academy/`; directorio de salida: `academy/dist`. Ajusta `ACADEMY_BASE=/` si se sirve en la raíz.

## Antes de publicar

- `npm run ci` en verde.
- Revisar en un navegador las páginas principales en modo claro y oscuro, en escritorio y en móvil.
- Confirmar que no hay datos personales en las transcripciones (rutas sustituidas por `<ruta>` y `<home>`).
