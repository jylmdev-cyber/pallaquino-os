#!/usr/bin/env node
/**
 * Docs-as-code checks for the academy content (no dependencies):
 *
 * - every lesson id is unique, and every `next` / lesson-id prerequisite points to an existing lesson;
 * - `<LessonComplete lessonId>` matches the page's own lesson id; quiz ids are unique;
 * - every `pallaquino …` / `python -m pallaquino_cli …` command written in code (fenced blocks and inline code) uses a real
 *   subcommand, a valid action and only options that subcommand accepts, according to the generated cli.json;
 * - agent and skill ids written in inline code exist in the registry;
 * - `<Transcript id>` and `<InteractiveTerminal challenge>` refer to recorded transcripts and existing challenges.
 *
 * Exit code 1 with one line per problem, 0 when everything is consistent.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DOCS = join(ROOT, 'src', 'content', 'docs');
const read = (p) => readFileSync(join(ROOT, p), 'utf8');
const cli = JSON.parse(read('src/data/generated/cli.json'));
const agents = JSON.parse(read('src/data/generated/agents.json'));
const skills = JSON.parse(read('src/data/generated/skills.json'));
const transcripts = JSON.parse(read('src/data/transcripts.json'));
const challengeIds = [...read('src/lib/challenges.ts').matchAll(/^\t\tid: '([^']+)'/gm)].map((m) => m[1]);
const transcriptIds = new Set([...transcripts.commands, ...transcripts.project].map((t) => t.id));
const knownIds = new Set([...agents.map((a) => a.id), ...skills.map((s) => s.id)]);
const commands = new Map(cli.commands.map((c) => [c.name, c]));
const ROLE_SUFFIX = /^[a-z]+(?:_[a-z]+)*_(engineer|architect|reviewer|analyzer|manager|expert|designer|analyst|agent|maintainer|explorer)$/;

const problems = [];
const report = (file, message) => problems.push(`${relative(ROOT, file).replaceAll('\\', '/')}: ${message}`);

function walk(dir) {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		return statSync(path).isDirectory() ? walk(path) : /\.mdx?$/.test(name) ? [path] : [];
	});
}

/** Minimal reader for the `lesson:` frontmatter block (scalars and `- item` lists two spaces deep). */
function lessonOf(text) {
	const fm = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
	if (!fm) return null;
	const block = fm[1].match(/^lesson:\r?\n((?: {2}.*\r?\n?)+)/m);
	if (!block) return null;
	const lesson = {}; let list = null;
	for (const line of block[1].split(/\r?\n/)) {
		const item = line.match(/^ {4}- (.*)$/);
		const field = line.match(/^ {2}([a-z_]+):\s*(.*)$/);
		if (item && list) lesson[list].push(item[1].trim());
		else if (field) { if (field[2] === '') { list = field[1]; lesson[list] = []; } else { list = null; lesson[field[1]] = field[2].trim(); } }
	}
	return lesson;
}

/** Shell-like tokenizer for single- and double-quoted arguments. */
function tokenize(line) {
	const tokens = []; let current = ''; let quote = null; let has = false;
	for (const ch of line) {
		if (quote) { if (ch === quote) quote = null; else current += ch; }
		else if (ch === '"' || ch === "'") { quote = ch; has = true; }
		else if (/\s/.test(ch)) { if (has || current) tokens.push(current); current = ''; has = false; }
		else current += ch;
	}
	if (has || current) tokens.push(current);
	return tokens;
}

const SEMVER = /^\d+\.\d+\.\d+$/;
let checkedCommands = 0;
function checkCommand(file, text) {
	const tokens = tokenize(text.trim());
	if (!tokens.length || tokens[0].startsWith('<') || SEMVER.test(tokens[0])) return;
	checkedCommands += 1;
	if (tokens.length === 1 && ['--version', '--help', '-h'].includes(tokens[0])) return;
	const command = commands.get(tokens[0]);
	if (!command) return report(file, `unknown command "${tokens[0]}" in: ${text.trim()}`);
	const flags = new Set(command.arguments.flatMap((a) => a.flags).concat(['--help', '-h']));
	const action = command.arguments.find((a) => a.positional && a.choices);
	const rest = tokens.slice(1);
	if (action && rest[0] && !rest[0].startsWith('-') && !rest[0].startsWith('<') && !action.choices.includes(rest[0]))
		report(file, `"${rest[0]}" is not a ${command.name} action (${action.choices.join(', ')}) in: ${text.trim()}`);
	for (const token of rest) {
		if (!token.startsWith('--')) continue;
		const flag = token.split('=')[0];
		if (!flags.has(flag)) report(file, `option ${flag} does not exist for "${command.name}" in: ${text.trim()}`);
		if (command.arguments.find((a) => a.flags.includes(flag))?.nargs === '...') break; // the rest belongs to the wrapped command
	}
}

/** Code snippets: lines of fenced blocks plus inline code spans outside fences. */
function codeSnippets(body) {
	const snippets = [];
	const withoutFences = body.replace(/^([ \t]*)(```|~~~)[^\n]*\n([\s\S]*?)^\1?[ \t]*\2[ \t]*$/gm, (_, _i, _f, code) => {
		snippets.push(...code.split('\n')); return '';
	});
	for (const m of withoutFences.matchAll(/`([^`\n]+)`/g)) snippets.push(m[1]);
	return snippets;
}

const COMMAND = /(?:^|[\s(:])(?:python3?|py)\s+-m\s+pallaquino_cli\b([^#|&;]*)|(?:^|[\s(:])pallaquino(?=\s)([^#|&;]*)/g;
const lessons = new Map();
const quizIds = new Map();
const files = walk(DOCS);

for (const file of files) {
	const text = readFileSync(file, 'utf8');
	const body = text.replace(/^---\r?\n[\s\S]*?\r?\n---/, '');
	const lesson = lessonOf(text);
	if (lesson) {
		if (lessons.has(lesson.id)) report(file, `duplicate lesson id "${lesson.id}" (also in ${relative(ROOT, lessons.get(lesson.id).file)})`);
		lessons.set(lesson.id, { ...lesson, file });
	}
	for (const m of body.matchAll(/<LessonComplete[^>]*lessonId="([^"]+)"/g))
		if (!lesson || m[1] !== lesson.id) report(file, `LessonComplete lessonId "${m[1]}" does not match the page lesson id "${lesson?.id ?? '(none)'}"`);
	for (const m of body.matchAll(/<QuizPlayer[^>]*\bid="([^"]+)"/g)) {
		if (quizIds.has(m[1])) report(file, `duplicate quiz id "${m[1]}"`);
		quizIds.set(m[1], file);
	}
	for (const m of body.matchAll(/<Transcript\s+id="([^"]+)"/g)) if (!transcriptIds.has(m[1])) report(file, `unknown transcript "${m[1]}"`);
	for (const m of body.matchAll(/<InteractiveTerminal[^>]*challenge="([^"]+)"/g)) if (!challengeIds.includes(m[1])) report(file, `unknown challenge "${m[1]}"`);
	for (const snippet of codeSnippets(body)) {
		for (const m of snippet.matchAll(COMMAND)) checkCommand(file, m[1] ?? m[2] ?? '');
		const id = snippet.trim();
		if (ROLE_SUFFIX.test(id) && !knownIds.has(id)) report(file, `"${id}" is not a registered agent or skill`);
	}
}

for (const [id, lesson] of lessons) {
	if (lesson.next && !lessons.has(lesson.next)) report(lesson.file, `next lesson "${lesson.next}" does not exist`);
	for (const p of lesson.prerequisites ?? []) if (/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(p) && !lessons.has(p)) report(lesson.file, `prerequisite "${p}" looks like a lesson id but no lesson "${p}" exists (lesson ${id})`);
}

if (problems.length) {
	console.error(problems.join('\n'));
	console.error(`\n${problems.length} problem(s) in ${files.length} page(s).`);
	process.exit(1);
}
console.log(`content ok: ${files.length} pages, ${lessons.size} lessons, ${quizIds.size} quizzes, ${checkedCommands} CLI commands; agent ids, transcripts and links between lessons verified`);
