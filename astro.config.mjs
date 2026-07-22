import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const normalizeBase = (basePath) => {
  const withLeadingSlash = basePath.startsWith('/') ? basePath : `/${basePath}`;
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`;
};

const base = normalizeBase(process.env.BASE_PATH || '/hdn-articles/');
const site = process.env.PUBLIC_SITE_URL || 'https://hatchyz-coder.github.io';

export default defineConfig({
  site,
  base,
  output: 'static',
  integrations: [sitemap()],
});
