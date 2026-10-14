# ADR-0011: Motor de memoria de proyecto en SQLite

- Status: accepted (2026-10-14, v0.4.0)
- Confidence: high
- Context: cada sesión volvía a leer el repositorio y no quedaba registro estructurado de planes, ejecuciones, decisiones ni resultados.
- Options: (a) archivos JSON sueltos — sin transacciones ni consultas; (b) base vectorial obligatoria — dependencia externa y no determinista;
  (c) SQLite de la stdlib por proyecto, con embeddings como extensión opcional futura.
- Decision: (c). `memory/pallaquino.db` dentro de la instalación del proyecto (estado de instancia: no se copia con `init`, no se versiona,
  no entra en el ZIP). Modo WAL, migraciones versionadas en `schema_migrations`, y cinco categorías: project, execution, decision, quality y
  agent_performance. Reglas:
  - toda consulta va filtrada por `project`;
  - los secretos se redactan antes de escribir;
  - cada documento lleva un checksum: lo manipulado se excluye de las búsquedas y se informa, y los planes, ejecuciones o tareas
    manipulados detienen la carga (`MemoryCorrupted`);
  - lo recuperado es siempre `trust: untrusted`, con aviso explícito y marca de instrucciones sospechosas, y nunca llega al rol de sistema;
  - el borrado y la purga exigen confirmación y quedan auditados;
  - la retención se basa en TTL y en registros reemplazados (`superseded_by`).
- Consequences: el historial de agentes solo cuenta ejecuciones verificadas y no simuladas, por lo que el router no fabrica tasas de éxito.
  La búsqueda es por palabras clave con ranking por coincidencias y recencia; la búsqueda semántica queda para una interfaz opcional.
- Reversal: borrar `memory/`; el motor recrea el esquema vacío.
