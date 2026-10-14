# Tutorial: crear y habilitar el primer plugin

Requisitos: PALLAQUINO 0.5.x instalado (`pip install -e universal_ai_fullstack_orchestrator`) y un proyecto con `pallaquino init`. Los
resultados mostrados se obtuvieron el 2026-10-14 en Windows con Python 3.11.

> En un proyecto inicializado, ejecuta los comandos con `--root .pallaquino` o con `PALLAQUINO_ROOT` exportado. Con una instalación
> editable, `pallaquino` resuelve antes el checkout del paquete que `./.pallaquino` (ADR-0004).

## 1. Generar el esqueleto

```bash
pallaquino plugin create ./my-plugin --id acme.text_tools --author Ana          # dry run: muestra los archivos
pallaquino plugin create ./my-plugin --id acme.text_tools --author Ana --write
```

Archivos generados:

- `pyproject.toml`, con el entry point `pallaquino.plugins`;
- `README.md`;
- `src/acme_text_tools/plugin.toml`, el manifiesto;
- `src/acme_text_tools/__init__.py`, con la herramienta `hello`;
- `tests/test_plugin.py`;
- `examples/README.md`.

## 2. Implementar y declarar

Cada herramienta se declara en `plugin.toml` (esquema, capacidades, operación) y se implementa con `@plugin.tool("nombre")`. Ver la
[guía](../sdk/PLUGIN_DEVELOPMENT_GUIDE.md) y la [referencia del manifiesto](../sdk/PLUGIN_MANIFEST_REFERENCE.md).

## 3. Probar aislado

```bash
cd my-plugin && python -m unittest discover -s tests -v      # PluginHarness: subproceso python -I, MCP stdio
pallaquino plugin validate src/acme_text_tools               # {"ok": true, "content_hash": "fbd90393..."}
pallaquino plugin test src/acme_text_tools                   # {"ok": true, "tools": ["hello"], "health": {"ok": true}, "isolated": true}
```

## 4. Instalar, revisar y habilitar

```bash
pallaquino plugins install src/acme_text_tools               # state INSTALLED: copiado en plugins/acme.text_tools/0.1.0/, nada ejecutado
pallaquino plugins enable acme.text_tools                    # exit 1: "a plugin without a trust policy never executes"
pallaquino plugins trust acme.text_tools --approved-by Ana   # registra el hash y allowed_capabilities ["FILE_READ"]
pallaquino plugins enable acme.text_tools                    # state ENABLED
```

## 5. Autorizar y usar

```bash
pallaquino tools run plugin.acme.text_tools.hello --args '{"name":"Ana"}'   # DENIED (exit 5): confiable no es autorizado
pallaquino permissions grant 'plugin.acme.text_tools.*'
pallaquino tools run plugin.acme.text_tools.hello --args '{"name":"Ana"}'   # COMPLETED {"greeting": "Hello, Ana!"}
pallaquino plugins list                                                     # state ACTIVE, trusted true
```

## 6. Modificar, actualizar o retirar

- Si cambias el código instalado, el hash ya no coincide: `enable` o `activate` lo pasan a QUARANTINED. Revísalo y vuelve a ejecutar
  `plugins trust`.
- `plugins update <dir>` instala una versión mayor y restaura la anterior si falla. `plugins rollback <id>` vuelve atrás manualmente.
- `plugins uninstall <id> --yes` borra solo `plugins/<id>/`.
