# Contribuir a PALLAQUINO

Gracias por ayudar a mejorar PALLAQUINO. Este repositorio prioriza cambios
pequeños, trazables, provider-neutral y acompañados por evidencia.

## Antes de comenzar

1. Busca un Issue existente o crea uno describiendo problema, alcance y criterio
   de aceptación.
2. Para cambios de arquitectura, seguridad, registros o contratos públicos,
   acuerda primero el diseño en el Issue.
3. No incluyas secretos, datos personales, credenciales ni contenido de terceros
   sin una licencia compatible.

## Entorno local

```bash
git clone <URL-DEL-FORK>
cd pallaquino-os
python scripts/configure_git_identity.py --name "Tu Nombre" --email "tu@email.com"
cd universal_ai_fullstack_orchestrator
python -m unittest discover -s tests -v
python scripts/validate_all.py
```

Python 3.11+ es suficiente para desarrollar. El framework no tiene dependencias
de runtime fuera de la Standard Library.

## Flujo de cambio

1. Crea una rama descriptiva: `feat/nombre`, `fix/nombre` o `docs/nombre`.
2. Conserva la compatibilidad de los registros y actualiza referencias cruzadas.
3. Añade o ajusta tests y casos dorados cuando cambie routing, riesgo o gates.
4. Documenta decisiones y limitaciones. Una tecnología nueva debe quedar
   `VERIFY_BEFORE_USE` hasta verificar fuentes oficiales.
5. Ejecuta las validaciones completas.
6. Abre un Pull Request usando la plantilla y enlaza el Issue.

## Validación requerida

```bash
python -m unittest discover -s tests -v
python scripts/validate_all.py
python scripts/architecture_fitness.py
python -m compileall -q pallaquino_cli scripts tests
```

Si el contenido distribuible cambió:

```bash
python scripts/package_release.py
python scripts/verify_zip_integrity.py
```

## Convenciones

- Python: código claro, tipado cuando aporte precisión y compatibilidad con 3.11+.
- JSON: UTF-8, indentación de dos espacios y claves estables.
- Markdown: encabezados jerárquicos, enlaces relativos y ejemplos ejecutables.
- Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `build:`,
  `ci:` o `chore:`.
- PRs: un propósito principal; evita cambios mecánicos no relacionados.

## Qué debe explicar un Pull Request

- Qué problema resuelve y por qué.
- Qué archivos, contratos y rutas afecta.
- Riesgos, seguridad, migración y rollback.
- Comandos ejecutados y resultado de los gates.
- Capturas o evidencia cuando cambie una experiencia visible.

Al participar aceptas el [Código de Conducta](CODE_OF_CONDUCT.md). Para reportes
de seguridad utiliza exclusivamente [SECURITY.md](SECURITY.md).

