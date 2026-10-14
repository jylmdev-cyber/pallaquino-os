/**
 * Learning progress, kept only in this browser (localStorage). No account, no network, no secrets: the store holds lesson IDs,
 * quiz scores and checklist ticks. Every read is validated, so a corrupted or edited value is ignored instead of breaking the page,
 * and storage that is unavailable (private mode, blocked site data) degrades to an in-memory store.
 */
export const STORAGE_KEY = 'pallaquino-academy-progress-v1';
export const SCHEMA_VERSION = 1;

export interface QuizResult {
	score: number;
	total: number;
	attempts: number;
	passed: boolean;
}

export interface ProgressState {
	schema: number;
	completed: string[];
	quizzes: Record<string, QuizResult>;
	checks: Record<string, string[]>;
	challenges: string[];
}

export interface Level {
	id: 'explorer' | 'developer' | 'advanced' | 'contributor';
	label: string;
	minPercent: number;
	description: string;
}

/** Educational levels; they are not certifications. */
export const LEVELS: Level[] = [
	{ id: 'explorer', label: 'Explorer', minPercent: 0, description: 'Conoces qué es PALLAQUINO y sus conceptos.' },
	{ id: 'developer', label: 'Developer', minPercent: 25, description: 'Instalas, validas y usas la CLI con soltura.' },
	{ id: 'advanced', label: 'Advanced Developer', minPercent: 60, description: 'Orquestas, gobiernas herramientas e integras MCP.' },
	{ id: 'contributor', label: 'PALLAQUINO Contributor', minPercent: 90, description: 'Extiendes el framework con agentes, skills y plugins.' },
];

export function emptyState(): ProgressState {
	return { schema: SCHEMA_VERSION, completed: [], quizzes: {}, checks: {}, challenges: [] };
}

const ID = /^[a-z0-9][a-z0-9:_-]{0,120}$/;

function isStringArray(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((v) => typeof v === 'string' && ID.test(v));
}

/** Validate untrusted input (storage or an imported file); returns null when it is not a valid progress document. */
export function parseState(value: unknown): ProgressState | null {
	if (!value || typeof value !== 'object') return null;
	const v = value as Record<string, unknown>;
	if (v.schema !== SCHEMA_VERSION || !isStringArray(v.completed) || !isStringArray(v.challenges ?? [])) return null;
	const quizzes: Record<string, QuizResult> = {};
	if (v.quizzes && typeof v.quizzes === 'object') {
		for (const [key, raw] of Object.entries(v.quizzes as Record<string, unknown>)) {
			const q = raw as Record<string, unknown>;
			if (!ID.test(key) || typeof q?.score !== 'number' || typeof q?.total !== 'number' || typeof q?.attempts !== 'number') return null;
			if (q.score < 0 || q.total < 1 || q.score > q.total) return null;
			quizzes[key] = { score: q.score, total: q.total, attempts: q.attempts, passed: Boolean(q.passed) };
		}
	}
	const checks: Record<string, string[]> = {};
	if (v.checks && typeof v.checks === 'object') {
		for (const [key, raw] of Object.entries(v.checks as Record<string, unknown>)) {
			if (!ID.test(key) || !isStringArray(raw)) return null;
			checks[key] = [...new Set(raw)];
		}
	}
	return { schema: SCHEMA_VERSION, completed: [...new Set(v.completed)], quizzes, checks, challenges: [...new Set((v.challenges as string[]) ?? [])] };
}

export interface StorageLike {
	getItem(key: string): string | null;
	setItem(key: string, value: string): void;
	removeItem(key: string): void;
}

function memoryStorage(): StorageLike {
	const map = new Map<string, string>();
	return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => void map.set(k, v), removeItem: (k) => void map.delete(k) };
}

export function defaultStorage(): StorageLike {
	try {
		const s = globalThis.localStorage;
		const probe = '__pallaquino_probe__';
		s.setItem(probe, '1'); s.removeItem(probe);
		return s;
	} catch {
		return memoryStorage();
	}
}

export class ProgressStore {
	private listeners = new Set<(state: ProgressState) => void>();

	constructor(private storage: StorageLike = defaultStorage()) {}

	load(): ProgressState {
		try {
			const raw = this.storage.getItem(STORAGE_KEY);
			return (raw && parseState(JSON.parse(raw))) || emptyState();
		} catch {
			return emptyState();
		}
	}

	private save(state: ProgressState): ProgressState {
		try { this.storage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* storage full or blocked: keep the in-page state */ }
		this.listeners.forEach((fn) => fn(state));
		if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('pallaquino-progress', { detail: state }));
		return state;
	}

	subscribe(fn: (state: ProgressState) => void): () => void {
		this.listeners.add(fn);
		return () => this.listeners.delete(fn);
	}

	setCompleted(lessonId: string, done: boolean): ProgressState {
		const state = this.load();
		const set = new Set(state.completed);
		if (done) set.add(lessonId); else set.delete(lessonId);
		return this.save({ ...state, completed: [...set].sort() });
	}

	isCompleted(lessonId: string): boolean {
		return this.load().completed.includes(lessonId);
	}

	recordQuiz(quizId: string, score: number, total: number, passMark = 0.7): ProgressState {
		const state = this.load(); const previous = state.quizzes[quizId];
		const best = previous && previous.score >= score ? previous.score : score;
		const result: QuizResult = { score: best, total, attempts: (previous?.attempts ?? 0) + 1, passed: best / total >= passMark };
		return this.save({ ...state, quizzes: { ...state.quizzes, [quizId]: result } });
	}

	toggleCheck(group: string, item: string, done: boolean): ProgressState {
		const state = this.load(); const set = new Set(state.checks[group] ?? []);
		if (done) set.add(item); else set.delete(item);
		return this.save({ ...state, checks: { ...state.checks, [group]: [...set].sort() } });
	}

	completeChallenge(id: string): ProgressState {
		const state = this.load();
		return this.save({ ...state, challenges: [...new Set([...state.challenges, id])].sort() });
	}

	reset(): ProgressState {
		try { this.storage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
		return this.save(emptyState());
	}

	exportJson(): string {
		return JSON.stringify({ ...this.load(), exported_by: 'PALLAQUINO Academy' }, null, 2);
	}

	/** Import a previously exported file. Invalid files are rejected and the current progress is kept. */
	importJson(text: string): { ok: boolean; error?: string } {
		if (text.length > 200_000) return { ok: false, error: 'El archivo es demasiado grande.' };
		let parsed: unknown;
		try { parsed = JSON.parse(text); } catch { return { ok: false, error: 'El archivo no es JSON válido.' }; }
		const state = parseState(parsed);
		if (!state) return { ok: false, error: 'El archivo no es un progreso válido de PALLAQUINO Academy.' };
		this.save(state);
		return { ok: true };
	}
}

export function percent(completed: string[], lessonIds: string[]): number {
	if (!lessonIds.length) return 0;
	const done = lessonIds.filter((id) => completed.includes(id)).length;
	return Math.round((done / lessonIds.length) * 100);
}

export function levelFor(pct: number): Level {
	return [...LEVELS].reverse().find((l) => pct >= l.minPercent) ?? LEVELS[0];
}
