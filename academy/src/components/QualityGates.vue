<script setup lang="ts">
import { computed, ref } from 'vue';
import pipeline from '../data/generated/pipeline.json';
import { FEATURED_GATES } from '../lib/gates';

/** Real gate stages from pipeline_definition.json: each declares where a failure returns for remediation. */
const FEATURED = FEATURED_GATES;
interface Stage { id: string; kind?: string; failure_return_to?: string | null; success_to?: string | null; evidence_required?: boolean; order?: number }
const stages = pipeline.stages as Stage[];
const gates = computed(() => FEATURED.map((id) => stages.find((s) => s.id === id)).filter((s): s is Stage => Boolean(s)));
const failing = ref<string[]>([]);
const firstFailure = computed(() => gates.value.find((g) => failing.value.includes(g.id)));
</script>

<template>
	<section class="gates" aria-labelledby="gates-title">
		<h2 id="gates-title">Quality gates</h2>
		<p class="muted">Etapas reales del pipeline de PALLAQUINO (de <code>pipeline_definition.json</code>). Marca una como fallida para ver qué ocurre.</p>
		<ul>
			<li v-for="g in gates" :key="g.id" :class="{ failing: failing.includes(g.id) }">
				<label><input v-model="failing" type="checkbox" :value="g.id" /> Simular fallo en <strong>{{ g.id }}</strong></label>
				<span class="meta">si pasa → {{ g.success_to ?? 'fin' }} · si falla → vuelve a {{ g.failure_return_to ?? '—' }}<span v-if="g.evidence_required"> · exige evidencia</span></span>
			</li>
		</ul>
		<p class="result" aria-live="polite">
			<template v-if="firstFailure">✖ La tarea <strong>no puede completarse</strong>: {{ firstFailure.id }} falló y el pipeline vuelve a <strong>{{ firstFailure.failure_return_to }}</strong> para remediar. Ninguna etapa posterior se da por superada.</template>
			<template v-else>✔ Todos los gates pasan: la tarea avanza hasta la entrega con evidencia registrada.</template>
		</p>
	</section>
</template>

<style scoped>
.gates { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem 1.25rem; margin-block: 1.5rem; }
h2 { margin-top: 0; }
.muted, .meta { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
ul { list-style: none; padding: 0; }
li { padding: 0.4rem 0.6rem; border-radius: 0.5rem; border-inline-start: 4px solid var(--academy-success); margin-bottom: 0.4rem; background: var(--sl-color-gray-6); }
li.failing { border-color: var(--academy-danger); }
.meta { display: block; margin-inline-start: 1.6rem; }
.result { font-weight: 600; }
input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
</style>
