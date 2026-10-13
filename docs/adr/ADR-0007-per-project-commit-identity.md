# ADR-0007: Identidad de commit configurable por proyecto

- Status: accepted (2026-10-13, decisión del propietario sobre Q-1)
- Confidence: high
- Context: la política fijaba `jimdev <jylmdev@gmail.com>` en el código, de modo que
  todo proyecto que adoptaba PALLAQUINO quedaba obligado a esa identidad, mientras
  `CONTRIBUTING.md` pedía a cada colaborador usar la suya.
- Options: (a) variable de entorno — depende de la máquina, no del proyecto;
  (b) eliminar la comprobación — debilita la política; (c) archivo versionado por
  proyecto con jimdev como valor por defecto.
- Decision: (c). `governance/git_identity.json` declara la identidad esperada; si no
  existe se usa jimdev. `pallaquino identity` la muestra, `--name/--email` la cambia y
  `--apply-local` la escribe solo en la configuración Git local. El validador, el CI y
  `commit_as_jimdev.py` la leen. Este repositorio mantiene jimdev.
- Consequences: los proyectos nuevos heredan jimdev hasta que lo cambien. Un archivo
  inválido hace fallar `validate_governance`. Se mantiene la prohibición de trailers
  de coautoría de IA (decisión sobre Q-2).
- Reversal: borrar el archivo devuelve el comportamiento de 0.2.1.
