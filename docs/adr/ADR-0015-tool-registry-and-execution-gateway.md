# ADR-0015: Registro unificado de herramientas, pasarela de permisos y pasarela de ejecución

- Status: accepted (2026-10-14, v0.5.0)
- Confidence: high
- Context:
  - Con plugins y MCP aparecen herramientas de origen y confianza distintos.
  - El pedido exige un único registro, deny by default, aprobaciones no implícitas para acciones críticas y que ningún agente se salte la
    pasarela.
  - Las herramientas abstractas de los contratos v2 de 0.4.0 (`read_repository`, `write_files`, `deploy`, etc.) deben seguir valiendo.
- Options:
  - (a) que cada fuente aplique su política: incoherente y fácil de saltar;
  - (b) confiar en las anotaciones MCP (`readOnlyHint`): la especificación las declara no confiables;
  - (c) contrato de herramienta propio con capacidades, clase de operación y política derivada; una sola pasarela que resuelve, valida,
    autoriza, ejecuta, normaliza y audita.
- Decision: (c).
  - **Contrato `tool` v1**:
    - ID con espacio de nombres (`core.*`, `plugin.<id>.*`, `mcp.<servidor>.*`);
    - 12 capacidades y 5 clases de operación;
    - riesgo y política derivados: no se pueden debilitar (`validate_tool` lo rechaza);
    - límites, timeouts y reintentos (solo en lecturas);
    - etiquetas funcionales `provides`, que asigna PALLAQUINO, un manifiesto revisado o un humano, nunca una descripción.
  - **Clasificación**: la de los builtin la fija el código; la de los plugins, el manifiesto aprobado por hash; la de las herramientas MCP,
    un humano en `tool_policies`. Por defecto, una herramienta MCP es `EXTERNAL_SIDE_EFFECT`.
  - **Políticas**:
    - `contract`: lectura builtin, basta el grant de tarea del agente;
    - `grant`: concesión con alcance de proyecto, principal, herramienta u operación, con caducidad, usos máximos y revocación;
    - `per_call`: aprobación humana ligada al digest de los argumentos y consumida al usarse.
  - **Agentes**: una capacidad solo se autoriza si el grant de tarea del agente contiene la herramienta abstracta correspondiente
    (`CAPABILITY_GRANTS`). Si la herramienta abstracta es gobernada, la llamada pasa siempre a `per_call`.
  - **Pasarela**:
    - registro write-ahead de cada llamada; deduplicación por clave de idempotencia;
    - timeout con señal de cancelación cooperativa;
    - validación de la salida;
    - redacción de secretos;
    - detección de instrucciones inyectadas: el contenido se marca y no se guarda en memoria;
    - eventos de auditoría y `traceparent` W3C.
  - **Router**: filtra por capacidades, `provides`, disponibilidad y una evaluación de permisos en seco. Ordena por localidad, riesgo,
    necesidad de aprobación e historial auditado (desde 5 llamadas). Nunca inventa herramientas.
  - **Integración con la orquestación**:
    - nuevo tipo de ejecutor `tool`: las tareas `git_inspect` y `quality_scan` se ejecutan como el agente asignado;
    - el planner resuelve las herramientas en tiempo de plan;
    - el executor las vuelve a resolver si cambiaron.
- Consequences:
  - Toda llamada deja rastro verificable en `tool_calls` y en eventos.
  - Las acciones críticas exigen intervención humana por llamada.
  - El coste es una transacción SQLite por llamada, más la evaluación de grants.
- Reversal: el ejecutor `tool` es aditivo. Los planes de 0.4.0 no lo usan y se ejecutan igual.
