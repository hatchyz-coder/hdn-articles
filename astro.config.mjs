import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const base = process.env.BASE_PATH || '/';
const site = process.env.PUBLIC_SITE_URL || 'https://article.hdnjapan.com';

export default defineConfig({
  site,
  base,
  output: 'static',
  integrations: [sitemap()],
});
