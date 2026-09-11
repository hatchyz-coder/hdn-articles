const optionalUrl = (value: string | undefined) => {
  const normalized = value?.trim();
  return normalized ? normalized : null;
};

export const distributionChannels = {
  canonicalBase: 'https://article.hdnjapan.com/',
  linkedInProfile: 'https://jp.linkedin.com/in/tsuyoshi-hadano',
  linkedInNewsletter: optionalUrl(import.meta.env.PUBLIC_LINKEDIN_NEWSLETTER_URL),
  note: optionalUrl(import.meta.env.PUBLIC_NOTE_URL),
} as const;

export const activeLinkedInDestination =
  distributionChannels.linkedInNewsletter ?? distributionChannels.linkedInProfile;

export const activeLinkedInChannel = distributionChannels.linkedInNewsletter ? 'newsletter' : 'linkedin';
