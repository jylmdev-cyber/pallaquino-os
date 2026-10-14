// @ts-check
import starlight from '@astrojs/starlight';
import vue from '@astrojs/vue';
import { defineConfig } from 'astro/config';

// Static hosting: ACADEMY_SITE is the public origin and ACADEMY_BASE the path prefix (for example "/pallaquino-os/" on GitHub Pages).
const site = process.env.ACADEMY_SITE ?? 'https://jylmdev-cyber.github.io';
const base = process.env.ACADEMY_BASE ?? '/pallaquino-os/';

export default defineConfig({
	site,
	base,
	trailingSlash: 'always',
	integrations: [
		starlight({
			title: 'PALLAQUINO Academy',
			description:
				'Aprende a instalar, usar y extender PALLAQUINO Autonomous Engineering OS con tutoriales interactivos verificados contra el código real.',
			defaultLocale: 'root',
			locales: {
				root: { label: 'Español', lang: 'es' },
				en: { label: 'English', lang: 'en' },
			},
			logo: { src: './src/assets/logo.svg', alt: 'PALLAQUINO' },
			favicon: '/favicon.svg',
			social: [{ icon: 'github', label: 'Repositorio en GitHub', href: 'https://github.com/jylmdev-cyber/pallaquino-os' }],
			editLink: { baseUrl: 'https://github.com/jylmdev-cyber/pallaquino-os/edit/main/academy/' },
			customCss: ['./src/styles/academy.css'],
			// Long commands wrap instead of scrolling sideways: readable on phones and reachable without a pointer.
			expressiveCode: { defaultProps: { wrap: true } },
			components: {
				PageTitle: './src/components/overrides/PageTitle.astro',
				MarkdownContent: './src/components/overrides/MarkdownContent.astro',
			},
			sidebar: [
				{ label: 'Comienza aquí', items: [{ label: 'Inicio', link: '/' }, { label: 'Rutas de aprendizaje', link: '/rutas/' }, { label: 'Tu progreso', link: '/progreso/' }] },
				{ label: '1 · Introducción', items: [{ autogenerate: { directory: 'introduccion' } }] },
				{ label: '2 · Instalación y configuración', items: [{ autogenerate: { directory: 'instalacion' } }] },
				{ label: '3 · Dominio de la CLI', items: [{ autogenerate: { directory: 'cli' } }] },
				{ label: '4 · Agentes y skills', collapsed: true, items: [{ autogenerate: { directory: 'agentes-y-skills' } }] },
				{ label: '5 · Pipelines y orquestación', collapsed: true, items: [{ autogenerate: { directory: 'orquestacion' } }] },
				{ label: '6 · Memoria y continuidad', collapsed: true, items: [{ autogenerate: { directory: 'memoria' } }] },
				{ label: '7 · Plugins y MCP', collapsed: true, items: [{ autogenerate: { directory: 'plugins-y-mcp' } }] },
				{ label: '8 · Proyectos reales', collapsed: true, items: [{ autogenerate: { directory: 'proyectos-reales' } }] },
				{ label: '9 · Extensión del framework', collapsed: true, items: [{ autogenerate: { directory: 'extension' } }] },
				{ label: 'Práctica interactiva', items: [{ autogenerate: { directory: 'practica' } }] },
				{ label: 'Referencia para desarrolladores', collapsed: true, items: [{ autogenerate: { directory: 'referencia' } }] },
				{ label: 'Videos (guiones)', collapsed: true, items: [{ autogenerate: { directory: 'videos' } }] },
			],
		}),
		vue(),
	],
});
