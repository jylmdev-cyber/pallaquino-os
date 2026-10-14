# ADR-0016: Credenciales por referencia, OAuth 2.1 según MCP 2026-07-28 y política de red anti-SSRF

- Status: accepted (2026-10-14, v0.5.0)
- Confidence: high para las reglas verificables (discovery, PKCE, `resource`, `iss`, aislamiento por emisor y SSRF); medium para la
  interoperabilidad con proveedores de identidad reales, probada solo contra un stub
- Context:
  - Los servidores MCP remotos usan OAuth 2.1, con descubrimiento de metadatos RFC 9728 y RFC 8414/OIDC, PKCE, RFC 8707 y RFC 9207.
  - El pedido prohíbe exponer credenciales al modelo y reutilizarlas entre servidores. También pide no implementar OAuth "desde cero" si hay
    una biblioteca madura compatible.
- Options:
  - (a) authlib o el cliente OAuth del SDK MCP: maduros, pero son dependencias externas;
  - (b) implementar solo la parte cliente que exige la especificación MCP (descubrimiento, validaciones, URL de autorización, intercambio de
    código, refresh y revocación), con la stdlib y sin criptografía propia;
  - (c) no soportar OAuth: deja fuera los servidores remotos protegidos.
- Decision: (b).
  - No hay criptografía propia: PKCE usa `secrets` y `hashlib`, y el transporte, `ssl` con verificación de certificados.
  - No se implementa Dynamic Client Registration, en desuso en 2026-07-28. El cliente está preregistrado o usa una URL de Client ID Metadata
    Document.
  - **Credenciales**:
    - se referencian como `env:VAR` (servidores stdio y adaptadores, como pide la especificación) o `vault:<servidor>`;
    - el vault guarda cada token por (proyecto, servidor, emisor) y nunca lo entrega a otro servidor ni a otro emisor;
    - usa el keyring del sistema si `keyring` está instalado y `PALLAQUINO_USE_KEYRING=1`; si no, un JSON fuera del workspace protegido solo
      por los permisos del sistema de archivos. Ese archivo no está cifrado, y `describe()` lo advierte.
  - **Flujo nativo** (`pallaquino mcp auth`, RFC 8252): callback de un solo uso en 127.0.0.1, validación de `state` e `iss` antes de enviar
    el código, PKCE S256 obligatorio (si el AS no lo anuncia, se rechaza) y `resource` canónico en la autorización y en el token. Step-up
    con la unión de los scopes ya concedidos y los nuevos.
  - **Política de red** (`mcp/netpolicy.py`):
    - solo HTTPS; HTTP únicamente a loopback y con permiso explícito;
    - sin credenciales ni fragmentos en la URL;
    - se rechazan direcciones privadas, loopback, link-local (metadatos cloud), multicast, reservadas y CGNAT;
    - la conexión se fija a la IP comprobada, contra el DNS rebinding;
    - no se siguen redirecciones; el tamaño de respuesta está limitado.
- Consequences:
  - Los tokens no aparecen en configuración, eventos, prompts ni argumentos: la redacción y las referencias se prueban en la suite.
  - El vault en archivo es una limitación declarada; la recomendación es usar `env:` o keyring.
- Reversal: `CredentialStore` y las funciones de `auth.py` son reemplazables por un adaptador de una biblioteca OAuth sin cambiar el
  registro de conexiones.
