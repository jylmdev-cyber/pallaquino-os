# Conexiones MCP

Código: `pallaquino_cli/mcp/connections.py`. CLI: `pallaquino mcp …`.

## Ciclo

```bash
# 1. Configurar (no conecta). Un servidor stdio es un programa local: configurarlo equivale a ejecutarlo.
pallaquino mcp add quality --classify "quality_scan=READ_ONLY:FILE_READ:quality_scan" --stdio python examples/mcp_servers/quality_server.py
pallaquino mcp add remote --url https://mcp.example.com/mcp --credential-ref vault:remote --issuer https://auth.example.com
# 2. Probar: versión negociada, era, capacidades, latencia
pallaquino mcp test quality
# 3. Revisar el catálogo: new | pinned | changed | poisoned (descripción e instrucciones marcadas como no confiables)
pallaquino mcp tools quality
# 4. Fijar lo revisado (solo entonces las herramientas entran en el registro)
pallaquino mcp pin quality [--tool quality_scan]
# 5. Conceder (READ_ONLY clasificada) o aprobar por llamada (sin clasificar)
pallaquino permissions grant mcp.quality.quality_scan --principal project_analyzer
pallaquino mcp doctor | inspect quality | disable quality | remove quality
pallaquino mcp auth remote --client-id https://pallaquino.example/client.json   # OAuth (solo HTTP)
pallaquino mcp logout remote
```

`--stdio` toma el resto de la línea, así que debe ir al final.

## Clasificación

`--classify TOOL=OPERACIÓN:CAP[,CAP][:TAG[,TAG]]` guarda en `tool_policies` la clasificación humana: operación, capacidades y etiquetas
`provides`. Sin clasificar, una herramienta queda como `EXTERNAL_SIDE_EFFECT`, con capacidad CODE_EXECUTION (stdio) o NETWORK_WRITE (HTTP)
y política `per_call`.

## Persistencia

| Documento | Contenido |
|---|---|
| `connection` | configuración (sin secretos: `env` solo admite `env:VAR`) |
| `catalog` | definiciones fijadas con su digest, herramientas rechazadas, quién las aprobó, versión y era negociadas |
| (memoria del proceso) | clientes vivos y estado de transporte |

Las credenciales viven en el `CredentialStore` (ADR-0016), nunca en estos documentos.

## Fallos

- Un servidor que no arranca o no responde pasa a FAILED, y sus herramientas quedan no disponibles; el resto sigue funcionando.
- La conexión se reintenta una vez, con espera de 0,2 s.
- Un 401 o 403 pasa la conexión a AUTH_REQUIRED.
- Si una definición difiere de la fijada, la conexión queda DEGRADED y la herramienta no está disponible hasta que se revisa de nuevo.
