import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsLoader, i18nLoader } from '@astrojs/starlight/loaders';
import { docsSchema, i18nSchema } from '@astrojs/starlight/schema';

/**
 * Lesson metadata is validated at build time: a lesson without objectives, duration or status, or with an unknown route or
 * difficulty, fails `astro build`. Pages that are not lessons (landing, reference, playground) omit `lesson`.
 */
export const lessonSchema = z.object({
	id: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
	path: z.enum(['introduccion', 'instalacion', 'cli', 'agentes-y-skills', 'orquestacion', 'memoria', 'plugins-y-mcp', 'proyectos-reales', 'extension']),
	difficulty: z.enum(['principiante', 'intermedio', 'avanzado']),
	duration: z.number().int().min(1).max(120),
	objectives: z.array(z.string().min(3)).min(1),
	prerequisites: z.array(z.string()).default([]),
	status: z.enum(['disponible', 'experimental', 'deprecado', 'proximamente']),
	since: z.string().regex(/^\d+\.\d+\.\d+$/),
	next: z.string().optional(),
});

export const collections = {
	docs: defineCollection({
		loader: docsLoader(),
		schema: docsSchema({ extend: z.object({ lesson: lessonSchema.optional() }) }),
	}),
	// UI string overrides per locale (src/content/i18n/<lang>.json); Starlight's built-in Spanish and English strings apply otherwise.
	i18n: defineCollection({ loader: i18nLoader(), schema: i18nSchema() }),
};
