# Tutorial: ejecutar herramientas de forma segura

> En un proyecto inicializado, ejecuta los comandos con `--root .pallaquino` o con `PALLAQUINO_ROOT` exportado. Con una instalación
> editable, `pallaquino` resuelve antes el checkout del paquete que `./.pallaquino` (ADR-0004).

```bash
pallaquino tools list                                  # ID, fuente, operación, riesgo, política, disponibilidad
pallaquino tools inspect core.files.write              # contrato completo
pallaquino tools route --capability FILE_READ          # candidatos permitidos, ordenados con motivos
pallaquino tools check core.files.write --args '{"path":"a.txt","content":"x"}'   # dry run: {"decision": {"outcome": "denied", ...}}
```

## Lectura builtin: permitida

```bash
pallaquino tools run core.git.status                   # COMPLETED; "checks" lista los 12 pasos de la pasarela
```

## Escritura: requiere un grant

```bash
pallaquino tools run core.files.write --args '{"path":"notes/a.txt","content":"hola"}'   # DENIED, exit 5
pallaquino permissions grant core.files.write --operation WRITE_OPERATION --days 1 --max-uses 3 --reason "notas"
pallaquino tools run core.files.write --args '{"path":"notes/a.txt","content":"hola"}'   # COMPLETED
pallaquino tools run core.files.write --args '{"path":".env","content":"A=1"}'           # DENIED: archivo sensible
pallaquino tools run core.files.write --args '{"path":"../fuera.txt","content":"x"}'     # DENIED: fuera del workspace
```

## Efecto externo: aprobación por llamada

Requiere la conexión del tutorial [CONNECT_MCP_SERVER](CONNECT_MCP_SERVER.md) con `echo` fijado (`pallaquino mcp pin quality --tool quality_scan --tool echo`); `echo` no está clasificada, así que su operación por defecto es EXTERNAL_SIDE_EFFECT.

```bash
pallaquino tools run mcp.quality.echo --args '{"message":"hola"}'             # APPROVAL_REQUIRED, exit 3
pallaquino tools run mcp.quality.echo --args '{"message":"hola"}' --approve   # aprueba exactamente esta llamada y la ejecuta
```

La aprobación se liga al digest SHA-256 de `[tool_id, argumentos]` y se consume al usarse. Ningún grant la sustituye.

## Auditoría

```bash
pallaquino tools calls                  # registro de cada llamada: estado, comprobaciones, principal, traceparent
pallaquino permissions history          # concesiones, denegaciones, revocaciones y violaciones de política
pallaquino tools metrics                # éxito, fallo, timeouts, denegaciones y latencia por herramienta
pallaquino permissions revoke <grant-id>
```

La salida de cualquier herramienta es un dato no confiable:

- los valores con forma de secreto se redactan (`redacted: true`);
- el contenido con instrucciones se marca (`suspicious_instructions: true`), queda registrado como `policy_violation` y no se guarda en
  memoria.
