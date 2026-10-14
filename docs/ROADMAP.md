# Roadmap de PALLAQUINO

Los objetivos cuantitativos parten del baseline medido en
[`AUDIT_REPORT.md`](AUDIT_REPORT.md) §3. Ninguna fase comienza sin que la anterior
cumpla sus criterios de aceptación con evidencia.

## Fase 1 — Auditoría y estabilización (0.3.0) — COMPLETADA EN RAMA

Entregado: los 7 hallazgos HIGH y 6 MEDIUM corregidos con tests de regresión;
`security audit`, `init --dry-run`, `validate --integrity-only`; archivo
reproducible; CI con escaneo de secretos e instalación no editable.

Pendiente de aprobación humana: merge, tag `v0.3.0`, GitHub Release.

## Fase 1.1 — Verificación del stack (`PAL-006`, modo UPGRADE, autonomía SAFE)

- Re-verificar las 11 entradas de `stack_versions_verified.json` contra fuentes oficiales.
- Aceptación: `pallaquino stack` devuelve `ok: true`; cada fuente es HTTPS oficial.
- Dependencia: acceso web del agente; no requiere cambios de código.

## Fase 2 — Inteligencia operativa (0.4.0)

| Entrega | Dependencias | Criterios de aceptación |
|---|---|---|
| Contratos v2 de agentes/skills (entradas, salidas, herramientas, activación, éxito, casos de prueba) — **PAL-007-A hecho** (esquema, derivación, validación, carga controlada); **PAL-007-B hecho** (0 agentes y 0 skills inalcanzables; 13 contratos de rol curados; ADR-0009) | Fase 1 | Validador rechaza contratos incompletos; migración automática desde v1 sin perder campos |
| Orchestration Engine: `plan`/`run` con `run_id`, DAG, límites de concurrencia, timeouts, reintentos acotados, cancelación — **hecho en 0.4.0** (reanudación probada en `test_scheduler.RecoveryTests`; el escenario `evaluation/abrupt_session_recovery` no se automatizó) | Contratos v2, locks 0.3.0 | Ciclos y dependencias bloqueadas detectados; una ejecución interrumpida se reanuda desde su checkpoint en los escenarios de `evaluation/abrupt_session_recovery` |
| Project Memory (SQLite + JSON, aislamiento por proyecto, retención) — **hecho en 0.4.0** | `instance_state` 0.3.0 | Consultas sin cruzar proyectos; borrado por política probado; el contenido recuperado se etiqueta como no confiable |
| Checkpoints a prueba de manipulación (cadena de hashes) — **parcial**: checksum por documento sin clave; cadena o HMAC pendiente para 0.5.0 | — | Alterar un checkpoint intermedio invalida la cadena |
| Interfaz de proveedores + adaptador "null"/local — **hecho en 0.4.0** (`mock` y Ollama) | — | Descubrimiento de capacidades, timeouts, presupuesto de tokens y registro sin secretos, probados sin red |

Objetivos: cobertura ≥ 90 % en cada módulo nuevo (cumplido: 94,4 % total, todos ≥ 90 %); suite < 15 s (no cumplido en Windows: 48 s con 154 tests; pendiente medir en CI Linux).

## Fase 3 — Extensibilidad (0.5.0) — CANDIDATO LOCAL (PAL-011)

Entregado (ver `docs/releases/RELEASE_V050.md`): sistema de plugins con confianza por hash y aislamiento por proceso, cliente MCP
2026-07-28, registro y pasarelas de herramientas, OAuth, adaptadores de filesystem, Git, SQLite y GitHub, SDK y demo end-to-end. Siguen
pendientes el ejecutor externo, los adaptadores comerciales y la optimización del scheduler (ver `docs/roadmap/ROADMAP_V050_TO_V060.md`).

Planteamiento original:

- Extension System: manifiesto validado, versión y compatibilidad, permisos por
  herramienta (denegación por defecto), procedencia (hash fijado), activar/desactivar.
- Adaptadores Git y sistema de archivos; MCP solo para servidores autorizados,
  distinguiendo autenticación STDIO y HTTP según la especificación vigente.
- Aceptación: un plugin sin política de confianza no se ejecuta; tests de inyección
  de prompts y uso indebido de herramientas en `evaluation/`.

## Fase 4 — Automatización de ingeniería (0.6.0)

- Project Factory con perfiles verificables (Nuxt, Django/DRF, Laravel, ASP.NET
  Core, Next.js, FastAPI, SaaS multi-tenant, ERP, POS, IA). Cada plantilla justifica
  cada tecnología y genera tests y CI que pasan en el primer commit.
- Quality Gate Engine configurado por riesgo con resultados asociados a `run_id`.
- Aceptación: cada plantilla generada pasa su propia CI en un contenedor limpio.

## Fase 5 — Experiencia visual (0.7.0)

- API local opcional y Control Center web (proyectos, grafo, ejecuciones, gates,
  aprobaciones, costos), con convenciones OpenTelemetry. El motor no depende de la UI.

## Fuera de alcance permanente

Despliegue autónomo a producción, almacenamiento de secretos y omisión de políticas.
