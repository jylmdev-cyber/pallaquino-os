# Mantenimiento de la academia

## En cada release de PALLAQUINO

1. `npm run data`: regenera la referencia (comandos, agentes, skills, pipeline, herramientas, catálogos). Revisa el diff.
2. `npm run transcripts`: vuelve a grabar las salidas en un clon limpio. Revisa el diff; si una salida cambió de forma relevante, revisa
   las lecciones que la usan (`grep -rn 'Transcript id="<id>"' academy/src/content`).
3. Actualiza `since` y `status` de las lecciones afectadas y la página `referencia/versiones.mdx`.
4. `npm run ci`.
5. Regenera la instantánea de `docs/learning/CONTENT_CATALOG.md` si cambiaron lecciones.

La CI falla si los datos generados no coinciden con el código (`data:check`) o si una lección cita un comando u opción que ya no existe
(`validate:content`).

## Dependencias

Las versiones están fijadas exactas en `academy/package.json`, con `package-lock.json`. Para actualizar:

1. comprueba en las fuentes oficiales (npm, changelogs) que la versión es estable y tiene al menos dos semanas;
2. actualiza una dependencia cada vez y ejecuta `npm run ci`;
3. ejecuta `npm audit`.

Restricciones conocidas: vue-tsc requiere la API de TypeScript 6, así que TypeScript 7 queda bloqueado hasta que vue-tsc lo soporte; el
`override` de `postcss-selector-parser` corrige un aviso de `npm audit`.

## Problemas abiertos que afectan al contenido

Ver [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md) §2 (en particular H-6). Cuando se corrija un defecto, retira el aviso de las lecciones
y de `referencia/solucion-de-problemas.mdx`.
