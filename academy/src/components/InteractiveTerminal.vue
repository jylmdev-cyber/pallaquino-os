<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import cli from '../data/generated/cli.json';
import transcripts from '../data/transcripts.json';
import { CHALLENGES } from '../lib/challenges';
import { TerminalSimulator, type TerminalResponse } from '../lib/terminal';
import { progressStore } from '../lib/useProgress';

const props = withDefaults(defineProps<{ challenge?: string; height?: string }>(), { challenge: '', height: '26rem' });

interface Entry { id: number; prompt: string; input: string; response: TerminalResponse }

const sim = new TerminalSimulator(cli, transcripts);
const entries = ref<Entry[]>([]);
const input = ref('');
const prompt = ref(sim.prompt());
const suggestions = ref<string[]>([]);
const historyIndex = ref<number | null>(null);
const output = ref<HTMLElement | null>(null);
const field = ref<HTMLInputElement | null>(null);
const challengeId = ref(props.challenge || CHALLENGES[0].id);
const stepIndex = ref(0);
const explanation = ref('');
const showHint = ref(false);
let counter = 0;

const challenge = computed(() => CHALLENGES.find((c) => c.id === challengeId.value) ?? CHALLENGES[0]);
const step = computed(() => challenge.value.steps[stepIndex.value]);
const finished = computed(() => stepIndex.value >= challenge.value.steps.length);

const KIND_LABEL: Record<string, string> = { recorded: 'salida real grabada', simulated: 'simulado', error: 'error', blocked: 'bloqueado', info: 'información', clear: '' };

function scrollToEnd() {
	nextTick(() => { if (output.value) output.value.scrollTop = output.value.scrollHeight; });
}

function submit() {
	const text = input.value;
	const response = sim.run(text);
	suggestions.value = []; historyIndex.value = null;
	if (response.kind === 'clear') { entries.value = []; input.value = ''; prompt.value = sim.prompt(); return; }
	entries.value.push({ id: counter++, prompt: prompt.value, input: text, response });
	if (entries.value.length > 60) entries.value.splice(0, entries.value.length - 60);
	if (text.trim() === 'reiniciar' || text.trim() === 'reset') { stepIndex.value = 0; explanation.value = ''; }
	if (!finished.value && step.value.accepts(text) && response.kind !== 'error' && response.kind !== 'blocked') {
		explanation.value = step.value.explanation; showHint.value = false; stepIndex.value++;
		if (finished.value) progressStore().completeChallenge(challenge.value.id);
	}
	prompt.value = sim.prompt(); input.value = '';
	scrollToEnd();
}

function onKey(event: KeyboardEvent) {
	const history = sim.state.history;
	if (event.key === 'Tab') {
		const options = sim.complete(input.value);
		if (options.length) {
			event.preventDefault();
			if (options.length === 1) { input.value = options[0]; suggestions.value = []; } else suggestions.value = options.slice(0, 12);
		}
	} else if (event.key === 'ArrowUp' && history.length) {
		event.preventDefault();
		historyIndex.value = historyIndex.value === null ? history.length - 1 : Math.max(0, historyIndex.value - 1);
		input.value = history[historyIndex.value];
	} else if (event.key === 'ArrowDown' && historyIndex.value !== null) {
		event.preventDefault();
		historyIndex.value = historyIndex.value + 1 < history.length ? historyIndex.value + 1 : null;
		input.value = historyIndex.value === null ? '' : history[historyIndex.value];
	}
}

function resetAll() {
	sim.reset(); entries.value = []; stepIndex.value = 0; explanation.value = ''; prompt.value = sim.prompt(); input.value = '';
	field.value?.focus();
}

function selectChallenge(id: string) {
	challengeId.value = id; resetAll();
}

function useHint() {
	input.value = step.value.hint; showHint.value = true; field.value?.focus();
}

onMounted(() => {
	if (progressStore().load().challenges.includes(challenge.value.id)) explanation.value = 'Ya completaste este reto antes. Puedes repetirlo cuando quieras.';
});
</script>

<template>
	<section class="terminal-card" aria-labelledby="terminal-title">
		<header class="terminal-head">
			<h2 id="terminal-title" class="terminal-title">PALLAQUINO Terminal Playground</h2>
			<p class="terminal-badge">
				<strong>SIMULACIÓN</strong>: no se ejecuta nada en tu equipo ni en un servidor. Las salidas de PALLAQUINO se grabaron de un clon real el
				{{ transcripts.captured_on }} ({{ transcripts.platform }}).
			</p>
		</header>

		<div class="challenge" aria-live="polite">
			<label class="challenge-select">
				<span>Reto guiado</span>
				<select :value="challengeId" @change="selectChallenge(($event.target as HTMLSelectElement).value)">
					<option v-for="c in CHALLENGES" :key="c.id" :value="c.id">{{ c.title }} ({{ c.level }})</option>
				</select>
			</label>
			<p v-if="!finished" class="challenge-step">
				<span class="step-count">Paso {{ stepIndex + 1 }} de {{ challenge.steps.length }}</span> {{ step.instruction }}
				<button type="button" class="link-button" @click="useHint">Ver comando</button>
			</p>
			<p v-else class="challenge-done">✔ Reto completado. Tu progreso se guardó en este navegador.</p>
			<p v-if="explanation" class="challenge-explanation"><strong>¿Qué pasó?</strong> {{ explanation }}</p>
		</div>

		<div ref="output" class="terminal-output" tabindex="0" role="log" aria-live="polite" aria-label="Salida de la terminal simulada" :style="{ maxHeight: height }">
			<p v-if="!entries.length" class="terminal-welcome">Escribe «ayuda» para ver qué puedes practicar, o sigue el reto guiado.</p>
			<div v-for="entry in entries" :key="entry.id" class="entry">
				<p class="entry-command"><span class="prompt">{{ entry.prompt }}</span> {{ entry.input }}</p>
				<p v-if="KIND_LABEL[entry.response.kind]" :class="['entry-kind', `kind-${entry.response.kind}`]">
					{{ KIND_LABEL[entry.response.kind] }}<template v-if="entry.response.kind !== 'info'"> · código de salida {{ entry.response.exitCode }}</template>
				</p>
				<pre v-if="entry.response.lines.length" class="entry-output">{{ entry.response.lines.join('\n') }}</pre>
				<p v-if="entry.response.note" class="entry-note">{{ entry.response.note }}</p>
			</div>
		</div>

		<form class="terminal-form" @submit.prevent="submit">
			<label for="terminal-input" class="prompt">{{ prompt }}</label>
			<input id="terminal-input" ref="field" v-model="input" class="terminal-input" type="text" autocomplete="off" autocapitalize="off" spellcheck="false"
				aria-describedby="terminal-help" maxlength="500" @keydown="onKey" />
			<button type="submit" class="run-button">Ejecutar</button>
		</form>
		<p v-if="suggestions.length" class="suggestions" aria-live="polite">Sugerencias: <code v-for="s in suggestions" :key="s">{{ s }}</code></p>
		<p id="terminal-help" class="terminal-help">
			Enter ejecuta · Tab completa · ↑/↓ recorren el historial ·
			<button type="button" class="link-button" @click="resetAll">Reiniciar simulador</button>
		</p>
	</section>
</template>

<style scoped>
.terminal-card { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; overflow: hidden; background: var(--sl-color-bg-nav); margin-block: 1.5rem; }
.terminal-head { padding: 0.75rem 1rem; border-bottom: 1px solid var(--sl-color-gray-5); }
.terminal-title { font-size: var(--sl-text-lg); margin: 0; }
.terminal-badge { margin: 0.25rem 0 0; font-size: var(--sl-text-sm); color: var(--sl-color-gray-2); }
.challenge { padding: 0.75rem 1rem; border-bottom: 1px solid var(--sl-color-gray-5); font-size: var(--sl-text-sm); }
.challenge p { margin: 0.4rem 0 0; }
.challenge-select { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.challenge-select select { max-width: 100%; }
.step-count { font-weight: 600; color: var(--sl-color-accent-high); margin-inline-end: 0.25rem; }
.challenge-done { color: var(--academy-success); font-weight: 600; }
.challenge-explanation { background: var(--sl-color-accent-low); padding: 0.5rem 0.75rem; border-radius: 0.5rem; }
.terminal-output { background: #0b1020; color: #e6edf3; padding: 0.75rem 1rem; overflow: auto; min-height: 10rem; font-family: var(--__sl-font-mono); font-size: 0.85rem; }
.terminal-welcome { color: #9fb3c8; margin: 0; }
.entry { margin-bottom: 0.75rem; }
.entry p { margin: 0; }
.entry-command { color: #ffffff; }
.prompt { color: #7ee787; font-family: var(--__sl-font-mono); white-space: nowrap; }
.entry-kind { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.15rem !important; }
.kind-recorded { color: #79c0ff; } .kind-simulated { color: #d2a8ff; } .kind-error { color: #ffa198; } .kind-blocked { color: #ffa657; } .kind-info { color: #9fb3c8; }
.entry-output { margin: 0.25rem 0 0; padding: 0; background: transparent; color: inherit; white-space: pre-wrap; word-break: break-word; border: 0; font-size: inherit; }
.entry-note { color: #c9d1d9; font-style: italic; margin-top: 0.25rem !important; font-family: var(--sl-font); }
.terminal-form { display: flex; gap: 0.5rem; align-items: center; padding: 0.6rem 1rem; background: #0b1020; border-top: 1px solid #30363d; }
.terminal-input { flex: 1; min-width: 0; background: #0d1426; color: #ffffff; border: 1px solid #30363d; border-radius: 0.4rem; padding: 0.4rem 0.5rem; font-family: var(--__sl-font-mono); font-size: 0.9rem; }
.terminal-input:focus-visible, .run-button:focus-visible, .link-button:focus-visible, select:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
.run-button { background: var(--sl-color-accent); color: var(--sl-color-black); border: 0; border-radius: 0.4rem; padding: 0.4rem 0.9rem; font-weight: 600; cursor: pointer; }
.suggestions, .terminal-help { padding: 0.4rem 1rem; margin: 0; font-size: var(--sl-text-xs); color: var(--sl-color-gray-2); }
.suggestions code { margin-inline-end: 0.5rem; }
.link-button { background: none; border: 0; padding: 0; color: var(--sl-color-text-accent); text-decoration: underline; cursor: pointer; font: inherit; }
@media (max-width: 40rem) { .terminal-form { flex-wrap: wrap; } .prompt { white-space: normal; font-size: 0.75rem; } }
</style>
