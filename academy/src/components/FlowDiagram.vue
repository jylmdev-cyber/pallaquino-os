<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';

interface Node { id: string; label: string; status: 'implementado' | 'parcial' | 'previsto'; since: string; responsibility: string; input: string; output: string;
	example: string; command?: string }

const NODES: Node[] = [
	{ id: 'request', label: 'Solicitud', status: 'implementado', since: '0.4.0', responsibility: 'Recibe lo que quieres conseguir en lenguaje natural.',
		input: 'Texto libre de la persona', output: 'Solicitud registrada con un identificador', example: '«Analiza el repositorio y revisa el estado de Git»',
		command: 'pallaquino plan "…"' },
	{ id: 'intent', label: 'Análisis', status: 'implementado', since: '0.4.0', responsibility: 'Clasifica intenciones, tecnologías, alcance y riesgo. El riesgo siempre lo calcula el motor determinista, nunca un modelo.',
		input: 'Solicitud', output: 'intent_result (intenciones, riesgo, permisos, criterios de aceptación)', example: 'PROJECT_DISCOVERY, riesgo LOW' , command: 'pallaquino risk "…"' },
	{ id: 'plan', label: 'Planificación', status: 'implementado', since: '0.4.0', responsibility: 'Compone pasos en un DAG validado: dependencias, ciclos, permisos y aprobaciones. Planificar no ejecuta nada.',
		input: 'intent_result', output: 'Plan PLANNED o INVALID', example: 'T01 discover → T02 git_inspect / T03 quality_scan → T04 report', command: 'pallaquino plan "…" --json' },
	{ id: 'agents', label: 'Agentes', status: 'implementado', since: '0.4.0', responsibility: 'El router asigna a cada tarea un agente registrado y explica por qué; si falta una capacidad, lo informa en lugar de inventar.',
		input: 'Tareas del plan', output: 'Agente y razones por tarea', example: 'project_analyzer para el descubrimiento', command: 'pallaquino agents match "…"' },
	{ id: 'execution', label: 'Ejecución', status: 'implementado', since: '0.4.0 / 0.5.0', responsibility: 'El scheduler ejecuta el DAG con concurrencia, locks, reintentos y aprobaciones. Desde 0.5.0 las herramientas pasan por la pasarela de permisos.',
		input: 'Plan validado', output: 'Ejecución con estado por tarea y evidencia', example: 'git status y quality_scan ejecutados como el agente', command: 'pallaquino run --plan <id>' },
	{ id: 'validation', label: 'Validación', status: 'implementado', since: '0.4.0', responsibility: 'Los quality gates (tests, revisión, informe con evidencia) deciden si una tarea se completa o vuelve a remediación.',
		input: 'Resultados y evidencia', output: 'COMPLETED o FAILED con motivo', example: 'el informe falla si ninguna sección cita evidencia' },
	{ id: 'result', label: 'Resultado', status: 'implementado', since: '0.4.0', responsibility: 'Consolida handoffs, guarda memoria por proyecto y produce un informe trazable.',
		input: 'Handoffs', output: 'Informe, memoria, trazas JSONL', example: 'logs/reports/<ejecución>.md', command: 'pallaquino executions report <id>' },
	{ id: 'ui', label: 'Control Center visual', status: 'previsto', since: '0.7.0 (roadmap)', responsibility: 'Interfaz visual para seguir ejecuciones. Hoy solo existe la salida JSON de la CLI.',
		input: '—', output: '—', example: 'Planificado, no disponible' },
];

const selected = ref(NODES[0].id);
const playing = ref(false);
let timer: number | undefined;
const node = computed(() => NODES.find((n) => n.id === selected.value)!);
const reduceMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function play() {
	if (playing.value) { stop(); return; }
	playing.value = true; let i = 0; selected.value = NODES[0].id;
	const advance = () => {
		i += 1;
		if (i >= NODES.length - 1) { stop(); return; }
		selected.value = NODES[i].id;
		timer = window.setTimeout(advance, reduceMotion() ? 2500 : 1600);
	};
	timer = window.setTimeout(advance, reduceMotion() ? 2500 : 1600);
}

function stop() {
	playing.value = false; if (timer) window.clearTimeout(timer);
}

onBeforeUnmount(stop);
</script>

<template>
	<section class="flow" aria-labelledby="flow-title">
		<h2 id="flow-title">¿Cómo avanza una solicitud?</h2>
		<p class="muted">Pulsa cada etapa para ver qué hace. Las etiquetas indican qué está implementado y desde qué versión.</p>
		<ol class="nodes">
			<li v-for="(n, i) in NODES" :key="n.id">
				<button type="button" :class="['node', n.status, { active: selected === n.id }]" :aria-pressed="selected === n.id" @click="stop(); selected = n.id">
					<span class="num">{{ i + 1 }}</span>
					<span class="label">{{ n.label }}</span>
					<span class="status">{{ n.status }}</span>
				</button>
			</li>
		</ol>
		<div class="controls">
			<button type="button" class="play" @click="play">{{ playing ? 'Detener recorrido' : '▶ Recorrer el flujo' }}</button>
		</div>
		<article class="detail" aria-live="polite">
			<h3>{{ node.label }} <span :class="['pill', node.status]">{{ node.status }} · {{ node.since }}</span></h3>
			<p>{{ node.responsibility }}</p>
			<dl>
				<dt>Entrada</dt><dd>{{ node.input }}</dd>
				<dt>Salida</dt><dd>{{ node.output }}</dd>
				<dt>Ejemplo</dt><dd>{{ node.example }}</dd>
				<template v-if="node.command"><dt>Comando relacionado</dt><dd><code>{{ node.command }}</code></dd></template>
			</dl>
		</article>
	</section>
</template>

<style scoped>
.flow { margin-block: 1.5rem; }
.muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.nodes { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.5rem; counter-reset: none; }
.nodes li { margin: 0; }
.node { display: grid; justify-items: center; gap: 0.15rem; min-width: 7.5rem; padding: 0.6rem 0.75rem; border-radius: 0.75rem; border: 2px solid var(--sl-color-gray-5);
	background: var(--sl-color-gray-6); color: var(--sl-color-white); cursor: pointer; transition: transform 0.2s ease, border-color 0.2s ease; }
.node.active { border-color: var(--sl-color-accent); background: var(--sl-color-accent-low); transform: translateY(-2px); }
.node.previsto { border-style: dashed; opacity: 0.85; }
.num { font-size: var(--sl-text-xs); color: var(--sl-color-gray-2); }
.label { font-weight: 600; }
.status { font-size: var(--sl-text-xs); text-transform: uppercase; letter-spacing: 0.04em; }
.controls { margin-block: 0.75rem; }
.play { border: 1px solid var(--sl-color-accent); background: transparent; color: var(--sl-color-text-accent); border-radius: 0.5rem; padding: 0.35rem 0.8rem; cursor: pointer; }
.detail { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem; }
.detail h3 { margin-top: 0; }
.pill { font-size: var(--sl-text-xs); border-radius: 1rem; padding: 0.1rem 0.5rem; margin-inline-start: 0.5rem; vertical-align: middle; border: 1px solid currentColor; }
.pill.implementado { color: var(--academy-success); } .pill.previsto { color: var(--academy-warning); } .pill.parcial { color: var(--academy-info); }
dt { font-weight: 600; margin-top: 0.4rem; } dd { margin: 0; }
button:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { .node { transition: none; } .node.active { transform: none; } }
</style>
