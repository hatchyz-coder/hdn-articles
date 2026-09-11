type ArticleData = {
  title: string;
  description?: string;
  category: string;
  tags: string[];
  audiences?: Array<'clinic' | 'lhub' | 'general'>;
  section?:
    | 'clinic-private-pay'
    | 'clinic-journey'
    | 'clinic-marketing'
    | 'clinic-compliance'
    | 'clinic-management'
    | 'lhub-usecase'
    | 'world-frictions'
    | 'research';
  industry?: 'medical' | 'dental' | 'real-estate' | 'retail' | 'creator' | 'fortune' | 'other';
  series?: string;
};

type ArticleLike = { data: ArticleData };

const text = (article: ArticleLike) =>
  [article.data.title, article.data.description ?? '', article.data.category, ...article.data.tags]
    .join(' ')
    .toLowerCase();

const includesAny = (value: string, terms: string[]) => terms.some((term) => value.includes(term.toLowerCase()));

const clinicTerms = [
  'クリニック',
  '医院',
  '病院',
  '医療',
  '患者',
  '診療',
  '医師',
  '歯科',
  '薬機法',
  '医療広告',
  '厚生労働省',
  'pmda',
  '自費',
  '自由診療',
  'オンライン診療',
];

const researchTerms = [
  '厚生労働省',
  'pmda',
  '消費者庁',
  '制度',
  '法令',
  'ガイドライン',
  '通知',
  '検討会',
  '行政',
  '規制',
  'コンプライアンス',
];

export const isWorldFrictionsArticle = (article: ArticleLike) => {
  if (article.data.section) return article.data.section === 'world-frictions';
  if (article.data.series) return article.data.series.toLowerCase() === 'world-frictions';
  return includesAny(text(article), ['世界の違和感', 'frictions in the world']);
};

export const isLHubArticle = (article: ArticleLike) => {
  if (article.data.audiences) return article.data.audiences.includes('lhub');
  if (article.data.section) return article.data.section === 'lhub-usecase';
  return text(article).includes('lhub');
};

export const isClinicArticle = (article: ArticleLike) => {
  if (article.data.audiences) return article.data.audiences.includes('clinic');
  if (article.data.section) return article.data.section.startsWith('clinic-');
  return includesAny(text(article), clinicTerms);
};

export const isResearchArticle = (article: ArticleLike) => {
  if (article.data.section) return article.data.section === 'research' || article.data.section === 'clinic-compliance';
  return includesAny(text(article), researchTerms);
};

export const isGeneralArticle = (article: ArticleLike) =>
  article.data.audiences ? article.data.audiences.includes('general') : isWorldFrictionsArticle(article);

export const articleLane = (article: ArticleLike) => {
  if (isWorldFrictionsArticle(article)) return 'world-frictions';
  if (isLHubArticle(article) && !isClinicArticle(article)) return 'lhub';
  if (isClinicArticle(article)) return 'clinic';
  if (isResearchArticle(article)) return 'research';
  return 'general';
};
