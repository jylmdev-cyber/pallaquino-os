<script setup lang="ts">
import { computed, ref } from 'vue';
import { LEVELS, levelFor, percent } from '../lib/progress';
import { PATHS } from '../lib/paths';
import { useProgress } from '../lib/useProgress';
import { CHALLENGES } from '../lib/challenges';

export interface LessonRef { id: string; title: string; path: string; href: string }
const props = defineProps<{ lessons: LessonRef[] }>();
const { state, ready, store } = useProgress();
const message = ref('');
const fileInput = ref<HTMLInputElement | null>(null);

const allIds = computed(() => props.lessons.map((l) => l.id));
const overall = computed(() => percent(state.value.completed, allIds.value));
const level = computed(() => levelFor(overall.value));
const byPath = computed(() => PATHS.map((p) => {
	const lessons = props.lessons.filter((l) => l.path === p.id);
	const next = lessons.find((l) => !state.value.completed.includes(l.id));
	return { ...p, lessons, pct: percent(state.value.completed, lessons.map((l) => l.id)), next };
}).filter((p) => p.lessons.length));
const nextLesson = computed(() => byPath.value.find((p) => p.next)?.next);

function download() {
	const blob = new Blob([store().exportJson()], { type: 'application/json' });
	const url = URL.createObjectURL(blob); const a = document.createElement('a');
	a.href = url; a.download = 'pallaquino-academy-progreso.json'; a.click(); URL.revokeObjectURL(url);
	message.value = 'Progreso exportado a pallaquino-academy-progreso.json.';
}

async function importFile(event: Event) {
	const file = (event.target as HTMLInputElement).files?.[0];
	if (!file) return;
	const result = store().importJson(await file.text());
	message.value = result.ok ? 'Progreso importado correctamente.' : `No se importó nada: ${result.error}`;
	if (fileInput.value) fileInput.value.value = '';
}

function reset() {
	if (window.confirm('¿Borrar todo tu progreso de este navegador? Esta acción no se puede deshacer.')) { store().reset(); message.value = 'Progreso reiniciado.'; }
}
</script>

<template>
	<section class="progress-dashboard" aria-labelledby="progress-title">
		<h2 id="progress-title">Tu progreso</h2>
		<p v-if="!ready">Cargando el progreso guardado en este navegador…</p>
		<template v-else>
			<div class="summary">
				<div>
					<p class="big">{{ overall }} %</p>
					<p class="muted">{{ state.completed.filter((id) => allIds.includes(id)).length }} de {{ lessons.length }} lecciones completadas</p>
				</div>
				<div>
					<p class="level">Nivel: <strong>{{ level.label }}</strong></p>
					<p class="muted">{{ level.description }} Los niveles son educativos y no son una certificación oficial.</p>
				</div>
			</div>
			<p v-if="nextLesson" class="next">Siguiente lección sugerida: <a :href="nextLesson.href">{{ nextLesson.title }}</a></p>
			<ul class="paths">
				<li v-for="p in byPath" :key="p.id">
					<div class="path-head"><span>{{ p.order }} · {{ p.title }}</span><span>{{ p.pct }} %</span></div>
					<div class="bar" role="progressbar" :aria-valuenow="p.pct" aria-valuemin="0" aria-valuemax="100" :aria-label="`Progreso en ${p.title}`">
						<span :style="{ width: `${p.pct}%` }"></span>
					</div>
				</li>
			</ul>
			<h3>Evaluaciones y retos</h3>
			<ul class="muted">
				<li v-for="(q, id) in state.quizzes" :key="id">{{ id }}: {{ q.score }}/{{ q.total }} {{ q.passed ? '✔' : '' }} ({{ q.attempts }} intento/s)</li>
				<li v-for="c in CHALLENGES" :key="c.id">{{ c.title }}: {{ state.challenges.includes(c.id) ? 'completado ✔' : 'pendiente' }}</li>
				<li v-if="!Object.keys(state.quizzes).length">Aún no has respondido ninguna evaluación.</li>
			</ul>
			<h3>Niveles</h3>
			<ul class="muted"><li v-for="l in LEVELS" :key="l.id"><strong>{{ l.label }}</strong> (desde {{ l.minPercent }} %): {{ l.description }}</li></ul>
			<div class="actions">
				<button type="button" @click="download">Exportar progreso</button>
				<label class="import">Importar progreso <input ref="fileInput" type="file" accept="application/json,.json" @change="importFile" /></label>
				<button type="button" class="danger" @click="reset">Reiniciar progreso</button>
			</div>
			<p class="muted" aria-live="polite">{{ message }}</p>
			<p class="muted">Privacidad: el progreso solo se guarda en este navegador (localStorage), nunca se envía a ningún servicio y no contiene datos personales.</p>
		</template>
	</section>
</template>

<style scoped>
.progress-dashboard { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem 1.25rem; margin-block: 1rem; }
h2 { margin-top: 0; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 1rem; }
.summary p { margin: 0; }
.big { font-size: 2.5rem; font-weight: 700; color: var(--sl-color-text-accent); }
.muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.level { font-size: var(--sl-text-lg); }
.paths { list-style: none; padding: 0; }
.paths li { margin-bottom: 0.6rem; }
.path-head { display: flex; justify-content: space-between; font-size: var(--sl-text-sm); }
.bar { height: 0.6rem; border-radius: 1rem; background: var(--sl-color-gray-5); overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--sl-color-accent); }
.actions { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; margin-top: 1rem; }
button, .import { border: 1px solid var(--sl-color-gray-4); background: var(--sl-color-gray-6); color: var(--sl-color-white); border-radius: 0.5rem; padding: 0.4rem 0.8rem; cursor: pointer; font-size: var(--sl-text-sm); }
.import input { display: block; margin-top: 0.25rem; font-size: var(--sl-text-xs); }
.danger { border-color: var(--academy-danger); }
button:focus-visible, .import input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
</style>
