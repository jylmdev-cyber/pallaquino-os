<script setup lang="ts">
import { computed, ref } from 'vue';
import { useProgress } from '../lib/useProgress';

export interface QuizOption { text: string; correct: boolean; why: string }
export interface QuizQuestion { question: string; options: QuizOption[] }

const props = defineProps<{ id: string; title: string; questions: QuizQuestion[] }>();
const { state, store } = useProgress();

const answers = ref<(number | null)[]>(props.questions.map(() => null));
const submitted = ref(false);
const score = computed(() => props.questions.filter((q, i) => answers.value[i] !== null && q.options[answers.value[i] as number].correct).length);
const complete = computed(() => answers.value.every((a) => a !== null));
const best = computed(() => state.value.quizzes[props.id]);

function submit() {
	if (!complete.value) return;
	submitted.value = true;
	store().recordQuiz(props.id, score.value, props.questions.length);
}

function retry() {
	answers.value = props.questions.map(() => null); submitted.value = false;
}
</script>

<template>
	<section class="quiz" :aria-labelledby="`${id}-title`">
		<h2 :id="`${id}-title`" class="quiz-title">{{ title }}</h2>
		<p class="quiz-meta">
			{{ questions.length }} preguntas · evaluación opcional.
			<span v-if="best"> Mejor resultado: {{ best.score }}/{{ best.total }} en {{ best.attempts }} intento(s).</span>
		</p>
		<form @submit.prevent="submit">
			<fieldset v-for="(q, qi) in questions" :key="qi" class="question" :disabled="submitted">
				<legend>{{ qi + 1 }}. {{ q.question }}</legend>
				<div v-for="(o, oi) in q.options" :key="oi" class="option">
					<label :class="{ chosen: answers[qi] === oi, right: submitted && o.correct, wrong: submitted && answers[qi] === oi && !o.correct }">
						<input type="radio" :name="`${id}-${qi}`" :value="oi" v-model="answers[qi]" />
						<span>{{ o.text }}</span>
					</label>
					<p v-if="submitted && (answers[qi] === oi || o.correct)" class="why" :class="o.correct ? 'why-right' : 'why-wrong'">
						<strong>{{ o.correct ? 'Correcta' : 'Incorrecta' }}:</strong> {{ o.why }}
					</p>
				</div>
			</fieldset>
			<div class="quiz-actions" aria-live="polite">
				<button v-if="!submitted" type="submit" class="quiz-button" :disabled="!complete">Comprobar respuestas</button>
				<template v-else>
					<p class="quiz-result" :class="score / questions.length >= 0.7 ? 'pass' : 'retry'">
						Resultado: {{ score }}/{{ questions.length }}.
						{{ score / questions.length >= 0.7 ? '¡Bien hecho! Has superado la evaluación.' : 'Revisa las explicaciones y vuelve a intentarlo.' }}
					</p>
					<button type="button" class="quiz-button" @click="retry">Reintentar</button>
				</template>
				<p v-if="!submitted && !complete" class="quiz-hint">Responde todas las preguntas para comprobar.</p>
			</div>
		</form>
	</section>
</template>

<style scoped>
.quiz { border: 1px solid var(--sl-color-gray-5); border-radius: 0.75rem; padding: 1rem 1.25rem; margin-block: 1.5rem; }
.quiz-title { margin: 0; font-size: var(--sl-text-xl); }
.quiz-meta { color: var(--sl-color-gray-2); font-size: var(--sl-text-sm); margin: 0.25rem 0 0.75rem; }
.question { border: 0; padding: 0; margin: 0 0 1rem; }
.question legend { font-weight: 600; margin-bottom: 0.5rem; }
.option label { display: flex; gap: 0.6rem; align-items: flex-start; padding: 0.45rem 0.6rem; border-radius: 0.5rem; border: 1px solid transparent; cursor: pointer; }
.option label:hover { background: var(--sl-color-gray-6); }
.option label.chosen { border-color: var(--sl-color-gray-4); }
.option label.right { border-color: var(--academy-success); }
.option label.wrong { border-color: var(--academy-danger); }
.option input { margin-top: 0.3rem; }
.option input:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
.why { margin: 0.2rem 0 0.4rem 2rem; font-size: var(--sl-text-sm); }
.why-right { color: var(--academy-success); } .why-wrong { color: var(--academy-danger); }
.quiz-actions p { margin: 0.5rem 0; }
.quiz-button { background: var(--sl-color-accent); color: var(--sl-color-black); border: 0; border-radius: 0.5rem; padding: 0.5rem 1rem; font-weight: 600; cursor: pointer; }
.quiz-button:disabled { opacity: 0.55; cursor: not-allowed; }
.quiz-button:focus-visible { outline: 3px solid var(--sl-color-accent-high); outline-offset: 2px; }
.quiz-result.pass { color: var(--academy-success); font-weight: 600; } .quiz-result.retry { color: var(--academy-warning); font-weight: 600; }
.quiz-hint { font-size: var(--sl-text-sm); color: var(--sl-color-gray-2); }
</style>
