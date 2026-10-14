# ADR-0017: Academia de aprendizaje estática con Astro + Starlight, islas Vue y datos generados del código

- Status: accepted (2026-10-14, PAL-012)
- Confidence: high para la generación de datos, la validación de contenido y el build estático, verificados localmente; medium para el
  despliegue, preparado pero no ejecutado (requiere aprobación)
- Context:
  - El pedido de PAL-012 es un portal educativo con rutas de aprendizaje, tutoriales, terminal simulada, recorridos visuales,
    evaluaciones, progreso local, referencia para desarrolladores, búsqueda, modo oscuro, estructura multilingüe (español primero),
    validación docs-as-code y despliegue estático gratuito.
  - Restricciones del pedido:
    - no inventar comandos ni funciones;
    - no alterar el núcleo innecesariamente;
    - no ejecutar comandos reales desde el navegador;
    - no guardar secretos en LocalStorage;
    - no enviar datos de aprendizaje a terceros;
    - no publicar sin autorización.
  - El framework es Python sin dependencias de ejecución. El portal es una pieza aparte y no debe añadir dependencias al núcleo.
- Options:
  - (a) Astro + Starlight con islas Vue: sitio estático, búsqueda local (Pagefind), modo oscuro, i18n, accesibilidad base, componentes
    de documentación (pasos, pestañas, avisos) e interactividad solo donde hace falta;
  - (b) VitePress: Vue nativo y ligero, pero con menos piezas listas (búsqueda local menos completa y sin páginas de lección tipadas);
  - (c) Docusaurus (React): maduro, pero más pesado, y añadiría React a un repositorio sin JavaScript;
  - (d) Nuxt Content: potente, pero orientado a aplicaciones con servidor y con más superficie para un sitio puramente estático;
  - (e) MkDocs Material (Python): encaja con el lenguaje del framework, pero la interactividad (terminal simulada, evaluaciones,
    simuladores) exigiría JavaScript a mano.
- Decision: (a), con versiones fijadas exactas.
  - Versiones: Astro 7.3.8, @astrojs/starlight 0.42.6, @astrojs/vue 7.0.3, Vue 3.5.44 y TypeScript 6.0.3. TypeScript 7 no se usa porque
    vue-tsc necesita la API de TypeScript 6.
  - Pruebas: vitest 5, @vue/test-utils, jsdom y axe-core.
  - El portal vive en `academy/` con su propio `package.json`. El núcleo no cambia.
  - **Fuentes de verdad**: `scripts/generate_data.py` importa `pallaquino_cli` y genera JSON deterministas con los comandos (recorriendo
    `argparse`), los agentes, las skills, los contratos, el pipeline, las herramientas builtin y los catálogos. `--check` falla si el JSON
    no coincide con el código.
  - **Salidas reales**: `scripts/capture_transcripts.py` clona el repositorio en un directorio temporal, ejecuta una lista fija de comandos
    de solo lectura o autocontenidos (incluido un proyecto de ejemplo) y guarda las salidas sanitizadas con la fecha y la plataforma de
    la captura.
  - **Terminal simulada**: reproduce únicamente esas salidas grabadas. No hay shell, ni servidor, ni `eval`. Bloquea comandos del sistema y
    operadores de shell, y etiqueta cada respuesta (grabada, simulada, informativa, error o bloqueada).
  - **Progreso**: solo en `localStorage`, bajo la clave `pallaquino-academy-progress-v1`, con un esquema validado al cargar e importar
    (límite de 200 KB). No guarda secretos ni datos personales y no envía nada a ningún servicio.
  - **Validación docs-as-code**, bloqueante en CI:
    - el esquema de lección se valida en el build;
    - `validate-content.mjs` comprueba ids de lección, siguientes lecciones, prerrequisitos, cada comando de la CLI escrito en el
      contenido contra `cli.json`, ids de agentes y skills, transcripciones y retos;
    - `validate-links.mjs` comprueba enlaces internos y anclas del sitio construido;
    - `validate-a11y.mjs` ejecuta axe-core sobre las páginas construidas;
    - pruebas de componentes con axe sobre el DOM hidratado.
  - **Despliegue**: GitHub Pages mediante un workflow de ejecución manual (`workflow_dispatch`), documentado y no ejecutado. Publicar
    requiere la aprobación del propietario.
- Consequences:
  - Cualquier cambio en la CLI, el registro o el pipeline se refleja con `npm run data`; si alguien olvida regenerarlos, la CI falla.
  - Una lección que cite un comando u opción inexistente no pasa la CI.
  - Las salidas grabadas envejecen. Hay que volver a capturarlas (`npm run transcripts`) en cada release y revisar el diff.
  - jsdom no calcula estilos: el contraste se comprueba con axe en un navegador real y queda registrado en la evidencia de PAL-012.
  - La edición en inglés está preparada (locale, interfaz, página de entrada) pero sin traducir; las páginas sin traducir muestran el
    contenido en español con un aviso.
