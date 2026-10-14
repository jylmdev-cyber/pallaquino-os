# Política de seguridad

## Versiones soportadas

| Versión | Soporte de seguridad |
|---|---|
| 0.3.x | Sí |
| 0.2.x | No |
| < 0.2 | No |

Mientras el proyecto permanezca antes de 1.0, las correcciones se publicarán en
la última versión disponible.

## Reportar una vulnerabilidad

No abras un Issue público. Envía un reporte a `jylmdev@gmail.com` con el asunto
`[PALLAQUINO SECURITY]` e incluye:

- componente y versión afectada;
- pasos mínimos de reproducción o prueba de concepto segura;
- impacto esperado y condiciones necesarias;
- mitigaciones conocidas;
- forma segura de contactarte.

Evita acceder a datos de terceros, degradar servicios o publicar detalles antes
de acordar una divulgación. Se intentará confirmar la recepción en 72 horas,
evaluar severidad y alcance, preparar una corrección y coordinar el aviso. Los
tiempos pueden variar según complejidad y disponibilidad del mantenedor.

## Alcance

Son relevantes vulnerabilidades en el CLI, scripts, registries, gates,
empaquetado, rutas de archivo, validación de entradas, supply chain y políticas
que produzcan una omisión de seguridad reproducible. Las tecnologías descritas
en perfiles externos conservan sus propios canales de seguridad.

## Modelo de amenazas (0.3.0)

PALLAQUINO se ejecuta localmente con los permisos del usuario y es leído por agentes
de IA. Activos: el repositorio del producto, el estado de continuidad, la evidencia
y las credenciales presentes en el entorno.

| Amenaza | Vector | Control en 0.3.0 | Estado |
|---|---|---|---|
| Inyección de instrucciones | README, issues, fixtures, memoria o salida de herramientas que intentan cambiar la política | `POLICY_HIERARCHY.md`, `PROMPT_INJECTION_DEFENSE.md`: el contenido es dato | Política (no ejecutable) |
| Fuga de secretos en evidencia | `scripts/evidence.py` guarda salida de comandos | `redact()` sobre comando y salida antes de persistir | Implementado y probado |
| Secretos versionados | Commits con claves | `pallaquino security audit` y paso de CI; los hallazgos nunca incluyen el valor | Implementado y probado |
| Contaminación entre proyectos | `init` copiaba estado ajeno | `manifest.json#instance_state` + estado limpio | Implementado y probado |
| Sobrescritura masiva accidental | Generadores de catálogo | Dry-run por defecto; `--write` explícito | Implementado y probado |
| Escape de rutas | Locks sobre rutas `../` | `_lock_key` confina al root en adquisición y liberación | Implementado y probado |
| Carreras entre agentes | Escritura concurrente de `file_locks.json` | Mutex `O_EXCL`, TTL y auditoría de expiración | Implementado y probado |
| Manipulación de checkpoints | Edición deliberada del JSON | SHA-256 detecta corrupción accidental, **no** manipulación | Limitación conocida (Fase 2) |
| Acciones destructivas | Borrado, despliegue, force push | `HUMAN_APPROVAL_POLICY.md`; el CLI no ejecuta ninguna | Política |
| Cadena de suministro | Dependencias del núcleo | Solo Standard Library; Actions oficiales con permisos `contents: read` | Implementado |

Los controles OWASP para aplicaciones con LLM (permisos por herramienta, denegación
por defecto, aislamiento de plugins) se implementan con el Extension System (Fase 3,
`docs/ROADMAP.md`). Hasta entonces PALLAQUINO no ejecuta herramientas ni plugins por
sí mismo.
