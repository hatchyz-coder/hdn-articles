import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const articles = (await getCollection('articles', ({ data }) => !data.draft))
    .sort((a,b) => b.data.publishedAt.valueOf() - a.data.publishedAt.valueOf());

  return rss({
    title: 'HDN Articles',
    description: '医療経営、患者導線設計、自由診療、LINE活用に関する実務記事。',
    site: context.site,
    items: articles.map((article) => ({
      title: article.data.title,
      description: article.data.description,
      pubDate: article.data.publishedAt,
      link: `${context.site.pathname.replace(/\/$/, '')}${import.meta.env.BASE_URL}articles/${article.id}/`,
    })),
  });
}
