# Cómo escribir una lección

## 1. Frontmatter

Cada lección es un `.mdx` en `academy/src/content/docs/<ruta>/` con el bloque `lesson`. El esquema se valida en el build: si falta un
campo obligatorio o un valor no es válido, el build falla.

```yaml
---
title: Título visible
description: Una frase para buscadores y tarjetas.
sidebar:
  order: 3
lesson:
  id: ruta-tema            # único, kebab-case
  path: cli                # una de las 9 rutas (src/lib/paths.ts)
  difficulty: intermedio   # principiante | intermedio | avanzado
  duration: 15             # minutos, 1-120
  objectives:
    - Qué sabrá hacer quien termine
  prerequisites:
    - otra-leccion-id      # un id de lección se convierte en enlace; también se admite texto libre
  status: disponible       # disponible | experimental | deprecado | proximamente
  since: 0.5.0             # versión de PALLAQUINO desde la que aplica
  next: siguiente-id       # opcional; debe existir
---
```

Termina la página con `<LessonComplete client:load lessonId="<el mismo id>" />`.

## 2. Estructura recomendada

Objetivo, explicación sencilla, ejemplo, comandos, resultado esperado, errores frecuentes, ejercicio, comprobación (`CheckList`,
`QuizPlayer` o reto de terminal), resumen y siguiente paso.

## 3. Reglas de veracidad

- **Ejecuta cada comando antes de publicarlo**, en un clon limpio o en un proyecto de prueba. `npm run validate:content` comprueba que el
  comando, la acción y las opciones existen, pero no que el ejemplo tenga sentido.
- Para mostrar salidas, usa `<Transcript id="…" />` con una transcripción grabada. Si hace falta una nueva, añádela a `COMMANDS` o a
  `PROJECT_COMMANDS` en `scripts/capture_transcripts.py` y ejecuta `npm run transcripts`. No pegues salidas escritas a mano.
- Si recortas una salida, dilo («extracto real»).
- No presentes como disponible nada que no exista. Usa `status: proximamente` o `experimental` y di en qué versión está previsto.
- Distingue siempre lo real, lo simulado (`simulated: true`) y lo no verificado.
- Escribe los ids de agentes y skills entre comillas invertidas: el validador comprueba que existen.

## 4. Componentes disponibles

| Componente | Uso |
|---|---|
| `Steps`, `Tabs`/`TabItem`, `Aside`, `Card`, `LinkCard`, `FileTree` | De `@astrojs/starlight/components` |
| `Transcript` | Salida real grabada (`id`, `lines` opcional) |
| `InteractiveTerminal` | Terminal simulada; `challenge` para abrir un reto |
| `QuizPlayer` | Evaluación (`id` único, `title`, `questions`); cada opción con `why` |
| `CheckList` | Lista de verificación persistente (`group`, `items`) |
| `FlowDiagram`, `DagPlayer`, `QualityGates`, `PermissionSimulator` | Recorridos visuales |
| `AgentExplorer`, `CommandExplorer` | Exploradores de la referencia |

## 5. Estilo

Español claro, frases cortas, segunda persona. Tablas para comparar y listas para pasos. Los comandos van en bloques `bash` (con
pestañas por sistema operativo cuando difieren). Cada imagen o diagrama necesita un texto alternativo o una descripción equivalente.

## 6. Antes de abrir el pull request

```bash
npm run ci
```
