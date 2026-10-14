/** Learning paths: the nine routes of the academy, in order. Lesson membership comes from each page's `lesson.path` frontmatter. */
export type Difficulty = 'principiante' | 'intermedio' | 'avanzado';

export interface LearningPath {
	id: string;
	order: number;
	title: string;
	level: string;
	summary: string;
	directory: string;
}

export const PATHS: LearningPath[] = [
	{ id: 'introduccion', order: 1, title: 'Introducción a PALLAQUINO', level: 'Principiante', directory: 'introduccion', summary: 'Qué es, para qué sirve y cómo encajan agentes, skills, pipelines y gobernanza.' },
	{ id: 'instalacion', order: 2, title: 'Instalación y configuración', level: 'Principiante', directory: 'instalacion', summary: 'Python, Git, el repositorio, el diagnóstico y tu primer proyecto con PALLAQUINO.' },
	{ id: 'cli', order: 3, title: 'Dominio de la CLI', level: 'Principiante · Intermedio', directory: 'cli', summary: 'doctor, validate, analyze, risk, init y cómo leer la salida JSON.' },
	{ id: 'agentes-y-skills', order: 4, title: 'Agentes y skills', level: 'Intermedio', directory: 'agentes-y-skills', summary: 'Catálogo real, contratos v2, selección por el router y cómo se crean.' },
	{ id: 'orquestacion', order: 5, title: 'Pipelines y orquestación', level: 'Intermedio', directory: 'orquestacion', summary: 'De una solicitud a un plan (DAG), su ejecución, los quality gates y los handoffs.' },
	{ id: 'memoria', order: 6, title: 'Memoria y continuidad', level: 'Intermedio', directory: 'memoria', summary: 'Memoria por proyecto, ejecuciones reanudables, checkpoints y handoffs.' },
	{ id: 'plugins-y-mcp', order: 7, title: 'Plugins y MCP', level: 'Intermedio · Avanzado', directory: 'plugins-y-mcp', summary: 'Herramientas gobernadas, plugins con confianza por hash y servidores MCP 2026-07-28.' },
	{ id: 'proyectos-reales', order: 8, title: 'PALLAQUINO en proyectos reales', level: 'Intermedio · Avanzado', directory: 'proyectos-reales', summary: 'Qué hace PALLAQUINO y qué haces tú en proyectos Python, Django, Nuxt y otros.' },
	{ id: 'extension', order: 9, title: 'Extensión del framework', level: 'Avanzado', directory: 'extension', summary: 'Arquitectura interna, contratos, SDK de plugins, pruebas y contribución.' },
];

export const DIFFICULTY_LABEL: Record<Difficulty, string> = { principiante: 'Principiante', intermedio: 'Intermedio', avanzado: 'Avanzado' };

export const STATUS_LABEL: Record<string, string> = {
	disponible: 'Disponible',
	experimental: 'Experimental',
	deprecado: 'Deprecado',
	proximamente: 'Próximamente',
};

export function pathById(id: string): LearningPath | undefined {
	return PATHS.find((p) => p.id === id);
}
