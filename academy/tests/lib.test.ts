import { describe, expect, it } from 'vitest';
import cli from '../src/data/generated/cli.json';
import tools from '../src/data/generated/tools.json';
import transcripts from '../src/data/transcripts.json';
import { CHALLENGES } from '../src/lib/challenges';
import { deriveApproval, deriveRisk, SCENARIOS, type Operation } from '../src/lib/permissions';
import { ProgressStore, STORAGE_KEY, emptyState, levelFor, parseState, percent, type StorageLike } from '../src/lib/progress';
import { TerminalSimulator, cliArguments, tokenize } from '../src/lib/terminal';

function memory(): StorageLike & { data: Map<string, string> } {
	const data = new Map<string, string>();
	return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: (k) => void data.delete(k) };
}

describe('progress store', () => {
	it('persists completion, quizzes, checks and challenges', () => {
		const storage = memory(); const store = new ProgressStore(storage);
		store.setCompleted('instalacion-primera-vez', true);
		store.recordQuiz('quiz-cli', 2, 4); store.recordQuiz('quiz-cli', 4, 4); store.recordQuiz('quiz-cli', 1, 4);
		store.toggleCheck('instalacion-primera-vez', 'python', true);
		store.completeChallenge('reto-primera-instalacion');
		const reloaded = new ProgressStore(storage).load();
		expect(reloaded.completed).toEqual(['instalacion-primera-vez']);
		expect(reloaded.quizzes['quiz-cli']).toEqual({ score: 4, total: 4, attempts: 3, passed: true });
		expect(reloaded.checks['instalacion-primera-vez']).toEqual(['python']);
		expect(reloaded.challenges).toEqual(['reto-primera-instalacion']);
		store.setCompleted('instalacion-primera-vez', false);
		expect(store.isCompleted('instalacion-primera-vez')).toBe(false);
	});

	it('ignores corrupted storage and survives unavailable storage', () => {
		const storage = memory(); storage.setItem(STORAGE_KEY, '{not json');
		expect(new ProgressStore(storage).load()).toEqual(emptyState());
		storage.setItem(STORAGE_KEY, JSON.stringify({ schema: 99, completed: [] }));
		expect(new ProgressStore(storage).load()).toEqual(emptyState());
		const broken: StorageLike = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); }, removeItem: () => { throw new Error('blocked'); } };
		const store = new ProgressStore(broken);
		expect(() => store.setCompleted('a', true)).not.toThrow();
		expect(store.load()).toEqual(emptyState());
	});

	it('exports, rejects invalid imports and imports valid files', () => {
		const a = new ProgressStore(memory()); a.setCompleted('cli-doctor', true);
		const exported = a.exportJson();
		const b = new ProgressStore(memory());
		expect(b.importJson('nope').ok).toBe(false);
		expect(b.importJson(JSON.stringify({ schema: 1, completed: ['<script>'] })).ok).toBe(false);
		expect(b.importJson(JSON.stringify({ schema: 1, completed: [], quizzes: { q: { score: 9, total: 2, attempts: 1 } } })).ok).toBe(false);
		expect(b.importJson(exported)).toEqual({ ok: true });
		expect(b.load().completed).toEqual(['cli-doctor']);
		b.reset(); expect(b.load()).toEqual(emptyState());
	});

	it('computes percentages and educational levels', () => {
		expect(percent(['a', 'x'], ['a', 'b', 'c', 'd'])).toBe(25);
		expect(percent([], [])).toBe(0);
		expect(levelFor(0).id).toBe('explorer'); expect(levelFor(25).id).toBe('developer');
		expect(levelFor(60).id).toBe('advanced'); expect(levelFor(95).id).toBe('contributor');
		expect(parseState(null)).toBeNull();
	});
});

describe('terminal simulator', () => {
	const fresh = () => new TerminalSimulator(cli, transcripts);

	it('tokenizes like a shell without expanding anything', () => {
		expect(tokenize(`python -m pallaquino_cli risk "agregar roles" --json`)).toEqual(['python', '-m', 'pallaquino_cli', 'risk', 'agregar roles', '--json']);
		expect(tokenize(`a '{"x": 1}' ""`)).toEqual(['a', '{"x": 1}', '']);
		expect(cliArguments(['pallaquino', 'doctor'])).toEqual(['doctor']);
		expect(cliArguments(['py', '-m', 'pallaquino_cli', 'stack'])).toEqual(['stack']);
		expect(cliArguments(['python', 'script.py'])).toBeNull();
	});

	it('requires the framework directory, like the real module', () => {
		const t = fresh();
		const outside = t.run('python -m pallaquino_cli doctor');
		expect(outside.kind).toBe('error'); expect(outside.lines[0]).toContain('No module named pallaquino_cli');
		// --version and --help need the importable module too; only the installed `pallaquino` command works from anywhere.
		expect(fresh().run('python -m pallaquino_cli --version').lines[0]).toContain('No module named pallaquino_cli');
		const installed = fresh().run('pallaquino --version');
		expect(installed.kind).toBe('recorded'); expect(installed.note).toContain('pip install -e');
		expect(t.run('cd pallaquino-os').kind).toBe('error');
		expect(t.run('git clone https://github.com/jylmdev-cyber/pallaquino-os.git').kind).toBe('simulated');
		expect(t.run('cd pallaquino-os/universal_ai_fullstack_orchestrator').exitCode).toBe(0);
		expect(t.prompt()).toContain('universal_ai_fullstack_orchestrator');
		const doctor = t.run('python -m pallaquino_cli doctor');
		expect(doctor.kind).toBe('recorded'); expect(doctor.transcriptId).toBe('doctor');
	});

	it('answers every recorded transcript and reproduces argparse errors', () => {
		const t = fresh(); t.run('git clone https://github.com/jylmdev-cyber/pallaquino-os.git'); t.run('cd pallaquino-os/universal_ai_fullstack_orchestrator');
		for (const record of transcripts.commands) {
			const response = t.run(record.command);
			expect(response.kind, record.command).toBe('recorded');
			expect(response.exitCode).toBe(record.exit_code);
		}
		const invalid = t.run('python -m pallaquino_cli deploy');
		expect(invalid.exitCode).toBe(2); expect(invalid.lines.join('\n')).toContain("invalid choice: 'deploy'");
		expect(t.run('python -m pallaquino_cli doctor --turbo').lines[0]).toContain('unrecognized arguments: --turbo');
		const unrecorded = t.run('python -m pallaquino_cli memory status');
		expect(unrecorded.kind).toBe('info'); expect(unrecorded.lines[0]).toContain('existe en la CLI real');
	});

	it('never runs system commands or shell operators', () => {
		const t = fresh();
		for (const cmd of ['rm -rf /', 'sudo ls', 'curl https://evil.example', 'powershell -c x', 'del C:\\x', 'git push origin main', 'pip install x']) {
			expect(t.run(cmd).kind, cmd).toBe('blocked');
		}
		expect(t.run('python -m pallaquino_cli doctor; rm -rf /').kind).toBe('blocked');
		expect(t.run('echo $(whoami)').kind).toBe('blocked');
		expect(t.run('x'.repeat(600)).kind).toBe('error');
		expect(t.run('ls').lines).toEqual(['(carpeta vacía)']);
	});

	it('completes subcommands and flags from the real CLI reference', () => {
		const t = fresh();
		expect(t.complete('python -m pallaquino_cli doc')).toEqual(['python -m pallaquino_cli doctor']);
		expect(t.complete('python -m pallaquino_cli validate --int')).toEqual(['python -m pallaquino_cli validate --integrity-only']);
		expect(t.complete('git c')).toEqual(['git clone https://github.com/jylmdev-cyber/pallaquino-os.git']);
	});

	it('keeps history and resets', () => {
		const t = fresh(); t.run('python --version'); t.run('git --version');
		expect(t.run('historial').lines).toHaveLength(3);
		t.run('reiniciar'); expect(t.state).toEqual({ cwd: 'home', cloned: false, history: [] });
	});
});

describe('guided challenges', () => {
	it('every accepted command is either recorded or a supported helper', () => {
		const t = new TerminalSimulator(cli, transcripts);
		for (const challenge of CHALLENGES) {
			t.reset(); t.run('git clone https://github.com/jylmdev-cyber/pallaquino-os.git');
			for (const step of challenge.steps) {
				expect(step.accepts(step.hint), `${challenge.id}: ${step.hint}`).toBe(true);
				if (step.hint.startsWith('cd ') || step.hint.startsWith('git clone')) { t.reset(); continue; }
				t.state.cloned = true; t.state.cwd = 'framework';
				const response = t.run(step.hint);
				expect(['recorded', 'simulated']).toContain(response.kind);
			}
		}
	});
});

describe('permission model matches the real tool contracts', () => {
	it('derives the same risk and approval as PALLAQUINO for every builtin tool', () => {
		for (const tool of tools.builtin) {
			expect(deriveRisk(tool.operation as Operation, tool.capabilities), tool.tool_id).toBe(tool.risk);
			expect(deriveApproval(tool.operation as Operation, 'builtin', tool.capabilities), tool.tool_id).toBe(tool.approval);
		}
	});

	it('uses real builtin tools in builtin scenarios', () => {
		const ids = new Set(tools.builtin.map((t) => t.tool_id));
		for (const s of SCENARIOS.filter((s) => s.source === 'builtin')) {
			expect(ids.has(s.toolId), s.toolId).toBe(true);
			const real = tools.builtin.find((t) => t.tool_id === s.toolId)!;
			expect(s.operation).toBe(real.operation); expect(s.capabilities).toEqual(real.capabilities);
		}
		expect(deriveApproval('READ_ONLY', 'untrusted', ['FILE_READ'])).toBe('grant');
		expect(deriveApproval('WRITE_OPERATION', 'trusted', ['DEPLOYMENT'])).toBe('per_call');
	});
});
