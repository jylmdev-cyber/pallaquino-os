# PALLAQUINO Autonomous Engineering OS

<p align="center">
  <strong>Framework portable de gobernanza, orquestación y ejecución para agentes de ingeniería de software.</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.4.0-0A7BBB">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Agents" src="https://img.shields.io/badge/agents-59-7B61FF">
  <img alt="Skills" src="https://img.shields.io/badge/skills-90-00A67E">
  <img alt="Technologies" src="https://img.shields.io/badge/technologies-46-F97316">
  <img alt="Tests" src="https://img.shields.io/badge/tests-154%20passing-2EA44F">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
  <img alt="Provider neutral" src="https://img.shields.io/badge/AI-provider--neutral-111827">
  <a href="https://github.com/jylmdev-cyber/pallaquino-os/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jylmdev-cyber/pallaquino-os/actions/workflows/ci.yml/badge.svg"></a>
</p>

PALLAQUINO convierte una solicitud humana en un flujo de ingeniería trazable:
descubre el repositorio, clasifica el riesgo, selecciona agentes y skills, construye
un grafo de tareas, ejecuta gates de calidad y conserva evidencia, checkpoints y
handoffs. No es solamente una colección de prompts: incluye CLI en Python,
registros validados, políticas, evaluaciones y empaquetado reproducible.

> **Estado (0.4.0):** el framework es utilizable y auto-validable. El snapshot de
> versiones se re-verificó el 14 de octubre de 2026 contra fuentes oficiales (`PAL-006`)
> y caduca a los 30 días.
> Todo perfil está marcado `VERIFY_BEFORE_USE`. Lo implementado, experimental y
> planificado se distingue en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Capacidades

- 59 agentes especializados para producto, arquitectura, frontend, backend,
  seguridad, datos, plataforma, SRE, IA, móvil y dominios de negocio.
- 90 skills version-agnostic cargables según la intención, riesgo y tecnología.
- 46 tecnologías catalogadas y 6 perfiles de arquitectura adoptables.
- Pipeline estricto con análisis, planificación, implementación, revisión,
  pruebas, seguridad, documentación, checkpoint y handoff.
- Clasificación de riesgo `LOW`, `MEDIUM`, `HIGH` y `CRITICAL` con gates
  proporcionales.
- Validación cruzada de agentes, skills, rutas, pipeline, continuidad y gobernanza.
- Instalación aislada por proyecto: `init` genera estado limpio y admite `--dry-run`.
- Escaneo de secretos de solo lectura (`pallaquino security audit`) y redacción de
  secretos en la evidencia.
- Archivo de release reproducible: mismo contenido, mismo SHA-256.
- **Motor de orquestación (0.4.0)**: análisis de intención, router de agentes explicable,
  planificador con DAG validado, scheduler concurrente con reintentos, timeouts,
  pausa, cancelación, aprobaciones y reanudación tras fallos; `plan` y `run` separados.
- **Memoria de proyecto** en SQLite: aislada por proyecto, con secretos redactados,
  integridad verificada y contenido recuperado tratado como no confiable.
- **Proveedores**: contrato estable, adaptador `mock` determinista y adaptador local
  Ollama; fallback solo autorizado y sin enviar datos a servicios remotos sin permiso.
- Neutralidad de proveedor: el agente activo (Codex, ChatGPT, Claude, Gemini u otro)
  lee las políticas y usa el CLI. Sin un proveedor real, las tareas de agente se
  simulan y se marcan como simuladas.
- Dependencias de ejecución: únicamente Python Standard Library.

## Inicio rápido

Requisitos: Git y Python 3.11 o superior.

```bash
git clone https://github.com/jylmdev-cyber/pallaquino-os.git
cd pallaquino-os/universal_ai_fullstack_orchestrator

python -m pallaquino_cli doctor
python -m pallaquino_cli validate --json
python -m pallaquino_cli analyze
python -m pallaquino_cli risk "agregar autenticación basada en roles"
python -m pallaquino_cli security audit --target ..
```

Instalación opcional (editable o normal):

```bash
python -m pip install -e ./universal_ai_fullstack_orchestrator
pallaquino --help
```

Con una instalación normal (`pip install ./universal_ai_fullstack_orchestrator`),
`pallaquino` localiza el framework con `--root`, `$PALLAQUINO_ROOT` o el
directorio `.pallaquino/` del proyecto actual.

Para incorporar el framework en otro proyecto sin sobrescribir archivos existentes:

```bash
python -m pallaquino_cli init --target /ruta/al/proyecto --dry-run --json
python -m pallaquino_cli init --target /ruta/al/proyecto --json
```

Demostración reproducible paso a paso: [`docs/DEMO.md`](docs/DEMO.md).

Después, entrega
[`AI_ENTRYPOINT.md`](universal_ai_fullstack_orchestrator/AI_ENTRYPOINT.md) al agente
activo y utiliza el
[`tutorial de prompts`](universal_ai_fullstack_orchestrator/docs/TUTORIAL_DE_PROMPTS.md).

## Cómo funciona

```text
pallaquino plan "Agregar un módulo de inventario"     # intención → plan (DAG) validado; no ejecuta
pallaquino run --plan <plan_id>                       # scheduler multiagente con locks y reintentos
pallaquino status --execution <execution_id>          # estado, métricas y aprobaciones pendientes
pallaquino executions report <execution_id>           # solicitud → plan → agente → validación → resultado
pallaquino memory search arquitectura                 # memoria persistente (datos no confiables)
```

Arquitectura: [`docs/architecture/ORCHESTRATION_ENGINE.md`](docs/architecture/ORCHESTRATION_ENGINE.md).
Primer uso guiado: [`docs/tutorials/FIRST_MULTI_AGENT_EXECUTION.md`](docs/tutorials/FIRST_MULTI_AGENT_EXECUTION.md).

La política superior vive en
[`AI_ENTRYPOINT.md`](universal_ai_fullstack_orchestrator/AI_ENTRYPOINT.md). Los
registros son la fuente de verdad para routing y validación; los nombres de skills
nunca seleccionan por sí solos una versión tecnológica.

## Stack tecnológico

### Baseline verificado

| Tecnología | Versión | Estado | Uso |
|---|---:|---|---|
| Python | 3.14.8 | estable | CLI, validadores y automatización |
| Node.js | 24.21.0 | Active LTS | runtime web de referencia |
| TypeScript | 6.0.3 | compatible estable | tipado frontend |
| .NET SDK / Runtime | 10.0.402 / 10.0.13 | LTS | servicios empresariales |
| Django | 5.2.18 | LTS | backend Python |
| Nuxt | 4.6.1 | estable | frontend Vue |
| PostgreSQL | 18.6 | estable | persistencia relacional |
| Docker Engine / Compose | 29.9.0 / 5.6.0 | estable | contenedores locales |
| Ubuntu | 26.04.1 | LTS | sistema operativo de referencia |

Las fuentes oficiales, fecha de verificación y notas de compatibilidad están en
[`stack_versions_verified.json`](universal_ai_fullstack_orchestrator/registry/stack_versions_verified.json).
El snapshot caduca a los 30 días y debe actualizarse antes de iniciar un proyecto
nuevo o una actualización mayor.

### Catálogo ampliado

<p>
  <img alt="React" src="https://img.shields.io/badge/React-available-61DAFB?logo=react&logoColor=111827">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-available-000000?logo=nextdotjs&logoColor=white">
  <img alt="Angular" src="https://img.shields.io/badge/Angular-available-DD0031?logo=angular&logoColor=white">
  <img alt="Spring Boot" src="https://img.shields.io/badge/Spring_Boot-available-6DB33F?logo=springboot&logoColor=white">
  <img alt="Go" src="https://img.shields.io/badge/Go-available-00ADD8?logo=go&logoColor=white">
  <img alt="Laravel" src="https://img.shields.io/badge/Laravel-available-FF2D20?logo=laravel&logoColor=white">
  <img alt="Flutter" src="https://img.shields.io/badge/Flutter-available-02569B?logo=flutter&logoColor=white">
  <img alt="Kubernetes" src="https://img.shields.io/badge/Kubernetes-available-326CE5?logo=kubernetes&logoColor=white">
  <img alt="Terraform" src="https://img.shields.io/badge/Terraform-available-844FBA?logo=terraform&logoColor=white">
  <img alt="Kafka" src="https://img.shields.io/badge/Apache_Kafka-available-231F20?logo=apachekafka&logoColor=white">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-available-DC382D?logo=redis&logoColor=white">
  <img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-available-47A248?logo=mongodb&logoColor=white">
</p>

También se incluyen AWS, Azure, GCP, Helm, Argo CD, RabbitMQ, SQL Server,
MySQL, OpenSearch, ClickHouse, React Native, SwiftUI, Kotlin, Playwright, OIDC,
MCP, RAG, bases vectoriales, evaluación de LLMs y seguridad de prompts. Consulta
el [`catálogo completo`](universal_ai_fullstack_orchestrator/registry/technology_catalog.json)
y la
[`guía de expansión`](universal_ai_fullstack_orchestrator/docs/TECHNOLOGY_EXPANSION.md).

### Perfiles disponibles

| Perfil | Enfoque | Gates destacados |
|---|---|---|
| `nextjs_saas` | SaaS web con identidad y datos | API, accesibilidad, seguridad, build |
| `spring_enterprise` | servicios Java orientados a eventos | API, eventos, seguridad, build |
| `dotnet_enterprise` | plataforma empresarial .NET | API, seguridad, build |
| `cloud_native_microservices` | microservicios y GitOps | IaC, IAM, eventos, recuperación |
| `flutter_mobile_backend` | app móvil y backend Python | seguridad móvil, API, seguridad |
| `ai_rag_platform` | RAG y herramientas de IA | evals, inyección, permisos, grounding, privacidad |

Todos comienzan en `VERIFY_BEFORE_USE`. Adoptar un perfil significa verificar
versiones oficiales, compatibilidad, amenazas, datos y estrategia de rollback.

## Estructura del repositorio

```text
.
├── .github/                             # CI, Dependabot y plantillas
├── docs/                                # auditoría, arquitectura, roadmap, ADR, demo
├── scripts/                             # utilidades del repositorio
├── universal_ai_fullstack_orchestrator/
│   ├── agents/                          # contratos de agentes
│   ├── skills/                          # procedimientos especializados
│   ├── registry/                        # fuentes de verdad y routing
│   ├── pipeline/                        # estados y transiciones
│   ├── governance/                      # políticas superiores
│   ├── evaluation/                      # casos dorados
│   ├── pallaquino_cli/                  # CLI sin dependencias externas
│   ├── scripts/                         # validación y release
│   └── tests/                           # suite automatizada
├── PALLAQUINO_autonomous_engineering_os.zip
└── PALLAQUINO_autonomous_engineering_os.sha256
```

## Desarrollo y validación

```bash
cd universal_ai_fullstack_orchestrator

python -m unittest discover -s tests -v
python scripts/validate_all.py            # colaboradores: pallaquino validate --integrity-only
python scripts/architecture_fitness.py
python -m pallaquino_cli security audit --target ..
python scripts/package_release.py
python scripts/verify_zip_integrity.py
```

El [workflow de GitHub Actions](https://github.com/jylmdev-cyber/pallaquino-os/actions/workflows/ci.yml)
ejecuta la suite en Python 3.11 y 3.14, valida la arquitectura, escanea secretos,
prueba la instalación no editable y comprueba el ZIP.

## Configurar la identidad de Git

La identidad esperada de cada proyecto vive en
`universal_ai_fullstack_orchestrator/governance/git_identity.json`
(`jimdev <jylmdev@gmail.com>` por defecto y en este repositorio):

```bash
cd universal_ai_fullstack_orchestrator
python -m pallaquino_cli identity                        # muestra esperada vs. local
python -m pallaquino_cli identity --apply-local          # la aplica solo en la config local
python -m pallaquino_cli identity --name "Equipo" --email "equipo@example.com"  # otro proyecto
```

La utilidad de la raíz escribe **solo** `user.name` y `user.email` en la configuración
local del repositorio; no modifica la identidad global del equipo:

```bash
python scripts/configure_git_identity.py \
  --name "Tu Nombre" \
  --email "tu-correo@example.com"

python scripts/configure_git_identity.py --show
```

## Apoya el crecimiento de PALLAQUINO

PALLAQUINO es un proyecto abierto orientado a construir mejores herramientas de
ingeniería para la comunidad. Si el framework te resulta útil, puedes colaborar
voluntariamente mediante PayPal para apoyar su mantenimiento, documentación,
infraestructura, pruebas y nuevos ejemplos.

<p align="center">
  <a href="https://www.paypal.com/donate/?hosted_button_id=25WTYKQWHSTWW">
    <img alt="Apoyar mediante PayPal" src="https://img.shields.io/badge/Apoyar-PayPal-003087?logo=paypal&logoColor=white">
  </a>
  <br><br>
  <a href="https://www.paypal.com/donate/?hosted_button_id=25WTYKQWHSTWW">
    <img alt="Código QR para apoyar PALLAQUINO mediante PayPal" src="docs/assets/paypal-donation-qr.png" width="180">
  </a>
</p>

**Correo de PayPal:** `jimmy.lingan@outlook.com`

Puedes seleccionar el botón o escanear el código QR para abrir la página oficial
de aportes de PALLAQUINO en PayPal.

Al realizar un aporte, verifica que el destinatario coincida exactamente con ese
correo. Las contribuciones son opcionales, no representan una compra y no otorgan
prioridad, control ni privilegios especiales sobre las decisiones del proyecto.

## Comunidad y seguridad

Antes de contribuir, consulta [`CONTRIBUTING.md`](CONTRIBUTING.md),
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) y [`SUPPORT.md`](SUPPORT.md).
Las vulnerabilidades no deben publicarse en Issues; utiliza el proceso privado de
[`SECURITY.md`](SECURITY.md).

## Roadmap

La evolución por fases (orquestación, memoria, proveedores, extensiones, Project
Factory y Control Center), con dependencias y criterios de aceptación, está en
[`docs/ROADMAP.md`](docs/ROADMAP.md). El diagnóstico que la motiva está en
[`docs/AUDIT_REPORT.md`](docs/AUDIT_REPORT.md) y las decisiones en
[`docs/adr/`](docs/adr/). La evolución hacia 0.5.0 está en
[`docs/roadmap/ROADMAP_V040_TO_V050.md`](docs/roadmap/ROADMAP_V040_TO_V050.md). Para actualizar desde
versiones anteriores, consulta [`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md).

## Licencia

Distribuido bajo la [licencia MIT](LICENSE). Copyright © 2026 jimdev.
