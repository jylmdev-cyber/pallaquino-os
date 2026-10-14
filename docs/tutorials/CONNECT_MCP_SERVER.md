# Tutorial: conectar un servidor MCP

Se usa el servidor de pruebas local `examples/mcp_servers/quality_server.py` (MCP 2026-07-28, stdio). Funciona sin red ni credenciales.

> En un proyecto inicializado, ejecuta los comandos con `--root .pallaquino` o con `PALLAQUINO_ROOT` exportado. Con una instalación
> editable, `pallaquino` resuelve antes el checkout del paquete que `./.pallaquino` (ADR-0004).

```bash
# 1. Configurar y clasificar la herramienta que vas a usar (operación, capacidades y etiqueta funcional)
pallaquino mcp add quality --classify "quality_scan=READ_ONLY:FILE_READ:quality_scan" --stdio python examples/mcp_servers/quality_server.py

# 2. Probar la conexión
pallaquino mcp test quality
#   {"ok": true, "era": "modern", "protocol_version": "2026-07-28", "tools": 5,
#    "instructions": {"text": "Static quality checks...", "trust": "untrusted"}, ...}

# 3. Revisar el catálogo: cada herramienta aparece como new, con descripción y anotaciones marcadas como no confiables
pallaquino mcp tools quality

# 4. Fijar solo lo que revisaste
pallaquino mcp pin quality --tool quality_scan

# 5. Autorizar al agente que lo usará
pallaquino permissions grant mcp.quality.quality_scan --principal project_analyzer --operation READ_ONLY --days 7

# 6. Usarlo desde el motor
pallaquino plan "Analiza el repositorio actual, identifica problemas de calidad, revisa el estado de Git y genera un informe técnico"
#   T03 quality_scan -> mcp.quality.quality_scan (sin el grant, el planner usa el fallback core.files.search)
pallaquino run --plan <plan-id>
```

## Servidores remotos

```bash
pallaquino mcp add remote --url https://mcp.example.com/mcp
pallaquino mcp test remote        # un 401 deja la conexión en AUTH_REQUIRED
pallaquino mcp auth remote --client-id https://tu-dominio.example/pallaquino-client.json
pallaquino mcp test remote
```

`mcp auth` descubre los metadatos (RFC 9728 y RFC 8414/OIDC), abre la autorización con PKCE S256 y `resource`, escucha el callback en
127.0.0.1, valida `state` e `iss` y guarda el token ligado a este servidor y a este emisor. Para servidores stdio, las credenciales se pasan
con referencias de entorno: `"env": {"API_TOKEN": "env:MI_TOKEN"}`.

Las URL privadas, loopback o link-local y el HTTP plano se rechazan, salvo `--allow-http-loopback` para un servidor local explícito.

## Cuando algo cambia

Si el servidor modifica la descripción o el esquema de una herramienta fijada, la siguiente llamada se rechaza ("no longer matches its
pinned definition"), la conexión pasa a DEGRADED y `mcp tools` muestra `changed`. Revisa el cambio y vuelve a ejecutar `mcp pin`. Las
descripciones con instrucciones (`poisoned`) no se pueden fijar.
