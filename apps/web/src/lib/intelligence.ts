import type { Article, SnapshotTopic, Source } from '@newseviday/contracts';

export function displayTitle(article: Article): string {
  return article.ai?.titleZh?.trim() || article.facts.title;
}

export function displaySummary(article: Article): string {
  return article.ai?.summaryZh?.trim() || article.facts.abstract?.trim() || '来源暂未提供摘要。';
}

export function displayWhy(article: Article): string | null {
  return article.ai?.whyItMatters?.trim() || null;
}

export function isChineseDisplayReady(article: Article): boolean {
  if (article.language === 'zh-CN') {
    return Boolean(article.facts.title.trim() && article.facts.abstract?.trim());
  }
  return Boolean(article.ai?.titleZh?.trim() && article.ai?.summaryZh?.trim());
}

export function languageLabel(language: string): string {
  if (language === 'en') return '英文原文';
  if (language === 'zh-CN') return '中文';
  if (language === 'mixed') return '多语言';
  return language;
}

export function sourceTypeLabel(sourceType?: Source['sourceType'] | Article['sourceType']): string {
  if (sourceType === 'academic') return '学术论文';
  if (sourceType === 'research_institute') return '研究机构';
  if (sourceType === 'professional_media') return '专业媒体';
  if (sourceType === 'independent_author') return '作者观察';
  return '官方一手';
}

export function translationStatus(article: Article): string {
  if (article.language === 'zh-CN') return '中文原文';
  const chineseReady = Boolean(article.ai?.titleZh?.trim() && article.ai?.summaryZh?.trim());
  return chineseReady
    ? `${languageLabel(article.language)}已整理`
    : `${languageLabel(article.language)}待整理`;
}

export function formatDateTime(value: string | null): string {
  if (!value) return '时间未知';
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
}

export function topicLabels(article: Article, topics: SnapshotTopic[]): string[] {
  const labels = new Map(topics.map((topic) => [topic.id, topic.label]));
  return Object.entries(article.topicScores)
    .sort((left, right) => right[1] - left[1])
    .map(([id]) => labels.get(id) ?? id)
    .slice(0, 3);
}

export function resolveSource(article: Article, sources: Source[]): Source | undefined {
  return sources.find((source) => source.id === article.sourceId);
}
