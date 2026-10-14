#!/usr/bin/env node
/**
 * Automated accessibility check of the built Spanish pages with axe-core (WCAG 2.0/2.1/2.2 A and AA rules) in jsdom.
 *
 * jsdom has no layout engine, so rules that need rendering (color contrast, target size) cannot run here; contrast is reviewed in a
 * real browser (docs/learning/UX_TEST_PROTOCOL.md). Interactive islands are checked in their server-rendered state; their hydrated
 * markup is covered by the component tests. Exit code 1 lists every violation.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { JSDOM, VirtualConsole } from 'jsdom';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DIST = join(ROOT, 'dist');
if (!existsSync(DIST)) { console.error('dist/ not found: run `npm run build` first'); process.exit(1); }
const axeSource = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8');

const walk = (dir) => readdirSync(dir).flatMap((n) => { const p = join(dir, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
// The English fallback pages repeat the Spanish content, so checking the Spanish pages covers every template and component.
const pages = walk(DIST).filter((p) => p.endsWith('.html') && !relative(DIST, p).replaceAll('\\', '/').startsWith('en/') || p.endsWith(join('en', 'index.html')));

const RUN_OPTIONS = {
	runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
	rules: { 'color-contrast': { enabled: false }, 'target-size': { enabled: false } },
	resultTypes: ['violations'],
};

// Starlight renders the table of contents twice (mobile and desktop) and hides one with CSS. jsdom applies no CSS, so both look
// visible and axe reports a duplicate landmark that a browser never exposes. The mobile copy is excluded here only.
const CONTEXT = { include: [['html']], exclude: [['mobile-starlight-toc']] };

let failures = 0;
for (const page of pages) {
	const virtualConsole = new VirtualConsole(); // page scripts are not executed; keep jsdom quiet about CSS it cannot parse
	const dom = new JSDOM(readFileSync(page, 'utf8'), { runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole });
	dom.window.eval(axeSource);
	const result = await dom.window.axe.run(CONTEXT, RUN_OPTIONS);
	const where = relative(DIST, page).replaceAll('\\', '/');
	for (const v of result.violations) {
		failures += 1;
		console.error(`${where}: [${v.impact}] ${v.id} — ${v.help}`);
		for (const node of v.nodes.slice(0, 3)) console.error(`    ${node.target.join(' ')}`);
	}
	dom.window.close();
}

if (failures) { console.error(`\n${failures} violation(s) in ${pages.length} pages`); process.exit(1); }
console.log(`a11y ok: ${pages.length} pages, no axe-core violations (WCAG A/AA + best practices; contrast checked in the browser)`);
