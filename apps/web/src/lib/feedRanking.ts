import type { Article } from '@newseviday/contracts';

import { isChineseDisplayReady } from './intelligence';

interface DiversityOptions {
  firstScreenSize?: number;
  maxPerSourceInFirstScreen?: number;
  leadingSourceIds?: string[];
}

function articleScore(article: Article): number {
  return article.contentScore ?? 0;
}

function articleTimestamp(article: Article): number {
  return new Date(article.publishedAt ?? article.collectedAt).getTime();
}

export function isWithinPublishedWindow(
  article: Article,
  anchor: string,
  windowDays: number,
): boolean {
  if (!article.publishedAt) return true;
  const age = new Date(anchor).getTime() - new Date(article.publishedAt).getTime();
  return age >= 0 && age <= windowDays * 24 * 60 * 60 * 1000;
}

export function sortLatestArticles(articles: Article[]): Article[] {
  return [...articles].sort(
    (left, right) =>
      articleTimestamp(right) - articleTimestamp(left) || articleScore(right) - articleScore(left),
  );
}

export function summarizeVisibleFreshness(
  articles: Article[],
  anchor: string,
  windowDays = 30,
): { visibleCount: number; recent24HourCount: number; latestPublishedAt: string | null } {
  const visible = sortLatestArticles(
    articles.filter(
      (article) =>
        isChineseDisplayReady(article) && isWithinPublishedWindow(article, anchor, windowDays),
    ),
  );
  return {
    visibleCount: visible.length,
    recent24HourCount: visible.filter((article) =>
      isWithinPublishedWindow(article, anchor, 1),
    ).length,
    latestPublishedAt: visible[0]?.publishedAt ?? visible[0]?.collectedAt ?? null,
  };
}

function tripleCount(sourceIds: string[]): number {
  return sourceIds.reduce(
    (count, sourceId, index) =>
      index >= 2 && sourceId === sourceIds[index - 1] && sourceId === sourceIds[index - 2]
        ? count + 1
        : count,
    0,
  );
}

function repairTrailingTriples(
  articles: Article[],
  leadingSourceIds: string[],
  firstScreenSize: number,
): Article[] {
  const repaired = [...articles];
  const firstMovableIndex = Math.max(0, firstScreenSize - leadingSourceIds.length);
  const sources = (): string[] => [
    ...leadingSourceIds,
    ...repaired.map((article) => article.sourceId),
  ];

  for (let attempt = 0; attempt < repaired.length; attempt += 1) {
    const currentTripleCount = tripleCount(sources());
    if (currentTripleCount === 0) break;
    let improved = false;

    for (let right = repaired.length - 1; right >= firstMovableIndex && !improved; right -= 1) {
      for (let left = right - 1; left >= firstMovableIndex; left -= 1) {
        if (repaired[left]?.sourceId === repaired[right]?.sourceId) continue;
        [repaired[left], repaired[right]] = [repaired[right] as Article, repaired[left] as Article];
        if (tripleCount(sources()) < currentTripleCount) {
          improved = true;
          break;
        }
        [repaired[left], repaired[right]] = [repaired[right] as Article, repaired[left] as Article];
      }
    }

    if (!improved) break;
  }
  return repaired;
}

export function selectKeySignal(articles: Article[]): Article | null {
  return (
    articles
      .filter((article) => article.keySignal?.eligible)
      .sort(
        (left, right) =>
          (right.keySignal?.score ?? 0) - (left.keySignal?.score ?? 0) ||
          articleScore(right) - articleScore(left),
      )[0] ?? null
  );
}

export function diversifyBySource(articles: Article[], options: DiversityOptions = {}): Article[] {
  const firstScreenSize = options.firstScreenSize ?? 8;
  const maxPerSource = options.maxPerSourceInFirstScreen ?? 3;
  const leadingSourceIds = options.leadingSourceIds ?? [];
  const remaining = [...articles];
  const result: Article[] = [];
  const firstScreenCounts = new Map<string, number>();
  const recentSources = leadingSourceIds.slice(-2);

  for (const sourceId of leadingSourceIds.slice(0, firstScreenSize)) {
    firstScreenCounts.set(sourceId, (firstScreenCounts.get(sourceId) ?? 0) + 1);
  }

  while (remaining.length > 0) {
    const overallPosition = leadingSourceIds.length + result.length;
    const inFirstScreen = overallPosition < firstScreenSize;
    const createsTriple = (article: Article): boolean =>
      recentSources.length >= 2 && recentSources.every((sourceId) => sourceId === article.sourceId);
    const withinSourceLimit = (article: Article): boolean =>
      !inFirstScreen || (firstScreenCounts.get(article.sourceId) ?? 0) < maxPerSource;

    let nextIndex = remaining.findIndex(
      (article) => !createsTriple(article) && withinSourceLimit(article),
    );
    if (nextIndex < 0) nextIndex = remaining.findIndex((article) => !createsTriple(article));
    if (nextIndex < 0) nextIndex = 0;

    const [next] = remaining.splice(nextIndex, 1);
    if (!next) break;
    result.push(next);
    recentSources.push(next.sourceId);
    if (recentSources.length > 2) recentSources.shift();
    if (inFirstScreen) {
      firstScreenCounts.set(next.sourceId, (firstScreenCounts.get(next.sourceId) ?? 0) + 1);
    }
  }

  return repairTrailingTriples(result, leadingSourceIds, firstScreenSize);
}
