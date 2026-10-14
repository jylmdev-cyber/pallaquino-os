# ADR-0005: Archivo de release determinista

- Status: accepted (2026-10-13, PAL-005)
- Confidence: medium (la salida DEFLATE puede variar entre versiones de zlib)
- Context: el ZIP incluía los `mtime` del checkout y los writers JSON emitían CRLF en
  Windows; el SHA-256 publicado no era reproducible.
- Options: (a) ZIP_STORED — determinista pero sin compresión; (b) DEFLATE con
  metadatos fijos; (c) tar.gz con `SOURCE_DATE_EPOCH`.
- Decision: (b): orden estable, `date_time` fijo (1980-01-01) o `SOURCE_DATE_EPOCH`,
  `create_system=3`, permisos `0644`/`0755` por shebang y escritura LF obligatoria.
- Consequences: dos builds del mismo contenido con la misma versión de Python/zlib
  tienen el mismo hash (probado). El hash de 0.3.0 difiere del de 0.2.1 por diseño.
- Reversal: volver a `zipfile.ZipFile.write`.
