# Guía de desarrollo de plugins (PALLAQUINO Extension Development Kit)

API pública: `pallaquino_cli.sdk` (SDK 1.0.0, PALLAQUINO 0.5.x). Ejemplo de referencia:
[`examples/pallaquino-example-plugin`](../../universal_ai_fullstack_orchestrator/examples/pallaquino-example-plugin).

## Interfaz

```python
from pallaquino_cli.sdk import Plugin, ToolCall

class MyPlugin(Plugin):
    def configure(self, config: dict) -> None: ...      # configuración ya validada por el host
    def initialize(self, context: dict) -> None: ...    # {workspace, plugin_id, version}; si lanza una excepción, el plugin queda FAILED
    def capabilities(self) -> dict: ...                 # informativo
    def health(self) -> dict: ...                       # {"ok": bool, ...}; se lee como recurso plugin://health
    def shutdown(self) -> None: ...                     # al cerrarse stdin; libera recursos

plugin = MyPlugin()

@plugin.tool("file_stats")                              # el nombre debe estar declarado en plugin.toml
def file_stats(args: dict, call: ToolCall) -> dict:
    path = call.resolve(args["path"])                   # confinado al workspace; fuera de él lanza PermissionError
    call.progress(0.5, 1.0, "leyendo")                  # notificación de progreso opcional
    if call.cancelled.is_set(): return {}               # cancelación cooperativa
    return {"path": args["path"], "lines": len(path.read_text().splitlines())}
```

- Lo que devuelve la función es `structuredContent`, y además su JSON va como texto. Si la herramienta declara `output_schema`, el resultado
  debe cumplirlo.
- Para un error de ejecución que el modelo pueda corregir, lanza una excepción o devuelve `ToolResult(is_error=True)`.

## Reglas que el host comprueba

1. Las herramientas implementadas y las declaradas deben coincidir exactamente; si no, el runner no arranca.
2. Los esquemas vivos deben ser iguales a los del manifiesto.
3. Cada capacidad de una herramienta debe estar en `permissions.requested`, y estas, en lo aprobado con `plugins trust`.
4. La compatibilidad (`compatibility.pallaquino`) debe incluir la versión instalada.
5. Cualquier cambio en el código cambia el hash: el plugin queda en cuarentena hasta que se vuelve a aprobar.

## Flujo

```bash
pallaquino plugin create ./my-plugin --id acme.text_tools --author "Ana" --write   # sin --write es dry run
cd my-plugin && python -m unittest discover -s tests -v                          # PluginHarness: proceso aislado real
pallaquino plugin validate src/acme_text_tools                                   # manifiesto + hash de contenido
pallaquino plugin test src/acme_text_tools                                       # arranque aislado, catálogo, health
pallaquino plugins install src/acme_text_tools                                   # copia; nada se ejecuta
pallaquino plugins trust acme.text_tools --approved-by "Ana"                     # revisión humana del hash
pallaquino plugins enable acme.text_tools
pallaquino permissions grant 'plugin.acme.text_tools.*' --principal project_analyzer
```

## Distribución

`pyproject.toml` declara el entry point `[project.entry-points."pallaquino.plugins"]` e incluye `plugin.toml` como package data. Un
`pip install` del paquete lo hace visible para `pallaquino plugins discover`, que no lo importa. Aun así, pasa por trust y enable antes de
ejecutarse.

## Pruebas

`pallaquino_cli.sdk.testing.PluginHarness(plugin_dir, workspace=..., config=...)` arranca el plugin como lo hace PALLAQUINO: `python -I`,
entorno saneado, MCP stdio. Expone `tools()`, `call()`, `call_raw()` y `health()`.
