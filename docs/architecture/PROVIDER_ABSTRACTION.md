# PALLAQUINO Provider Abstraction Layer

Estado: contrato, router, fallback y presupuestos **IMPLEMENTADOS**. Adaptadores: `mock` **IMPLEMENTADO**; `ollama` **IMPLEMENTADO, verificado
solo contra un servidor stub**. OpenAI, Anthropic y Gemini: **PLANIFICADOS**, sin código (ADR-0012).

## Contrato

```python
class Provider(Protocol):
    name: str
    boundary: str                     # "local" | "remote"
    def capabilities(self) -> dict    # structured_output, tools, streaming, boundary, simulated
    def validate_config(self) -> dict # {"ok": bool, ...}; no lanza
    def complete(self, request: ProviderRequest) -> ProviderResponse
```

`ProviderResponse` contiene: provider, model, text, structured (objeto JSON validado), usage, latency_ms y simulated. `Usage` lleva
`input_tokens`, `output_tokens`, `verified`, `cost_estimated` y `cost_verified`. Si el proveedor no informa el consumo, el estado es
"unverified" y el presupuesto lo cuenta en `unverified_calls`.

Errores normalizados (`ProviderError.kind`): `not_configured`, `auth`, `rate_limit` (con `retry_after`), `timeout`, `unavailable`,
`invalid_response`, `budget_exceeded` y `cancelled`. Son reintentables: `rate_limit`, `timeout` y `unavailable`.

## Configuración (`governance/providers.json`)

```json
{
  "default": "mock",
  "providers": {"mock": {"enabled": true, "responses_file": null},
                "ollama": {"enabled": false, "model": "llama3.1", "base_url": "http://127.0.0.1:11434"}},
  "fallback": {"order": [], "allow_cross_boundary": false},
  "privacy": {"local_only": true},
  "budgets": {"execution": {"max_calls": 200, "max_tokens": 400000, "max_cost": null}, "task": {"max_calls": 12}}
}
```

## Selección y fallback

- Candidatos: el proveedor preferido o por defecto, seguido de `fallback.order`. Se filtran los deshabilitados, los que no tienen salida
  estructurada y, con `privacy.local_only`, los remotos.
- El fallback solo ocurre ante `unavailable`, `rate_limit`, `timeout` o `not_configured`. Con `auth` o `invalid_response` no se cambia de
  proveedor.
- Nunca se cruza la frontera local→remoto sin `allow_cross_boundary: true`.
- Ollama se considera `local` solo si apunta a loopback (127.0.0.1, localhost o ::1).

## Ollama

Usa `GET /api/tags` y `POST /api/chat` con `stream: false` y `format: "json"`. Toma los tokens de `prompt_eval_count` y `eval_count`. El
coste estimado es 0 porque la inferencia es local; nunca se presenta como coste facturado.

Para activarlo: instala Ollama, ejecuta `ollama pull <modelo>`, pon `enabled: true` y el modelo en `providers.json`, y comprueba con
`pallaquino providers doctor`.

## Router de modelos (alcance real)

Hoy la selección combina capacidades (salida estructurada), privacidad, disponibilidad (`doctor`) y presupuesto. Todavía **no** considera
latencia histórica ni precio por token, porque no hay adaptadores comerciales que los informen.
