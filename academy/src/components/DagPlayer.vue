<script setup lang="ts">
import { computed, ref } from 'vue';
import plan from '../data/plan_example.json';

type State = 'PLANNED' | 'READY' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'BLOCKED' | 'RETRYING';
const STATE_LABEL: Record<State, string> = { PLANNED: 'planificada', READY: 'lista', RUNNING: 'en ejecución', COMPLETED: 'completada', FAILED: 'fallida', BLOCKED: 'bloqueada', RETRYING: 'reintentando' };

const injectFailure = ref(false);
const states = ref<Record<string, State>>(initial());
const log = ref<string[]>(['Plan cargado: todas las tareas empiezan en PLANNED.']);
const retried = ref(false);

function initial(): Record<string, State> {
	return Object.fromEntries(plan.tasks.map((t) => [t.task_id, 'PLANNED' as State]));
}

const levels = computed(() => plan.dag.levels as string[][]);
const byId = computed(() => Object.fromEntries(plan.tasks.map((t) => [t.task_id, t])));
const done = computed(() => plan.tasks.every((t) => ['COMPLETED', 'BLOCKED', 'FAILED'].includes(states.value[t.task_id])));

/** One scheduler tick: promote, then run READY tasks (a simplified model of orchestration/scheduler.py for teaching). */
function step() {
	const next = { ...states.value }; const events: string[] = [];
	for (const t of plan.tasks) {
		if (next[t.task_id] === 'RUNNING') {
			if (injectFailure.value && t.step === 'quality_scan' && !retried.value) { next[t.task_id] = 'RETRYING'; retried.value = true; events.push(`${t.task_id} falló (timeout simulado) → RETRYING con la misma clave de idempotencia`); }
			else { next[t.task_id] = 'COMPLETED'; events.push(`${t.task_id} completada: evidencia y handoff registrados`); }
		} else if (next[t.task_id] === 'RETRYING') { next[t.task_id] = 'RUNNING'; events.push(`${t.task_id} reintento en ejecución`); }
	}
	for (const t of plan.tasks) {
		if (next[t.task_id] !== 'PLANNED') continue;
		const deps = t.dependencies.map((d) => next[d]);
		if (deps.some((d) => d === 'FAILED' || d === 'BLOCKED')) { next[t.task_id] = 'BLOCKED'; events.push(`${t.task_id} bloqueada por una dependencia fallida`); }
		else if (deps.every((d) => d === 'COMPLETED')) { next[t.task_id] = 'READY'; events.push(`${t.task_id} lista: sus dependencias terminaron`); }
	}
	for (const t of plan.tasks) {
		if (states.value[t.task_id] === 'READY' && next[t.task_id] === 'READY') { next[t.task_id] = 'RUNNING'; events.push(`${t.task_id} en ejecución (${t.agent})`); }
	}
	states.value = next; log.value = [...log.value, ...events].slice(-12);
}

function reset() {
	states.value = initial(); retried.value = false; log.value = ['Plan reiniciado.'];
}
</script>

<template>
	<section class="dag" aria-labelledby="dag-title">
		<h2 id="dag-title">DAG interactivo</h2>
		<p class="muted">
			Plan real que generó <code>pallaquino plan</code> para «{{ plan.request }}» (estado {{ plan.status }}, riesgo {{ plan.risk }}).
			La animación de estados es una <strong>simulación educativa</strong> del scheduler: no ejecuta nada.
		</p>
		<div class="columns" tabindex="0" role="group" aria-label="Niveles del plan">
			<div v-for="(level, li) in levels" :key="li" class="column">
				<p class="level-title">Nivel {{ li + 1 }}<span v-if="level.length > 1"> · en paralelo</span></p>
				<article v-for="id in level" :key="id" :class="['task', states[id].toLowerCase()]">
					<p class="task-id">{{ id }} · {{ byId[id].step }}</p>
					<p class="task-title">{{ byId[id].title }}</p>
					<p class="task-meta">agente <code>{{ byId[id].agent }}</code> · ejecutor {{ byId[id].executor }}</p>
					<p v-if="byId[id].tools" class="task-meta">herramientas: {{ (byId[id].tools as string[]).join(', ') }}</p>
					<p v-if="byId[id].dependencies.length" class="task-meta">depende de {{ byId[id].dependencies.join(', ') }}</p>
					<p class="state">{{ STATE_LABEL[states[id]] }}</p>
				</article>
			</div>
		</div>
		<div class="controls">
			<button type="button" :disabled="done" @click="step">Avanzar un paso del scheduler</button>
			<button type="button" @click="reset">Reiniciar</button>
			<label><input v-model="injectFailure" type="checkbox" @change="reset" /> Simular un fallo transitorio en quality_scan</label>
		</div>
		<ol class="log" aria-live="polite" aria-label="Eventos del scheduler"><li v-for="(e, i) in log" :key="i">{{ e }}</li></ol>
		<p v-if="done" class="muted">Ejecución terminada. En PALLAQUINO real, el estado final y la traza quedan en la memoria del proyecto (<code>pallaquino executions report</code>).</p>
	</section>
</template>

<style scoped>
.dag { margin-block: 1.5rem; }
.muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.columns { display: flex; gap: 0.75rem; overflow-x: auto; padding-bottom: 0.5rem; }
.column { min-width: 13rem; flex: 1; }
.level-title { font-size: var(--sl-text-xs); text-transform: uppercase; letter-spacing: 0.05em; color: var(--sl-color-gray-2); margin: 0 0 0.4rem; }
.task { border: 2px solid var(--sl-color-gray-5); border-radius: 0.6rem; padding: 0.5rem 0.65rem; margin-bottom: 0.5rem; background: var(--sl-color-gray-6); }
.task p { margin: 0; }
.task-id { font-weight: 700; font-size: var(--sl-text-sm); } .task-title { font-size: var(--sl-text-sm); } .task-meta { font-size: var(--sl-text-xs); color: var(--sl-color-gray-2); }
.state { margin-top: 0.3rem !important; font-size: var(--sl-text-xs); font-weight: 700; text-transform: uppercase; }
.task.ready { border-color: var(--academy-info); } .task.running, .task.retrying { border-color: var(--academy-warning); }
.task.completed { border-color: var(--academy-success); } .task.failed, .task.blocked { border-color: var(--academy-danger); }
.controls { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; margin-block: 0.75rem; font-size: var(--sl-text-sm); }
.controls button { border: 1px solid var(--sl-color-gray-4); background: var(--sl-color-gray-6); color: var(--sl-color-white); border-radius: 0.5rem; padding: 0.35rem 0.8rem; cursor: pointer; }
.controls button:disabled { opacity: 0.55; }
.log { font-size: var(--sl-text-xs); color: var(--sl-color-gray-2); }
button:focus-visible, input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
</style>
