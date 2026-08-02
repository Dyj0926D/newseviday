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

export function languageLabel(language: string): string {
  if (language === 'en') return '英文原文';
  if (language === 'zh-CN') return '中文';
  if (language === 'mixed') return '多语言';
  return language;
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
