export type KnowledgeTopic = {
  slug: string;
  label: string;
  shortLabel: string;
  description: string;
  keywords: string[];
};

export const knowledgeTopics: KnowledgeTopic[] = [
  {
    slug: 'private-pay',
    label: '自費診療・オンライン診療',
    shortLabel: '自費診療',
    description: '自費診療の立ち上げ、診療メニュー、オンライン診療、収益設計、継続運用を実務目線で整理します。',
    keywords: ['自費診療', '自由診療', 'オンライン診療', 'AGA', 'ED', 'ダイエット', 'GLP-1', '再生医療'],
  },
  {
    slug: 'patient-journey',
    label: '患者導線・LINE / LHub',
    shortLabel: '患者導線・LHub',
    description: 'LINE、予約、問診、決済、患者管理、再診・継続フォローまで、患者が止まらない導線を扱います。',
    keywords: ['患者導線', 'LINE', 'LHub', '予約', '問診', '決済', 'CRM', '再診', 'フォロー'],
  },
  {
    slug: 'medical-sns',
    label: '医療SNS・動画',
    shortLabel: '医療SNS・動画',
    description: 'SNS、YouTube、動画企画、患者心理、認知から予約までの接続を医療機関向けに整理します。',
    keywords: ['SNS', 'YouTube', '動画', '医療マーケティング', '集患', 'コンテンツ'],
  },
  {
    slug: 'compliance',
    label: '制度・コンプライアンス',
    shortLabel: '制度・法令',
    description: '医療広告、薬機法、景品表示法、行政通知や制度変更を、現場で何を確認するかまで落とし込みます。',
    keywords: ['医療広告', '薬機法', '景品表示法', '法令', '制度', '厚生労働省', '改善命令', 'コンプライアンス', '安全性確保法'],
  },
  {
    slug: 'clinic-management',
    label: 'クリニック経営・業務改善',
    shortLabel: 'クリニック経営',
    description: '院長・事務長の経営判断、業務改善、数値管理、AI・DX活用など、診療以外の運営課題を扱います。',
    keywords: ['クリニック経営', '業務改善', '事務長', 'AI', 'DX', '経営', '運営', '収益'],
  },
];

type TopicArticle = {
  data: {
    title: string;
    description?: string;
    category: string;
    tags: string[];
  };
};

const articleText = (article: TopicArticle) =>
  [article.data.title, article.data.description ?? '', article.data.category, ...article.data.tags].join(' ').toLowerCase();

export const matchesTopic = (article: TopicArticle, topic: KnowledgeTopic) => {
  const haystack = articleText(article);
  return topic.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
};

export const topicsForArticle = (article: TopicArticle) => knowledgeTopics.filter((topic) => matchesTopic(article, topic));

export const topicHref = (slug: string, base = '/') => `${base}topics/${slug}/`;
