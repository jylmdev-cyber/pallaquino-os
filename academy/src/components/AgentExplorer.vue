<script setup lang="ts">
import { computed, ref } from 'vue';
import agents from '../data/generated/agents.json';
import skills from '../data/generated/skills.json';

type Kind = 'agents' | 'skills';
const props = withDefaults(defineProps<{ initial?: Kind }>(), { initial: 'agents' });

interface Item { id: string; name: string; description: string; category: string; domains: string[]; capabilities: string[]; technologies: string[];
	inputs: string[]; outputs: string[]; [key: string]: unknown }

const kind = ref<Kind>(props.initial);
const query = ref('');
const category = ref('');
const selectedId = ref('');

const items = computed<Item[]>(() => (kind.value === 'agents' ? agents : skills) as Item[]);
const categories = computed(() => [...new Set(items.value.map((i) => i.category))].sort());
const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	return items.value.filter((i) => (!category.value || i.category === category.value)
		&& (!q || [i.id, i.name, i.description, ...i.domains, ...i.capabilities, ...i.technologies].join(' ').toLowerCase().includes(q)));
});
const selected = computed(() => items.value.find((i) => i.id === selectedId.value) ?? null);

function choose(id: string) {
	selectedId.value = id;
}

function switchKind(next: Kind) {
	kind.value = next; category.value = ''; selectedId.value = '';
}
</script>

<template>
	<section class="explorer" aria-labelledby="explorer-title">
		<h2 id="explorer-title" class="sr-only">Explorador de agentes y skills</h2>
		<div class="tabs" role="group" aria-label="Tipo de catálogo">
			<button type="button" :aria-pressed="kind === 'agents'" @click="switchKind('agents')">Agentes ({{ agents.length }})</button>
			<button type="button" :aria-pressed="kind === 'skills'" @click="switchKind('skills')">Skills ({{ skills.length }})</button>
		</div>
		<div class="filters">
			<label>Buscar <input v-model="query" type="search" placeholder="id, dominio, capacidad o tecnología" /></label>
			<label>Categoría
				<select v-model="category"><option value="">Todas</option><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select>
			</label>
		</div>
		<p class="count" aria-live="polite">{{ filtered.length }} resultado(s). Datos generados del registro real de PALLAQUINO.</p>
		<div class="layout">
			<ul class="list">
				<li v-for="item in filtered" :key="item.id">
					<button type="button" :aria-pressed="selectedId === item.id" @click="choose(item.id)">
						<span class="name">{{ item.name }}</span>
						<code>{{ item.id }}</code>
						<span class="cat">{{ item.category }}</span>
					</button>
				</li>
			</ul>
			<article class="detail" aria-live="polite">
				<template v-if="selected">
					<h3>{{ selected.name }}</h3>
					<p><code>{{ selected.id }}</code> · categoría <strong>{{ selected.category }}</strong>
						<template v-if="kind === 'agents'"> · límite de riesgo <strong>{{ selected.risk_limit }}</strong></template>
						<template v-else> · riesgo <strong>{{ selected.risk_level }}</strong></template>
					</p>
					<p>{{ selected.description }}</p>
					<dl>
						<dt>Dominios</dt><dd>{{ selected.domains.join(', ') || '—' }}</dd>
						<dt>Capacidades</dt><dd>{{ selected.capabilities.join(', ') || '—' }}</dd>
						<dt v-if="selected.technologies.length">Tecnologías</dt><dd v-if="selected.technologies.length">{{ selected.technologies.join(', ') }}</dd>
						<dt>Entradas</dt><dd><ul><li v-for="x in selected.inputs" :key="x">{{ x }}</li></ul></dd>
						<dt>Salidas</dt><dd><ul><li v-for="x in selected.outputs" :key="x">{{ x }}</li></ul></dd>
						<template v-if="kind === 'agents'">
							<dt>Criterios de éxito</dt><dd><ul><li v-for="x in (selected.success_criteria as string[])" :key="x">{{ x }}</li></ul></dd>
							<dt>Herramientas permitidas</dt><dd>{{ (selected.tools_allowed as string[]).join(', ') || '—' }}</dd>
							<dt>Requieren aprobación</dt><dd>{{ (selected.tools_approval as string[]).join(', ') || 'ninguna' }}</dd>
							<dt>Skills que usa</dt><dd>{{ (selected.skills as string[]).join(', ') || '—' }}</dd>
							<dt v-if="(selected.pipeline_stages as string[]).length">Rol en etapas</dt><dd v-if="(selected.pipeline_stages as string[]).length">{{ (selected.pipeline_stages as string[]).join(', ') }}</dd>
						</template>
						<template v-else>
							<dt>Depende de</dt><dd>{{ (selected.dependencies as string[]).join(', ') || '—' }}</dd>
						</template>
						<dt>Curación</dt><dd>{{ selected.curation === 'curated' ? 'contrato revisado a mano' : 'contrato derivado de la categoría (genérico)' }}</dd>
					</dl>
				</template>
				<p v-else class="muted">Selecciona un {{ kind === 'agents' ? 'agente' : 'skill' }} para ver su contrato: objetivo, entradas, salidas, restricciones y herramientas.</p>
			</article>
		</div>
	</section>
</template>

<style scoped>
.explorer { margin-block: 1.5rem; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.tabs { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.tabs button, .list button { border: 1px solid var(--sl-color-gray-5); background: var(--sl-color-gray-6); color: var(--sl-color-white); border-radius: 0.5rem; padding: 0.4rem 0.8rem; cursor: pointer; }
.tabs button[aria-pressed='true'] { background: var(--sl-color-accent); color: var(--sl-color-black); border-color: var(--sl-color-accent); }
.filters { display: flex; gap: 1rem; flex-wrap: wrap; }
.filters label { display: flex; flex-direction: column; font-size: var(--sl-text-sm); gap: 0.25rem; }
.filters input { min-width: 16rem; }
.count, .muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.layout { display: grid; grid-template-columns: minmax(14rem, 1fr) 2fr; gap: 1rem; }
.list { list-style: none; padding: 0; margin: 0; max-height: 32rem; overflow: auto; }
.list li { margin: 0 0 0.35rem; }
.list button { width: 100%; text-align: start; display: grid; gap: 0.1rem; }
.list button[aria-pressed='true'] { border-color: var(--sl-color-accent); background: var(--sl-color-accent-low); }
.list .name { font-weight: 600; } .list .cat { font-size: var(--sl-text-xs); color: var(--sl-color-gray-2); }
.detail { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem; }
.detail h3 { margin-top: 0; }
dt { font-weight: 600; margin-top: 0.5rem; } dd { margin: 0; } dd ul { margin: 0; padding-inline-start: 1.1rem; }
button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
@media (max-width: 50rem) { .layout { grid-template-columns: 1fr; } .list { max-height: 16rem; } }
</style>
