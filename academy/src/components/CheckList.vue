<script setup lang="ts">
import { computed } from 'vue';
import { useProgress } from '../lib/useProgress';

const props = defineProps<{ group: string; title?: string; items: { id: string; label: string }[] }>();
const { state, ready, store } = useProgress();
const ticked = computed(() => new Set(state.value.checks[props.group] ?? []));
const count = computed(() => props.items.filter((i) => ticked.value.has(i.id)).length);
</script>

<template>
	<fieldset class="checklist">
		<legend>{{ title ?? 'Comprueba tu progreso' }} <span class="count">({{ count }}/{{ items.length }})</span></legend>
		<label v-for="item in items" :key="item.id">
			<input type="checkbox" :checked="ticked.has(item.id)" :disabled="!ready" @change="store().toggleCheck(group, item.id, ($event.target as HTMLInputElement).checked)" />
			<span>{{ item.label }}</span>
		</label>
	</fieldset>
</template>

<style scoped>
.checklist { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 0.75rem 1rem; margin-block: 1rem; }
legend { font-weight: 600; padding-inline: 0.25rem; }
.count { color: var(--sl-color-gray-2); font-weight: 400; }
label { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.25rem 0; cursor: pointer; }
input { margin-top: 0.3rem; }
input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
</style>
