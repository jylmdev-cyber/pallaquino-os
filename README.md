# PALLAQUINO Autonomous Engineering OS

<p align="center">
  <strong>Framework portable de gobernanza, orquestación y ejecución para agentes de ingeniería de software.</strong>
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.2.1-0A7BBB">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Agents" src="https://img.shields.io/badge/agents-59-7B61FF">
  <img alt="Skills" src="https://img.shields.io/badge/skills-90-00A67E">
  <img alt="Technologies" src="https://img.shields.io/badge/technologies-46-F97316">
  <img alt="Tests" src="https://img.shields.io/badge/tests-18%20passing-2EA44F">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
  <img alt="Provider neutral" src="https://img.shields.io/badge/AI-provider--neutral-111827">
</p>

PALLAQUINO convierte una solicitud humana en un flujo de ingeniería trazable:
descubre el repositorio, clasifica el riesgo, selecciona agentes y skills, construye
un grafo de tareas, ejecuta gates de calidad y conserva evidencia, checkpoints y
handoffs. No es solamente una colección de prompts: incluye CLI en Python,
registros validados, políticas, evaluaciones y empaquetado reproducible.

> **Estado:** el framework es utilizable y auto-validable. Las versiones concretas
> del baseline se verificaron el 31 de agosto de 2026. Todo perfil adicional está
> marcado `VERIFY_BEFORE_USE` hasta auditar versiones y compatibilidad para el
> proyecto que lo adopte.

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
- Neutralidad de proveedor: Codex, ChatGPT, Claude, Gemini, Mistral, Grok u otro.
- Dependencias de ejecución: únicamente Python Standard Library.

## Inicio rápido

Requisitos: Git y Python 3.11 o superior.

```bash
git clone <URL-DE-TU-REPOSITORIO>
cd pallaquino-os/universal_ai_fullstack_orchestrator

python -m pallaquino_cli doctor
python -m pallaquino_cli validate --json
python -m pallaquino_cli analyze
python -m pallaquino_cli risk "agregar autenticación basada en roles"
```

Instalación editable opcional:

```bash
python -m pip install -e ./universal_ai_fullstack_orchestrator
pallaquino --help
```

Para incorporar el framework en otro proyecto sin sobrescribir archivos existentes:

```bash
python -m pallaquino_cli init --target /ruta/al/proyecto --json
```

Después, entrega
[`AI_ENTRYPOINT.md`](universal_ai_fullstack_orchestrator/AI_ENTRYPOINT.md) al agente
activo y utiliza el
[`tutorial de prompts`](universal_ai_fullstack_orchestrator/docs/TUTORIAL_DE_PROMPTS.md).

## Cómo funciona

```text
Solicitud
   │
   ├─ Descubrimiento del repositorio y capacidades del proveedor
   ├─ Clasificación de intención, riesgo y alcance
   ├─ Selección de agentes, skills y gates
   ├─ Grafo de tareas + locks + ejecución controlada
   ├─ Tests, seguridad, revisión y evidencia
   └─ Checkpoint, release y handoff recuperable
```

La política superior vive en
[`AI_ENTRYPOINT.md`](universal_ai_fullstack_orchestrator/AI_ENTRYPOINT.md). Los
registros son la fuente de verdad para routing y validación; los nombres de skills
nunca seleccionan por sí solos una versión tecnológica.

## Stack tecnológico

### Baseline verificado

| Tecnología | Versión | Estado | Uso |
|---|---:|---|---|
| Python | 3.14.7 | estable | CLI, validadores y automatización |
| Node.js | 24.20.0 | Active LTS | runtime web de referencia |
| TypeScript | 6.0.3 | compatible estable | tipado frontend |
| .NET SDK / Runtime | 10.0.400 / 10.0.11 | LTS | servicios empresariales |
| Django | 5.2.17 | LTS | backend Python |
| Nuxt | 4.5.2 | estable | frontend Vue |
| PostgreSQL | 18.6 | estable | persistencia relacional |
| Docker Engine / Compose | 29.7.2 / 5.5.0 | estable | contenedores locales |
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
├── docs/                                # documentación pública del repositorio
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
python scripts/validate_all.py
python scripts/architecture_fitness.py
python scripts/package_release.py
python scripts/verify_zip_integrity.py
```

El workflow de GitHub Actions ejecuta la suite en Python 3.11 y 3.14, valida la
arquitectura y comprueba el ZIP. Al crear el repositorio remoto, reemplaza
`OWNER/REPOSITORY` en el siguiente badge y agrégalo a esta cabecera:

```markdown
[![CI](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPOSITORY/actions/workflows/ci.yml)
```

## Configurar la identidad de Git

La utilidad escribe **solo** `user.name` y `user.email` en la configuración local
del repositorio; no modifica la identidad global del equipo:

```bash
python scripts/configure_git_identity.py \
  --name "Tu Nombre" \
  --email "tu-correo@example.com"

python scripts/configure_git_identity.py --show
```

## Comunidad y seguridad

Antes de contribuir, consulta [`CONTRIBUTING.md`](CONTRIBUTING.md),
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) y [`SUPPORT.md`](SUPPORT.md).
Las vulnerabilidades no deben publicarse en Issues; utiliza el proceso privado de
[`SECURITY.md`](SECURITY.md).

## Roadmap sugerido

- Publicar el paquete en PyPI y firmar artefactos de release con Sigstore.
- Añadir un esquema JSON formal para cada registro público.
- Incorporar cobertura de tests, lint estático y escaneo de secretos en CI.
- Probar perfiles contra repositorios de referencia ejecutables.
- Generar documentación web versionada y ejemplos completos por proveedor.
- Activar GitHub Discussions y protección de la rama principal.

## Licencia

Distribuido bajo la [licencia MIT](LICENSE). Copyright © 2026 jimdev.
