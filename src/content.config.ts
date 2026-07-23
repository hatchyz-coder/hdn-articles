import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const articles = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/articles' }),
  schema: z.object({
    title: z.string(),
    description: z.string().min(60).max(160),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    author: z.string().default('羽田野 剛士'),
    editorialSourceAuthor: z.string().optional(),
    draft: z.boolean().default(false),
    featured: z.boolean().default(false),
    sourceUrl: z.string().url().optional(),
    cta: z.enum(['consultation', 'lhub', 'self-pay']).default('consultation'),
  }),
});

export const collections = { articles };
