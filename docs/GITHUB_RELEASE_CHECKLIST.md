# Checklist para publicar PALLAQUINO en GitHub

## 1. Crear el repositorio

- Usa visibilidad **Public**.
- No inicialices README, licencia ni `.gitignore`; ya existen localmente.
- Descripción sugerida: `Provider-neutral autonomous engineering OS for AI agents.`
- Topics sugeridos: `ai-agents`, `software-engineering`, `orchestration`,
  `devsecops`, `governance`, `python`, `multi-agent`, `llm`.

## 2. Metadata del repositorio

El slug configurado es `jylmdev-cyber/pallaquino-os`. Antes de cada release,
confirma que README, citation, changelog y badges continúen apuntando a este
repositorio.

## 3. Conectar y publicar

```bash
git branch -M main
git remote add origin https://github.com/jylmdev-cyber/pallaquino-os.git
git push -u origin main
```

Antes de ejecutar, confirma `git remote -v`, `git status` y la cuenta autenticada.
Este documento no debe usarse para sobrescribir un remoto existente sin revisar.

## 4. Configuración recomendada

- Habilita Issues y Discussions.
- Activa `Private vulnerability reporting` y `Dependabot alerts`.
- Protege `main`: PR obligatorio, CI requerido, conversaciones resueltas, sin force
  push y sin eliminación.
- Limita los permisos por defecto de Actions a lectura.
- Activa secret scanning y push protection si GitHub los ofrece para el repositorio.
- Crea labels: `bug`, `enhancement`, `security`, `documentation`, `dependencies`,
  `agents`, `skills`, `stack`, `good first issue`.

## 5. Primera release

- Verifica que CI esté verde.
- Crea el tag anotado `v0.2.1` y la GitHub Release.
- Adjunta `PALLAQUINO_autonomous_engineering_os.zip` y su `.sha256`.
- Copia las notas de `CHANGELOG.md` y verifica el checksum descargado.

```bash
git tag -a v0.2.1 -m "PALLAQUINO 0.2.1"
git push origin v0.2.1
```

No publiques el tag hasta que el commit final y los artefactos hayan sido
validados.

## 6. Siguientes mejoras

- Añadir `CODEOWNERS` cuando exista el usuario/equipo definitivo.
- Configurar OpenSSF Scorecard y CodeQL tras evaluar permisos y ruido.
- Firmar commits/tags y releases; documentar claves y rotación.
- Publicar documentación versionada y, posteriormente, el paquete en PyPI.
