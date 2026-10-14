# ADR-0012: Capa de abstracción de proveedores

- Status: accepted (2026-10-14, v0.4.0)
- Confidence: high para el contrato y la política; medium para Ollama (verificado contra un stub, no contra un Ollama real)
- Context: el pedido pide compatibilidad con OpenAI, Anthropic, Gemini y Ollama sin SDKs ficticios ni compatibilidad simulada.
- Options: (a) adaptadores para los cuatro sin poder verificarlos — riesgo de compatibilidad inventada; (b) SDKs oficiales — dependencias
  externas obligatorias; (c) contrato estable más los adaptadores verificables con la stdlib: `mock` (determinista) y `ollama` (HTTP local).
- Decision: (c). Contrato `Provider`: `capabilities`, `validate_config`, `complete`, `ProviderResponse` estructurada y `ProviderError`
  normalizado (`not_configured`, `auth`, `rate_limit`, `timeout`, `unavailable`, `invalid_response`, `budget_exceeded`, `cancelled`).
  - El uso de tokens lleva `verified` (solo si lo reporta el proveedor); el coste estimado y el facturado son campos distintos.
  - La configuración por proyecto vive en `governance/providers.json`.
  - El fallback solo ocurre ante errores de disponibilidad, solo hacia proveedores de `fallback.order`, y nunca de local a remoto sin
    `allow_cross_boundary`; `privacy.local_only` excluye remotos.
  - Hay presupuestos por ejecución y por tarea (este se conserva entre reintentos).
  - Los adaptadores comerciales no se incluyen hasta poder verificarlos con credenciales autorizadas; `validate_config` rechaza proveedores
    sin adaptador.
- Consequences: la suite completa corre offline. La ejecución con modelo real requiere un Ollama local o un adaptador futuro; el escenario de
  referencia informa "no ejecutado" en lugar de simularlo.
- Reversal: los adaptadores son módulos independientes registrados en `build_provider`.
