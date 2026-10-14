<script setup lang="ts">
import { computed, ref } from 'vue';
import cli from '../data/generated/cli.json';

const query = ref('');
const filtered = computed(() => {
	const q = query.value.trim().toLowerCase();
	return cli.commands.filter((c) => !q || [c.name, c.help ?? '', ...c.arguments.map((a) => `${a.flags.join(' ')} ${a.name} ${a.help ?? ''}`)].join(' ').toLowerCase().includes(q));
});
const shown = (a: { name: string }) => a.name !== 'root' && a.name !== 'json';
</script>

<template>
	<section class="commands" aria-labelledby="cmd-title">
		<h2 id="cmd-title">Explorador de comandos ({{ cli.commands.length }})</h2>
		<p class="muted">Generado del parser real de la CLI (PALLAQUINO {{ cli.version }}). Todos los comandos aceptan <code>--root</code> y <code>--json</code>.</p>
		<label class="search">Filtrar comandos <input v-model="query" type="search" placeholder="por ejemplo: memory, --dry-run, plugin" /></label>
		<p class="muted" aria-live="polite">{{ filtered.length }} comando(s)</p>
		<details v-for="c in filtered" :key="c.name" class="command">
			<summary><code>pallaquino {{ c.name }}</code> — {{ c.help }}</summary>
			<table v-if="c.arguments.filter(shown).length">
				<thead><tr><th scope="col">Argumento</th><th scope="col">Descripción</th><th scope="col">Valores</th></tr></thead>
				<tbody>
					<tr v-for="a in c.arguments.filter(shown)" :key="a.name + a.flags.join()">
						<td><code>{{ a.flags.length ? a.flags.join(', ') : a.name }}</code><span v-if="a.required" class="req"> (obligatorio)</span></td>
						<td>{{ a.help ?? '—' }}</td>
						<td>{{ Array.isArray(a.choices) ? (a.choices as string[]).join(' | ') : (a.takes_value ? 'valor' : 'interruptor') }}</td>
					</tr>
				</tbody>
			</table>
			<p v-else class="muted">Sin argumentos propios.</p>
		</details>
	</section>
</template>

<style scoped>
.muted { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); }
.search { display: flex; flex-direction: column; gap: 0.25rem; font-size: var(--sl-text-sm); max-width: 28rem; }
.command { border: 1px solid var(--sl-color-gray-5); border-radius: 0.5rem; padding: 0.5rem 0.75rem; margin-bottom: 0.5rem; }
.command summary { cursor: pointer; }
.command summary:focus-visible, input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
table { width: 100%; font-size: var(--sl-text-sm); margin-top: 0.5rem; }
.req { color: var(--academy-warning); font-size: var(--sl-text-xs); }
</style>
