# Modelo de seguridad de plugins (v0.5.0)

## Principios

1. **Instalado no es autorizado.** Un plugin instalado queda `INSTALLED`. Sin una entrada de confianza ligada a su hash nunca se ejecuta, y
   sus herramientas necesitan además grants de la pasarela.
2. **Descubrir no es ejecutar.** El descubrimiento lee metadatos de distribución y `plugin.toml`; no importa módulos ni carga entry points.
3. **El manifiesto declara; el humano aprueba.** Capacidades, operaciones y esquemas salen del manifiesto. El humano aprueba ese manifiesto y
   ese código (`plugins trust`) por su hash.
4. **Separado del proceso principal.** El plugin no comparte memoria, credenciales, base de datos ni entorno con PALLAQUINO.

## Capas

| Capa | Mecanismo | Qué detiene |
|---|---|---|
| Integridad | `content_hash` (SHA-256 de rutas y contenidos, sin cachés) frente a `plugin_trust.json` | código manipulado tras la revisión → QUARANTINED |
| Alcance | `allowed_capabilities` ⊇ `permissions.requested` ⊇ capacidades de cada herramienta | plugins que piden más de lo aprobado |
| Honestidad del catálogo | el host compara herramientas y esquemas vivos con el manifiesto; el runner rechaza implementaciones no declaradas | herramientas ocultas (`exfiltrate`) |
| Proceso | `python -I`, bootstrap explícito, entorno saneado, `cwd` temporal, cierre por stdin | lectura de tokens del entorno, imports del directorio actual |
| Workspace | `ToolCall.resolve` confina las rutas; solo se pasa el workspace si se piden capacidades de lectura o escritura | rutas `../` o absolutas |
| Pasarela | grants, aprobaciones por llamada, validación de salida, redacción, marcas de inyección | uso no autorizado y fugas |
| Instalación | ZIP con SHA-256 obligatorio, sin traversal ni enlaces, sin scripts; no instala dependencias | cadena de suministro |
| Ciclo de vida | transiciones validadas; rollback ante una actualización fallida; desinstalación acotada | estado inconsistente; borrados fuera de alcance |

## Lo que no promete

- Sandbox del sistema operativo (seccomp, AppContainer, contenedores): fuera de alcance en 0.5.0.
- Revertir efectos externos que un plugin haya producido. El rollback restaura la versión del plugin, no el mundo exterior.
- Verificar la identidad del autor: no hay firma de editores. La confianza la da la revisión local del hash.
