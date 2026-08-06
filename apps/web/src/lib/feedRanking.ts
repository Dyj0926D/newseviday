import type { Article } from '@newseviday/contracts';

interface DiversityOptions {
  firstScreenSize?: number;
  maxPerSourceInFirstScreen?: number;
  leadingSourceIds?: string[];
}

function articleScore(article: Article): number {
  return article.contentScore ?? 0;
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

  return result;
}
