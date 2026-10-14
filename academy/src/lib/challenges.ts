/** Guided challenges for the terminal playground. Each step names the commands it accepts and explains the result. */
import { REPO_URL, cliArguments, tokenize } from './terminal';

export interface ChallengeStep {
	instruction: string;
	hint: string;
	accepts: (input: string) => boolean;
	explanation: string;
}

export interface Challenge {
	id: string;
	title: string;
	level: string;
	steps: ChallengeStep[];
}

const cli = (expected: string[]) => (input: string) => JSON.stringify(cliArguments(tokenize(input))) === JSON.stringify(expected);
const exact = (...options: string[]) => (input: string) => options.includes(tokenize(input).join(' '));

export const CHALLENGES: Challenge[] = [
	{
		id: 'reto-primera-instalacion',
		title: 'Instala y ejecuta PALLAQUINO por primera vez',
		level: 'Principiante',
		steps: [
			{ instruction: 'Comprueba que tienes Python.', hint: 'python --version', accepts: exact('python --version', 'python3 --version', 'py --version'),
				explanation: 'PALLAQUINO necesita Python 3.11 o superior y no instala dependencias externas: solo usa la biblioteca estándar.' },
			{ instruction: 'Comprueba que tienes Git.', hint: 'git --version', accepts: exact('git --version'),
				explanation: 'Git sirve para descargar el repositorio y también lo usan algunas validaciones (identidad de commits) y el adaptador core.git.' },
			{ instruction: 'Clona el repositorio.', hint: `git clone ${REPO_URL}`, accepts: exact(`git clone ${REPO_URL}`),
				explanation: 'Se crea la carpeta pallaquino-os con el framework, la documentación y el ZIP de release.' },
			{ instruction: 'Entra en el directorio del framework.', hint: 'cd pallaquino-os/universal_ai_fullstack_orchestrator',
				accepts: exact('cd pallaquino-os/universal_ai_fullstack_orchestrator', 'cd pallaquino-os\\universal_ai_fullstack_orchestrator'),
				explanation: 'Sin instalar el paquete, `python -m pallaquino_cli` solo funciona desde esta carpeta, que contiene el paquete pallaquino_cli.' },
			{ instruction: 'Ejecuta el diagnóstico.', hint: 'python -m pallaquino_cli doctor', accepts: cli(['doctor']),
				explanation: 'doctor reúne validaciones, capacidades del equipo y frescura del stack. En un clon recién descargado devuelve "ok": false solo por la identidad Git (comprobación de entorno), no por un problema del framework.' },
			{ instruction: 'Valida solo la integridad del contenido.', hint: 'python -m pallaquino_cli validate --integrity-only --json', accepts: cli(['validate', '--integrity-only', '--json']),
				explanation: '--integrity-only omite las comprobaciones que dependen de tu equipo. "ok": true significa que registros, pipeline, continuidad, gobernanza, grafo, contexto, riesgo y CLI son coherentes.' },
			{ instruction: 'Analiza el repositorio.', hint: 'python -m pallaquino_cli analyze', accepts: cli(['analyze']),
				explanation: 'analyze construye el mapa del repositorio (lenguajes, entrypoints, tests, configuración) y lo guarda en repository/REPOSITORY_MAP.json.' },
			{ instruction: 'Simula la instalación en un proyecto sin escribir nada.', hint: 'python -m pallaquino_cli init --target ../mi-proyecto --dry-run --json',
				accepts: cli(['init', '--target', '../mi-proyecto', '--dry-run', '--json']),
				explanation: 'Con --dry-run, init informa qué copiaría a ../mi-proyecto/.pallaquino sin escribir nada. Sin --dry-run lo hace y nunca sobrescribe archivos existentes.' },
		],
	},
	{
		id: 'reto-riesgo-y-herramientas',
		title: 'Riesgo, agentes y herramientas gobernadas',
		level: 'Intermedio',
		steps: [
			{ instruction: 'Entra en el framework (si no lo estás) y clasifica el riesgo de «agregar autenticación basada en roles».', hint: 'python -m pallaquino_cli risk "agregar autenticación basada en roles" --json',
				accepts: cli(['risk', 'agregar autenticación basada en roles', '--json']),
				explanation: 'La clasificación es determinista: «autenticación» y «roles» activan factores de identidad, el nivel resulta HIGH y se exigen gates de seguridad.' },
			{ instruction: 'Pregunta qué agentes propone el router para esa solicitud.', hint: 'python -m pallaquino_cli agents match "agregar autenticación basada en roles" --json',
				accepts: cli(['agents', 'match', 'agregar autenticación basada en roles', '--json']),
				explanation: 'El router puntúa agentes reales por capacidades, dominios y tecnologías, y explica por qué elige cada uno. No inventa agentes.' },
			{ instruction: 'Lista las herramientas registradas.', hint: 'python -m pallaquino_cli tools list --no-plugins', accepts: cli(['tools', 'list', '--no-plugins']),
				explanation: 'Aparecen las 15 herramientas builtin: filesystem, Git y SQLite. Las de plugins y MCP solo aparecen cuando las configuras, revisas y autorizas.' },
			{ instruction: 'Comprueba en seco si puedes escribir un archivo.', hint: `python -m pallaquino_cli tools check core.files.write --no-plugins --args '{"path": "a.txt", "content": "x"}' --json`,
				accepts: cli(['tools', 'check', 'core.files.write', '--no-plugins', '--args', '{"path": "a.txt", "content": "x"}', '--json']),
				explanation: 'La decisión es "denied": las escrituras necesitan un grant explícito (pallaquino permissions grant). Deny by default.' },
		],
	},
];
