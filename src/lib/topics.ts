export type KnowledgeTopic = {
  slug: string;
  label: string;
  shortLabel: string;
  description: string;
  keywords: string[];
  requiredKeywords?: string[];
  excludedKeywords?: string[];
  en: {
    label: string;
    shortLabel: string;
    description: string;
    keywords: string[];
    requiredKeywords?: string[];
    excludedKeywords?: string[];
  };
};

const medicalContextJa = ['患者', 'クリニック', '医療', '診療', '医院', '医師', '歯科', '院長', '事務長'];
const medicalContextEn = ['patient', 'clinic', 'healthcare', 'medical', 'doctor', 'dental'];

export const knowledgeTopics: KnowledgeTopic[] = [
  {
    slug: 'private-pay',
    label: '自費診療・オンライン診療',
    shortLabel: '自費診療',
    description: '自費診療の立ち上げ、診療メニュー、オンライン診療、収益設計、継続運用を実務目線で整理します。',
    keywords: ['自費診療', '自由診療', 'オンライン診療', 'AGA', 'ED', 'ダイエット', 'GLP-1', '再生医療'],
    en: {
      label: 'Private-pay Care & Telemedicine',
      shortLabel: 'Private-pay Care',
      description: 'Practical guidance on launching private-pay services, telemedicine, service design, revenue models, and ongoing operations.',
      keywords: ['private-pay', 'self-pay', 'telemedicine', 'online care', 'AGA', 'ED', 'weight management', 'GLP-1', 'regenerative medicine'],
    },
  },
  {
    slug: 'patient-journey',
    label: 'クリニックの患者導線・LINE',
    shortLabel: '患者導線・LINE',
    description: '医療機関のLINE、予約、問診、決済、患者管理、再診・継続フォローを扱います。その他業種のLHub活用はLHub専用ページで分けて案内します。',
    keywords: ['患者導線', 'LINE', 'LHub', '予約', '問診', '決済', 'CRM', '再診', 'フォロー'],
    requiredKeywords: medicalContextJa,
    en: {
      label: 'Clinic Patient Journey & LINE',
      shortLabel: 'Patient Journey',
      description: 'How healthcare organizations connect LINE, booking, questionnaires, payments, CRM, follow-up, and repeat visits.',
      keywords: ['patient journey', 'LINE', 'LHub', 'booking', 'appointment', 'questionnaire', 'payment', 'CRM', 'follow-up', 'repeat visit'],
      requiredKeywords: medicalContextEn,
    },
  },
  {
    slug: 'medical-sns',
    label: '医療SNS・動画',
    shortLabel: '医療SNS・動画',
    description: 'SNS、YouTube、動画企画、患者心理、認知から予約までの接続を医療機関向けに整理します。',
    keywords: ['SNS', 'YouTube', '動画', '医療マーケティング', '集患', 'コンテンツ'],
    requiredKeywords: medicalContextJa,
    en: {
      label: 'Healthcare Social Media & Video',
      shortLabel: 'Social & Video',
      description: 'Practical content strategy for healthcare social media, YouTube, patient psychology, and the path from awareness to booking.',
      keywords: ['social media', 'SNS', 'YouTube', 'video', 'healthcare marketing', 'content', 'patient acquisition'],
      requiredKeywords: medicalContextEn,
    },
  },
  {
    slug: 'compliance',
    label: '制度・コンプライアンス',
    shortLabel: '制度・法令',
    description: '医療広告、薬機法、景品表示法、行政通知や制度変更を、現場で何を確認するかまで落とし込みます。',
    keywords: ['医療広告', '薬機法', '景品表示法', '法令', '制度', '厚生労働省', '改善命令', 'コンプライアンス', '安全性確保法'],
    en: {
      label: 'Regulation & Compliance',
      shortLabel: 'Compliance',
      description: 'Operational implications of healthcare advertising rules, regulatory updates, government notices, and compliance requirements.',
      keywords: ['medical advertising', 'healthcare advertising', 'regulation', 'compliance', 'law', 'MHLW', 'Ministry of Health', 'improvement order', 'safety act'],
    },
  },
  {
    slug: 'clinic-management',
    label: 'クリニック経営・業務改善',
    shortLabel: 'クリニック経営',
    description: '院長・事務長の経営判断、業務改善、数値管理、AI・DX活用など、診療以外の運営課題を扱います。',
    keywords: ['クリニック経営', '業務改善', '事務長', 'AI', 'DX', '経営', '運営', '収益'],
    requiredKeywords: medicalContextJa,
    en: {
      label: 'Clinic Management & Operations',
      shortLabel: 'Clinic Management',
      description: 'Decision-making, workflow improvement, management metrics, AI, DX, and other operational issues outside clinical care.',
      keywords: ['clinic management', 'operations', 'workflow', 'business improvement', 'AI', 'DX', 'management', 'revenue'],
      requiredKeywords: medicalContextEn,
    },
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

const includesAny = (haystack: string, values: string[]) => values.some((value) => haystack.includes(value.toLowerCase()));

export const matchesTopic = (article: TopicArticle, topic: KnowledgeTopic, lang: 'ja' | 'en' = 'ja') => {
  const haystack = articleText(article);
  const config = lang === 'en' ? topic.en : topic;
  if (!includesAny(haystack, config.keywords)) return false;
  if (config.requiredKeywords?.length && !includesAny(haystack, config.requiredKeywords)) return false;
  if (config.excludedKeywords?.length && includesAny(haystack, config.excludedKeywords)) return false;
  return true;
};

export const topicsForArticle = (article: TopicArticle, lang: 'ja' | 'en' = 'ja') =>
  knowledgeTopics.filter((topic) => matchesTopic(article, topic, lang));

export const topicHref = (slug: string, base = '/', lang: 'ja' | 'en' = 'ja') =>
  `${base}${lang === 'en' ? 'en/' : ''}topics/${slug}/`;
