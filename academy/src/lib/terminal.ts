/**
 * PALLAQUINO Terminal Playground engine: a deterministic simulator that runs entirely in the browser.
 *
 * It never executes anything. PALLAQUINO commands are answered with transcripts recorded from a real clone (see
 * scripts/capture_transcripts.py); commands the real CLI has but the simulator did not record get an honest "not recorded" answer
 * that cites the generated CLI reference; argparse errors and the "run it from the framework directory" error are reproduced; and
 * operating-system commands that could change anything are refused. A small virtual file tree only explains `git clone`/`cd`.
 */
export interface CliArgument { name: string; flags: string[]; positional: boolean; help: string | null; choices: unknown; takes_value: boolean }
export interface CliCommand { name: string; help: string | null; arguments: CliArgument[] }
export interface CliReference { commands: CliCommand[] }
export interface Transcript { id: string; command: string; cwd: string; exit_code: number; note: string; output: string; truncated: boolean }
export interface Transcripts { captured_on: string; platform: string; commands: Transcript[] }

export type ResponseKind = 'recorded' | 'simulated' | 'error' | 'blocked' | 'info' | 'clear';
export interface TerminalResponse { kind: ResponseKind; lines: string[]; exitCode: number; note?: string; transcriptId?: string }

export type Location = 'home' | 'repo' | 'framework';
export interface SessionState { cwd: Location; cloned: boolean; history: string[] }

export const REPO_URL = 'https://github.com/jylmdev-cyber/pallaquino-os.git';
const PROMPTS: Record<Location, string> = { home: '~', repo: '~/pallaquino-os', framework: '~/pallaquino-os/universal_ai_fullstack_orchestrator' };
const BLOCKED = new Set(['rm', 'del', 'rmdir', 'rd', 'sudo', 'su', 'curl', 'wget', 'chmod', 'chown', 'mv', 'cp', 'powershell', 'pwsh', 'cmd', 'bash', 'sh', 'zsh',
	'format', 'mkfs', 'dd', 'shutdown', 'reboot', 'kill', 'taskkill', 'npm', 'pip', 'pip3', 'docker', 'ssh', 'scp', 'eval', 'exec', 'source']);
const LISTINGS: Record<Location, string[]> = {
	home: [],
	repo: ['.github/', 'docs/', 'scripts/', 'universal_ai_fullstack_orchestrator/', 'CHANGELOG.md', 'MIGRATION_GUIDE.md', 'README.md',
		'PALLAQUINO_autonomous_engineering_os.zip', 'PALLAQUINO_autonomous_engineering_os.sha256'],
	framework: ['AI_ENTRYPOINT.md', 'agents/', 'continuity/', 'examples/', 'governance/', 'pallaquino_cli/', 'pipeline/', 'registry/', 'scripts/', 'skills/',
		'tests/', 'manifest.json', 'pyproject.toml'],
};

/** Minimal shell-like tokenizer: whitespace separation with single and double quotes; no expansion of any kind. */
export function tokenize(input: string): string[] {
	const tokens: string[] = []; let current = ''; let quote: string | null = null; let started = false;
	for (const ch of input.trim()) {
		if (quote) { if (ch === quote) quote = null; else current += ch; continue; }
		if (ch === '"' || ch === "'") { quote = ch; started = true; continue; }
		if (/\s/.test(ch)) { if (started || current) { tokens.push(current); current = ''; started = false; } continue; }
		current += ch; started = true;
	}
	if (started || current) tokens.push(current);
	return tokens;
}

/** Returns the PALLAQUINO arguments when the input invokes the CLI (`pallaquino ...`, `python -m pallaquino_cli ...`), else null. */
export function cliArguments(tokens: string[]): string[] | null {
	if (tokens[0] === 'pallaquino') return tokens.slice(1);
	if (['python', 'python3', 'py'].includes(tokens[0]) && tokens[1] === '-m' && tokens[2] === 'pallaquino_cli') return tokens.slice(3);
	return null;
}

export class TerminalSimulator {
	state: SessionState = { cwd: 'home', cloned: false, history: [] };
	private byArgs = new Map<string, Transcript>();
	private commands = new Map<string, CliCommand>();

	constructor(cli: CliReference, private transcripts: Transcripts) {
		for (const c of cli.commands) this.commands.set(c.name, c);
		for (const t of transcripts.commands) {
			const args = cliArguments(tokenize(t.command));
			if (args) this.byArgs.set(JSON.stringify(args), t);
		}
	}

	prompt(): string {
		return `${PROMPTS[this.state.cwd]} $`;
	}

	reset(): void {
		this.state = { cwd: 'home', cloned: false, history: [] };
	}

	recordedCommands(): string[] {
		return this.transcripts.commands.map((t) => t.command);
	}

	run(input: string): TerminalResponse {
		const text = input.trim();
		if (!text) return { kind: 'info', lines: [], exitCode: 0 };
		if (text.length > 500) return { kind: 'error', lines: ['El simulador acepta comandos de hasta 500 caracteres.'], exitCode: 2 };
		this.state.history.push(text);
		if (/[;&|`$><]/.test(text)) return { kind: 'blocked', exitCode: 126, lines: ['El simulador no interpreta operadores de shell (; & | ` $ > <).'], note: 'Escribe un comando por línea.' };
		const tokens = tokenize(text); const [head] = tokens;
		const args = cliArguments(tokens);
		if (args) return this.pallaquino(args);
		switch (head.toLowerCase()) {
			case 'help': case 'ayuda': return this.help();
			case 'clear': case 'cls': case 'limpiar': return { kind: 'clear', lines: [], exitCode: 0 };
			case 'reset': case 'reiniciar': this.reset(); return { kind: 'info', exitCode: 0, lines: ['Simulador reiniciado: vuelves a tu carpeta personal, sin el repositorio clonado.'] };
			case 'history': case 'historial': return { kind: 'info', exitCode: 0, lines: this.state.history.map((h, i) => `${String(i + 1).padStart(3)}  ${h}`) };
			case 'pwd': return { kind: 'simulated', exitCode: 0, lines: [PROMPTS[this.state.cwd]] };
			case 'ls': case 'dir': return { kind: 'simulated', exitCode: 0, lines: LISTINGS[this.state.cwd].length ? LISTINGS[this.state.cwd] : (this.state.cloned ? ['pallaquino-os/'] : ['(carpeta vacía)']) };
			case 'cd': return this.cd(tokens[1]);
			case 'git': return this.git(tokens);
			case 'python': case 'python3': case 'py':
				if (tokens[1] === '--version' || tokens[1] === '-V') return { kind: 'simulated', exitCode: 0, lines: ['Python 3.11.15'], note: 'Salida de ejemplo. En tu equipo debe ser Python 3.11 o superior.' };
				return { kind: 'error', exitCode: 1, lines: ['El simulador solo reconoce `python --version` y `python -m pallaquino_cli ...`.'] };
		}
		if (BLOCKED.has(head.toLowerCase())) return { kind: 'blocked', exitCode: 126, lines: [`«${head}» está bloqueado: el simulador nunca ejecuta comandos del sistema ni modifica archivos.`] };
		return { kind: 'error', exitCode: 127, lines: [`${head}: comando no disponible en el simulador. Escribe «ayuda» para ver qué puedes practicar.`] };
	}

	private help(): TerminalResponse {
		return { kind: 'info', exitCode: 0, lines: [
			'Comandos de PALLAQUINO (salidas reales grabadas):',
			...this.recordedCommands().map((c) => `  ${c}`),
			'',
			'Comandos de apoyo simulados: git --version, git clone <url>, cd, ls, pwd, python --version',
			'Utilidades: ayuda, historial, limpiar, reiniciar. Tab completa; ↑/↓ recorren el historial.',
		] };
	}

	private cd(target?: string): TerminalResponse {
		const dest = (target ?? '~').replace(/\\/g, '/').replace(/\/$/, '');
		const map: Record<string, Partial<Record<Location, Location>>> = {
			'~': { home: 'home', repo: 'home', framework: 'home' },
			'..': { repo: 'home', framework: 'repo', home: 'home' },
			'pallaquino-os': { home: 'repo' },
			'pallaquino-os/universal_ai_fullstack_orchestrator': { home: 'framework' },
			'universal_ai_fullstack_orchestrator': { repo: 'framework' },
		};
		const next = map[dest]?.[this.state.cwd];
		if (!next || (next !== 'home' && !this.state.cloned)) return { kind: 'error', exitCode: 1, lines: [`cd: ${target}: no existe ese directorio`], note: this.state.cloned ? undefined : 'Primero clona el repositorio con git clone.' };
		this.state.cwd = next;
		return { kind: 'simulated', exitCode: 0, lines: [] };
	}

	private git(tokens: string[]): TerminalResponse {
		if (tokens[1] === '--version') return { kind: 'simulated', exitCode: 0, lines: ['git version 2.56.0'], note: 'Salida de ejemplo. Cualquier versión reciente de Git sirve.' };
		if (tokens[1] === 'clone') {
			if (tokens[2] !== REPO_URL) return { kind: 'error', exitCode: 128, lines: [`El simulador solo clona ${REPO_URL}`] };
			if (this.state.cwd !== 'home') return { kind: 'error', exitCode: 128, lines: ['Clona desde tu carpeta personal (escribe «cd ~»).'] };
			if (this.state.cloned) return { kind: 'error', exitCode: 128, lines: ["fatal: destination path 'pallaquino-os' already exists and is not an empty directory."] };
			this.state.cloned = true;
			return { kind: 'simulated', exitCode: 0, lines: ["Cloning into 'pallaquino-os'...", 'remote: Enumerating objects... done.', 'Resolving deltas: 100%, done.'],
				note: 'Simulación: no se descargó nada. En tu equipo, este comando crea la carpeta pallaquino-os.' };
		}
		if (tokens[1] === 'push' || tokens[1] === 'reset' || tokens[1] === 'clean') return { kind: 'blocked', exitCode: 126, lines: [`git ${tokens[1]} está bloqueado en el simulador.`] };
		return { kind: 'error', exitCode: 1, lines: ['El simulador solo reconoce git --version y git clone.'] };
	}

	private pallaquino(args: string[]): TerminalResponse {
		const informational = args.length === 1 && ['--help', '-h', '--version'].includes(args[0]);
		if (this.state.cwd !== 'framework' && !informational) {
			return { kind: 'error', exitCode: 1, lines: ['python: No module named pallaquino_cli'],
				note: 'Sin instalar el paquete, el módulo solo existe dentro de pallaquino-os/universal_ai_fullstack_orchestrator. Entra con cd antes de ejecutarlo.' };
		}
		const recorded = this.byArgs.get(JSON.stringify(args));
		if (recorded) return { kind: 'recorded', exitCode: recorded.exit_code, lines: recorded.output.split('\n'), note: recorded.note, transcriptId: recorded.id };
		if (informational && args[0] === '-h') return this.pallaquino(['--help']);
		const sub = args.find((a) => !a.startsWith('-'));
		if (!sub) return { kind: 'error', exitCode: 2, lines: ['usage: pallaquino [-h] [--version] {…} ...', 'pallaquino: error: the following arguments are required: command'] };
		const command = this.commands.get(sub);
		if (!command) {
			return { kind: 'error', exitCode: 2, lines: ['usage: pallaquino [-h] [--version] {…} ...',
				`pallaquino: error: argument command: invalid choice: '${sub}' (choose from ${[...this.commands.keys()].map((c) => `'${c}'`).join(', ')})`] };
		}
		const known = new Set(command.arguments.flatMap((a) => a.flags).concat(['-h', '--help']));
		const unknown = args.filter((a) => a.startsWith('-') && !known.has(a.split('=')[0]));
		if (unknown.length) return { kind: 'error', exitCode: 2, lines: [`pallaquino: error: unrecognized arguments: ${unknown.join(' ')}`] };
		return { kind: 'info', exitCode: 0, lines: [`«${sub}» existe en la CLI real: ${command.help ?? ''}`, 'El simulador no tiene grabada esta combinación exacta de argumentos.'],
			note: 'Ejecútalo en tu equipo, o consulta la referencia de la CLI para ver sus opciones.' };
	}

	complete(partial: string): string[] {
		const tokens = tokenize(partial); const endsWithSpace = /\s$/.test(partial);
		const args = cliArguments(tokens);
		if (args) {
			const prefix = partial.slice(0, partial.length - (endsWithSpace ? 0 : (tokens.at(-1)?.length ?? 0)));
			const current = endsWithSpace ? '' : (args.at(-1) ?? '');
			const subcommand = args.find((a) => !a.startsWith('-') && this.commands.has(a));
			const pool = subcommand && (args.length > 1 || endsWithSpace)
				? (this.commands.get(subcommand)?.arguments.flatMap((a) => a.flags) ?? [])
				: [...this.commands.keys()];
			return pool.filter((c) => c.startsWith(current)).sort().map((c) => prefix + c);
		}
		const starters = ['python -m pallaquino_cli ', 'git clone ' + REPO_URL, 'git --version', 'python --version', 'cd pallaquino-os/universal_ai_fullstack_orchestrator', 'ayuda', 'limpiar', 'reiniciar'];
		return starters.filter((s) => s.startsWith(partial));
	}
}
