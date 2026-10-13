# ADR-0001: Separar validadores de integridad y de entorno

- Status: accepted (2026-10-13, PAL-005)
- Confidence: high
- Context: la suite fallaba en cualquier clon sin la identidad Git del mantenedor y
  por el paso del tiempo (snapshot de stack). Un test que depende del host o del
  reloj no detecta regresiones de código: produce ruido y bloquea a colaboradores.
- Options: (a) configurar la identidad dentro de los tests — muta el repositorio del
  usuario; (b) eliminar el check — debilita la política; (c) etiquetar cada check con
  `scope` y permitir excluir los de entorno — conserva la política y aísla los tests.
- Decision: (c). `validate_all(include_environment=True)` y `validate` mantienen el
  comportamiento anterior; `--integrity-only` excluye checks de entorno. La caducidad
  del stack se calcula con una fecha inyectable y se informa en `doctor`/`stack`.
- Consequences: CI sigue validando todo (configura la identidad); los tests prueban
  el check de autoría en un repositorio temporal.
- Reversal: quitar el campo `scope` y el flag; ningún dato persistido depende de ellos.
