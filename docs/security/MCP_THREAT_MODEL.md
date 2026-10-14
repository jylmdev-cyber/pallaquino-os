# Modelo de amenazas: plugins, MCP y herramientas (v0.5.0)

Todo lo que llega de un servidor o de un plugin es dato no confiable: descripciones, anotaciones, `instructions`, resultados y mensajes de
error. Nada de eso concede permisos ni cambia una clasificación.

| Amenaza | Defensa implementada | Test |
|---|---|---|
| Prompt injection en resultados | `INJECTION_PATTERNS` marca la salida (`suspicious_instructions`); el hallazgo se degrada a `hypothesis`; no se guarda en memoria; evento `policy_violation` | `test_results_are_validated_redacted_and_flagged`, `test_injection_in_results_is_labelled_untrusted` |
| Tool poisoning (descripción manipulada) | las descripciones con instrucciones se marcan `poisoned` en la revisión y nunca se fijan ni registran; las descripciones no influyen en el router | `test_poisoned_descriptions_are_never_pinned_…` |
| Anotaciones engañosas (`readOnlyHint`) | se muestran como pistas; la clasificación la decide PALLAQUINO o un humano; por defecto `EXTERNAL_SIDE_EFFECT` → aprobación por llamada | mismo test (`delete_everything` queda `per_call`) |
| Cambio inesperado del catálogo (rug pull) | digest por definición; en cada llamada se compara la definición viva con la fijada; si difiere, se rechaza y la conexión pasa a DEGRADED | `test_rug_pull_after_review_is_refused` |
| Respuestas maliciosas o malformadas | validación de `resultType`, `outputSchema` y tamaños; las herramientas con esquema inválido se excluyen | `test_malformed_and_oversized_responses`, `test_x_mcp_header_…` |
| Exfiltración de información | los remotos se excluyen del router con `sensitive=True`; los argumentos van validados; los archivos sensibles se rechazan en el adaptador | `test_local_first_…`, `test_confinement_and_sensitive_files` |
| SSRF | `netpolicy.check_url`: HTTPS, sin IP privadas/loopback/link-local/CGNAT, IP fijada y sin redirecciones | `NetworkPolicyTest`, `test_configuration_never_holds_literal_secrets` |
| Filtración de credenciales | referencias `env:`/`vault:`; tokens por servidor y emisor; redacción en salida y eventos; entorno saneado para stdio y plugins | `test_tokens_are_bound_…`, `test_malicious_plugin_…`, test GitHub |
| Path traversal | `confine` (sin rutas absolutas ni `..`, resuelve enlaces); los walks no siguen enlaces; las escrituras no pasan por enlaces | `test_confinement_…`, `test_symbolic_links_never_escape`* |
| Confused deputy | el agente necesita el grant de tarea del contrato y además el grant de la pasarela; el router no ofrece herramientas que el agente no puede usar | `test_confused_deputy_…`, `SchedulerToolTest` |
| Escalada de privilegios | los grants no cubren `per_call`; las capacidades gobernadas fuerzan `per_call`; un plugin no pasa de las capacidades aprobadas | `test_critical_operations_…`, `test_capabilities_beyond_…` |
| Ataques a la cadena de suministro | instalación sin scripts; ZIP con SHA-256 y sin traversal ni enlaces; confianza ligada al hash; cuarentena si cambia | `test_archive_install_…`, `test_tampering_after_review_quarantines` |
| Suplantación de servidor | `serverInfo` no se usa para decisiones; OAuth valida `issuer` de metadatos e `iss` de la respuesta; tokens por emisor | `test_discovery_order_issuer_and_pkce_checks` |
| Peticiones de input del servidor (MRTR) | el manejador por defecto deniega; el servidor no puede pedir capacidades no declaradas | `test_multi_round_trip_input_is_denied_…` |
| DoS por esquema | profundidad, número de subesquemas y pasos acotados; `$ref` recursivo detectado | `test_resource_bounds_stop_hostile_schemas` |
| DNS rebinding contra el servidor de referencia | validación de `Origin` (403); bind a 127.0.0.1 | `test_server_validation_rules` |

\* Se omite en hosts que no pueden crear enlaces simbólicos, como el Windows de desarrollo; en Linux (CI) se ejecuta.

## Riesgos residuales declarados

- Un plugin **confiable** no está en un sandbox del sistema operativo: puede leer archivos con los permisos del usuario.
- Un servidor MCP stdio es un proceso local con los permisos del usuario. Configurarlo equivale a ejecutar ese programa.
- El vault de credenciales en archivo no está cifrado; se recomiendan referencias `env:` o keyring.
- Los checksums del store siguen sin clave (deuda de 0.4.0).
- El timeout de un adaptador builtin es cooperativo: el hilo puede seguir ejecutándose después de la señal.
