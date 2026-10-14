#!/usr/bin/env node
/**
 * Internal link check of the built site (`dist/`, run after `astro build`). Every `href`/`src` that stays on the site must resolve
 * to a built file, and a `#fragment` must match an `id` in the target page. External links are not fetched (no network in CI).
 * The base path comes from ACADEMY_BASE, as in astro.config.mjs.
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DIST = join(ROOT, 'dist');
const BASE = (process.env.ACADEMY_BASE ?? '/pallaquino-os/').replace(/\/?$/, '/');
const ORIGIN = 'https://academy.invalid';

if (!existsSync(DIST)) { console.error('dist/ not found: run `npm run build` first'); process.exit(1); }

const walk = (dir) => readdirSync(dir).flatMap((n) => { const p = join(dir, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
const pages = walk(DIST).filter((p) => p.endsWith('.html'));
const idCache = new Map();
const idsOf = (file) => {
	if (!idCache.has(file)) idCache.set(file, new Set([...readFileSync(file, 'utf8').matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])));
	return idCache.get(file);
};
const urlOf = (file) => BASE + relative(DIST, file).replaceAll('\\', '/').replace(/index\.html$/, '');

/** Built file for a site path, or null. */
function target(pathname) {
	if (!pathname.startsWith(BASE)) return null;
	const rel = decodeURIComponent(pathname.slice(BASE.length));
	for (const candidate of [rel, join(rel, 'index.html'), `${rel}.html`]) {
		const file = join(DIST, candidate);
		if (existsSync(file) && statSync(file).isFile()) return file;
	}
	return null;
}

const problems = []; let checked = 0;
for (const page of pages) {
	const html = readFileSync(page, 'utf8');
	const pageUrl = new URL(urlOf(page), ORIGIN);
	for (const m of html.matchAll(/\s(?:href|src)="([^"]+)"/g)) {
		const raw = m[1].replaceAll('&amp;', '&');
		if (/^(?:[a-z]+:)?\/\//i.test(raw) && !raw.startsWith(ORIGIN) || /^(mailto|tel|data|javascript):/i.test(raw)) continue;
		const url = new URL(raw, pageUrl);
		if (url.origin !== ORIGIN) continue;
		checked += 1;
		const file = url.pathname === pageUrl.pathname ? page : target(url.pathname);
		const where = relative(DIST, page).replaceAll('\\', '/');
		if (!file) { problems.push(`${where}: broken link ${raw}`); continue; }
		const fragment = decodeURIComponent(url.hash.slice(1));
		if (fragment && file.endsWith('.html') && !idsOf(file).has(fragment)) problems.push(`${where}: missing anchor ${raw}`);
	}
}

if (problems.length) { console.error([...new Set(problems)].join('\n')); console.error(`\n${problems.length} problem(s)`); process.exit(1); }
console.log(`links ok: ${checked} internal links in ${pages.length} pages`);
