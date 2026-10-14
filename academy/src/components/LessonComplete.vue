<script setup lang="ts">
import { computed } from 'vue';
import { useProgress } from '../lib/useProgress';

const props = defineProps<{ lessonId: string }>();
const { state, ready, store } = useProgress();
const done = computed(() => state.value.completed.includes(props.lessonId));

function toggle() {
	store().setCompleted(props.lessonId, !done.value);
}
</script>

<template>
	<div class="lesson-complete" :class="{ done }">
		<button type="button" :aria-pressed="done" :disabled="!ready" @click="toggle">
			{{ done ? '✔ Lección completada' : 'Marcar lección como completada' }}
		</button>
		<p aria-live="polite">{{ done ? 'Guardado en este navegador. Puedes desmarcarla cuando quieras.' : 'Tu progreso se guarda solo en este navegador; no hace falta registrarse.' }}</p>
	</div>
</template>

<style scoped>
.lesson-complete { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; margin-block: 2rem 1rem; padding: 1rem; border-radius: 0.75rem; background: var(--sl-color-gray-6); }
.lesson-complete p { margin: 0; font-size: var(--sl-text-sm); color: var(--sl-color-gray-2); }
button { border: 2px solid var(--sl-color-accent); background: transparent; color: var(--sl-color-text-accent); border-radius: 0.5rem; padding: 0.5rem 1rem; font-weight: 600; cursor: pointer; }
.done button { background: var(--academy-success); border-color: var(--academy-success); color: var(--sl-color-black); }
button:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
button:disabled { opacity: 0.6; }
</style>
