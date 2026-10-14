# Adaptador Git (`core.git.*`)

Código: `pallaquino_cli/integrations/git.py`. Se ejecuta `git` con un argv fijo, sin shell, con `GIT_TERMINAL_PROMPT=0`, sin helper de
credenciales y con `core.longpaths=true`.

| Herramienta | Operación | Política | `provides` | Resultado |
|---|---|---|---|---|
| `core.git.status` | READ_ONLY | contract | `git_status` | rama, `clean`, cambios (`index`, `worktree`, `path`) |
| `core.git.diff` | READ_ONLY | contract | `git_diff` | diff (staged o unstaged, `--stat`, una ruta), redactado |
| `core.git.log` | READ_ONLY | contract | `git_history` | commits (`sha`, `author`, `date`, `subject`); un repositorio sin commits da historial vacío |
| `core.git.branches` | READ_ONLY | contract | — | ramas locales con `current` y `head` |
| `core.git.show` | READ_ONLY | contract | — | un commit con estadísticas |
| `core.git.stage` | WRITE_OPERATION (GIT_WRITE) | grant | — | `git add -- <rutas>`, local y reversible con `git restore --staged` |

## Seguridad

- **Revisiones**: deben cumplir `^(?!-)[A-Za-z0-9._/~^@{}:-]{1,200}$`, así que una revisión no puede empezar por `-` (sin inyección de
  opciones).
- **Rutas**: se confinan al workspace y se pasan después de `--`.
- **Sin operaciones remotas ni destructivas**: no hay push, fetch, reset, rebase, clean ni borrado de ramas. `git_push` sigue siendo una
  herramienta gobernada de los contratos v2 sin ejecutor (ADR-0010).
- **Salida**: se limita a 200 000 caracteres y se redacta.

Tests: `tests/test_integrations.py::GitTest`.
