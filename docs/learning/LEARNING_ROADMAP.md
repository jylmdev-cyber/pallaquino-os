# Hoja de ruta de la academia

## Entregado en PAL-012 (primer incremento)

- Portal estático con Astro, Starlight y Vue: 9 rutas, 46 lecciones, 10 evaluaciones y 2 retos de terminal.
- Tutorial obligatorio «Instala y ejecuta PALLAQUINO por primera vez».
- Terminal simulada con 24 salidas reales grabadas (17 del framework y 7 del proyecto de ejemplo).
- Recorridos visuales: flujo, DAG, quality gates y permisos.
- Progreso local con niveles.
- Referencia generada del código: CLI, agentes y skills, herramientas y pipeline.
- Búsqueda local, modo oscuro, estructura en español e inglés.
- Validación docs-as-code y CI.
- Guiones de video, solo texto.

## Siguiente

| Prioridad | Trabajo | Criterio de aceptación |
|---|---|---|
| Alta | Ejecutar el protocolo de pruebas con usuarios ([UX_TEST_PROTOCOL.md](UX_TEST_PROTOCOL.md)) | Al menos 5 sesiones registradas, con hallazgos y cambios aplicados |
| Alta | Publicar en GitHub Pages | Aprobación del propietario; workflow `deploy` en verde |
| Media | Traducir al inglés las rutas 1 a 3 | Páginas en `docs/en/` que pasen `npm run ci` |
| Media | Tutoriales Django y Nuxt de principio a fin | Solo cuando el recorrido se haya ejecutado y grabado con la versión vigente |
| Media | Retos de terminal para las rutas 5 y 7 | Cada paso validado contra transcripciones grabadas |
| Baja | Grabar los videos de los guiones | Video publicado y enlazado desde su guion |
| Baja | Lecciones de 0.6.0 (*Project Factory*) | Cuando la versión exista |
