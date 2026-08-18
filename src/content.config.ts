import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const ctaSchema = z.enum(['consultation', 'lhub', 'self-pay', 'sns']).default('consultation');

const articles = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/articles' }),
  schema: z.object({
    title: z.string(),
    socialTitle: z.string().min(4).max(80).optional(),
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
    cta: ctaSchema,
  }),
});

const articlesEn = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/articles-en' }),
  schema: z.object({
    title: z.string(),
    socialTitle: z.string().min(4).max(100).optional(),
    description: z.string().min(50).max(180),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    author: z.string().default('Tsuyoshi Hadano'),
    draft: z.boolean().default(false),
    sourceUrl: z.string().url().optional(),
    cta: ctaSchema,
  }),
});

export const collections = { articles, articlesEn };
