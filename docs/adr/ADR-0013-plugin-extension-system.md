# ADR-0013: Sistema de extensiones — manifiesto, descubrimiento sin ejecución, confianza por hash y aislamiento por proceso

- Status: accepted (2026-10-14, v0.5.0)
- Confidence: high para el contrato, el ciclo de vida y la política de confianza; medium para el aislamiento, que es por proceso y no un sandbox del sistema operativo
- Context: el pedido v0.5.0 exige descubrir, validar, habilitar y ejecutar plugins sin que instalar uno le dé permisos, sin ejecutar código
  desconocido al descubrirlo y con el código no confiable fuera del proceso principal.
- Options:
  - (a) importar los plugins en el proceso (estilo pluggy): rápido, pero un plugin hereda memoria, credenciales y permisos del host;
  - (b) contenedores por plugin: aislamiento fuerte, pero exige Docker y rompe "offline, solo stdlib";
  - (c) manifiesto declarativo, descubrimiento por metadatos, política de confianza ligada al hash del contenido y ejecución en un subproceso
    que habla MCP por stdio.
- Decision: (c).
  - **Manifiesto** `plugin.toml` v1, leído con `tomllib`:
    - define identidad, tipo (11 tipos), compatibilidad SemVer, entrypoint, aislamiento, permisos solicitados, herramientas (esquema,
      capacidades, clase de operación y etiquetas `provides`), dependencias y configuración;
    - un plugin no puede declararse confiable.
  - **Descubrimiento** mediante entry points `pallaquino.plugins` (`importlib.metadata`, sin llamar a `EntryPoint.load`) y el directorio
    `plugins/` del proyecto. Las duplicadas se informan como conflicto.
  - **Confianza**: `governance/plugin_trust.json` es una decisión humana por proyecto, con el hash SHA-256 del contenido y las capacidades
    permitidas.
    - Sin entrada, un plugin nunca se ejecuta.
    - Si el hash cambia, el plugin queda en cuarentena.
    - Si pide más capacidades de las aprobadas, se rechaza.
  - **Ejecución**: `python -I` con un bootstrap que solo añade el framework y la ruta del plugin; entorno saneado; directorio de trabajo
    temporal. El plugin se sirve como servidor MCP 2026-07-28 por stdio.
    - El host compara el catálogo vivo con el manifiesto: nombres y esquemas.
    - Las herramientas se registran desde el manifiesto revisado, nunca desde lo que el plugin dice de sí mismo.
  - **Instalación**: copia un directorio, o extrae un ZIP con SHA-256 verificado (sin rutas inseguras ni enlaces simbólicos). Nunca ejecuta
    scripts de instalación ni instala dependencias.
  - **Actualización**: conserva la versión anterior y la restaura si la nueva falla.
  - **Desinstalación**: borra solo el directorio que el gestor creó.
- Consequences:
  - Un plugin confiable sigue sin poder usarse sin un grant de la pasarela (ADR-0015).
  - El aislamiento separa memoria, credenciales y entorno, pero no impide que un plugin confiable lea archivos del sistema con los permisos
    del usuario. Eso se declara y se documenta en `docs/security/PLUGIN_SECURITY_MODEL.md`.
- Reversal: los plugins se ejecutan aparte. Deshabilitarlos o desinstalarlos los quita del registro sin tocar el núcleo.
