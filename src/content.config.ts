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

const radarReports = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/radar-reports' }),
  schema: z.object({
    title: z.string(),
    description: z.string().min(60).max(160),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    product: z.enum(['market-radar', 'career-radar', 'relationship-engine']),
    contentType: z.enum(['report', 'insight', 'snapshot', 'guide']),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    author: z.string().default('HDN Market Intelligence Team'),
    draft: z.boolean().default(true),
    language: z.enum(['ja', 'en']).default('ja'),
    canonical: z.string().url().optional(),
    sourcePeriod: z.string().optional(),
    dataAsOf: z.coerce.date().optional(),
    cta: ctaSchema,
    legalReview: z.enum(['required', 'completed', 'not-required']).default('required'),
    reportData: z.string().optional(),
    socialData: z.string().optional(),
    sourcesFile: z.string().optional(),
    ogImage: z.string().optional(),
  }),
});

export const collections = { articles, articlesEn, radarReports };
