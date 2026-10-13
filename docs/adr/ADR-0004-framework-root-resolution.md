# ADR-0004: Orden de resolución del root del framework

- Status: accepted (2026-10-13, PAL-005)
- Confidence: high
- Context: el root por defecto era el directorio padre del paquete; con
  `pip install .` (no editable) apuntaba a `site-packages` y todo comando fallaba.
- Options: (a) empaquetar todos los datos en la wheel — cambio mayor de layout;
  (b) descubrir el root; (c) exigir siempre `--root`.
- Decision: (b) en este orden: `--root`, `$PALLAQUINO_ROOT`, checkout del paquete si
  es un root válido, `./.pallaquino` o el primer padre que lo contenga. Un root
  inválido produce exit 2 y un mensaje con las tres formas de corregirlo.
- Consequences: comportamiento idéntico a 0.2.1 en instalaciones editables y desde
  el código fuente. Empaquetar los datos en la wheel queda para la publicación en PyPI.
- Reversal: restablecer `default=framework_root()` en el parser.
