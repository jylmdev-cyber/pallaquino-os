/**
 * Component tests: each interactive island is mounted in jsdom, exercised like a learner would, and checked with axe-core in its
 * hydrated state (the build-time check in scripts/validate-a11y.mjs only sees the server-rendered markup).
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import axe from 'axe-core';
import AgentExplorer from '../src/components/AgentExplorer.vue';
import CheckList from '../src/components/CheckList.vue';
import CommandExplorer from '../src/components/CommandExplorer.vue';
import DagPlayer from '../src/components/DagPlayer.vue';
import FlowDiagram from '../src/components/FlowDiagram.vue';
import InteractiveTerminal from '../src/components/InteractiveTerminal.vue';
import LearningProgress from '../src/components/LearningProgress.vue';
import LessonComplete from '../src/components/LessonComplete.vue';
import PermissionSimulator from '../src/components/PermissionSimulator.vue';
import QualityGates from '../src/components/QualityGates.vue';
import QuizPlayer from '../src/components/QuizPlayer.vue';
import pipeline from '../src/data/generated/pipeline.json';
import { STORAGE_KEY } from '../src/lib/progress';
import { progressStore } from '../src/lib/useProgress';

const mounted: VueWrapper[] = [];
function render<T>(component: T, props: Record<string, unknown> = {}) {
	const wrapper = mount(component as never, { props: props as never, attachTo: document.body });
	mounted.push(wrapper);
	return wrapper;
}

/** axe-core on the mounted component; layout-dependent rules cannot run in jsdom. */
async function expectAccessible(wrapper: VueWrapper) {
	const result = await axe.run(wrapper.element as HTMLElement, {
		rules: { 'color-contrast': { enabled: false }, 'target-size': { enabled: false }, region: { enabled: false } },
	});
	expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

const stored = () => JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');

beforeEach(() => { localStorage.clear(); progressStore().reset(); });
afterEach(() => { while (mounted.length) mounted.pop()!.unmount(); document.body.innerHTML = ''; });

const QUESTIONS = [
	{ question: '¿Uno?', options: [{ text: 'sí', correct: true, why: 'a' }, { text: 'no', correct: false, why: 'b' }] },
	{ question: '¿Dos?', options: [{ text: 'sí', correct: false, why: 'c' }, { text: 'no', correct: true, why: 'd' }] },
];

describe('QuizPlayer', () => {
	it('scores the answers, explains them and stores the best result locally', async () => {
		const quiz = render(QuizPlayer, { id: 'quiz-test', title: 'Prueba', questions: QUESTIONS });
		await flushPromises();
		expect(quiz.find('button[type=submit]').attributes('disabled')).toBeDefined();
		const radios = quiz.findAll('input[type=radio]');
		await radios[0].setValue(true); await radios[3].setValue(true);
		await quiz.find('form').trigger('submit');
		expect(quiz.text()).toContain('Resultado: 2/2');
		expect(quiz.text()).toContain('Correcta');
		expect(stored().quizzes['quiz-test']).toMatchObject({ score: 2, total: 2 });
		await expectAccessible(quiz);
	});

	it('asks to retry below the 70 % pass mark', async () => {
		const quiz = render(QuizPlayer, { id: 'quiz-fail', title: 'Prueba', questions: QUESTIONS });
		const radios = quiz.findAll('input[type=radio]');
		await radios[1].setValue(true); await radios[3].setValue(true);
		await quiz.find('form').trigger('submit');
		expect(quiz.text()).toContain('Resultado: 1/2');
		expect(quiz.text()).toContain('vuelve a intentarlo');
	});
});

describe('InteractiveTerminal', () => {
	async function run(terminal: VueWrapper, command: string) {
		await terminal.find('input.terminal-input').setValue(command);
		await terminal.find('form.terminal-form').trigger('submit');
	}

	it('replays a recorded transcript only inside the framework folder and blocks system commands', async () => {
		const terminal = render(InteractiveTerminal);
		await flushPromises();
		await run(terminal, 'python -m pallaquino_cli doctor');
		expect(terminal.find('[role=log]').text()).toContain('No module named pallaquino_cli');
		await run(terminal, 'git clone https://github.com/jylmdev-cyber/pallaquino-os.git');
		await run(terminal, 'cd pallaquino-os/universal_ai_fullstack_orchestrator');
		await run(terminal, 'python -m pallaquino_cli validate --integrity-only --json');
		const log = terminal.find('[role=log]').text();
		expect(log).toMatch(/SALIDA REAL GRABADA/i);
		expect(log).toContain('"ok": true');
		await run(terminal, 'rm -rf /');
		expect(terminal.find('[role=log]').text()).toMatch(/BLOQUEADO/i);
		await expectAccessible(terminal);
	});

	it('advances the guided challenge with the expected commands', async () => {
		const terminal = render(InteractiveTerminal, { challenge: 'reto-primera-instalacion' });
		await flushPromises();
		expect(terminal.text()).toContain('Paso 1 de 8');
		await run(terminal, 'python --version');
		expect(terminal.text()).toContain('Paso 2 de 8');
		await run(terminal, 'git --version');
		expect(terminal.text()).toContain('Paso 3 de 8');
	});
});

describe('progress components', () => {
	it('LessonComplete toggles the lesson in local progress', async () => {
		const button = render(LessonComplete, { lessonId: 'leccion-x' });
		await flushPromises();
		await button.find('button').trigger('click');
		expect(stored().completed).toContain('leccion-x');
		expect(button.find('button').attributes('aria-pressed')).toBe('true');
		await expectAccessible(button);
	});

	it('CheckList stores each ticked item', async () => {
		const list = render(CheckList, { group: 'grupo', items: [{ id: 'a', label: 'Primero' }, { id: 'b', label: 'Segundo' }] });
		await flushPromises();
		await list.findAll('input[type=checkbox]')[1].setValue(true);
		expect(stored().checks.grupo).toEqual(['b']);
		await expectAccessible(list);
	});

	it('LearningProgress shows the level for the completed share of lessons', async () => {
		const lessons = Array.from({ length: 4 }, (_, i) => ({ id: `l${i}`, title: `Lección ${i}`, path: 'cli', href: `/l${i}/` }));
		progressStore().setCompleted('l0', true);
		const panel = render(LearningProgress, { lessons });
		await flushPromises();
		expect(panel.text()).toContain('25');
		expect(panel.text()).toMatch(/Developer/);
		await expectAccessible(panel);
	});
});

describe('walkthroughs and explorers', () => {
	it.each([
		['FlowDiagram', FlowDiagram], ['DagPlayer', DagPlayer], ['QualityGates', QualityGates], ['PermissionSimulator', PermissionSimulator],
		['AgentExplorer', AgentExplorer], ['CommandExplorer', CommandExplorer],
	])('%s renders accessibly', async (_name, component) => {
		const wrapper = render(component);
		await flushPromises();
		expect(wrapper.text().length).toBeGreaterThan(50);
		await expectAccessible(wrapper);
	});

	it('DagPlayer completes the real example plan step by step', async () => {
		const dag = render(DagPlayer);
		const next = () => dag.findAll('button').find((b) => b.text().includes('Avanzar'))!;
		for (let i = 0; i < 10 && next().attributes('disabled') === undefined; i += 1) await next().trigger('click');
		expect(next().attributes('disabled')).toBeDefined();
		expect(dag.text()).toContain('T04');
	});

	it('QualityGates sends a failed gate back to its real remediation stage', async () => {
		const gates = render(QualityGates);
		const security = gates.findAll('li').find((li) => li.find('strong').text() === 'SECURITY_CHECK')!;
		await security.find('input').setValue(true);
		const stage = pipeline.stages.find((s) => s.id === 'SECURITY_CHECK')!;
		expect(gates.find('.result').text()).toContain(`SECURITY_CHECK falló y el pipeline vuelve a ${stage.failure_return_to}`);
	});

	it('AgentExplorer filters the real registry', async () => {
		const explorer = render(AgentExplorer);
		await explorer.find('input[type=search]').setValue('migration_safety');
		expect(explorer.text()).toContain('migration_safety_reviewer');
	});
});
