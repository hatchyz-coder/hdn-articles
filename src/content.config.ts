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
    draft: z.boolean().default(false),
    featured: z.boolean().default(false),
    sourceUrl: z.string().url().optional(),
    cta: z.enum(['consultation', 'lhub', 'self-pay']).default('consultation'),
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
    cta: z.enum(['consultation', 'lhub', 'self-pay']).default('consultation'),
    legalReview: z.enum(['required', 'completed', 'not-required']).default('required'),
    reportData: z.string().optional(),
    socialData: z.string().optional(),
    sourcesFile: z.string().optional(),
    ogImage: z.string().optional(),
  }),
});

export const collections = { articles, radarReports };
