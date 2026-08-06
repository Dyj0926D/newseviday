import { assertContentSnapshot, type ContentSnapshot } from '@newseviday/contracts';
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

type ContentState = 'idle' | 'loading' | 'ready' | 'error';

export interface ArchiveArticleEntry {
  id: string;
  title: string;
  originalTitle: string;
  sourceId: string;
  publishedAt: string | null;
  snapshotPath: string;
}

interface ArchiveManifest {
  schemaVersion: '1.0.0';
  updatedAt: string;
  articles: ArchiveArticleEntry[];
}

export const useContentStore = defineStore('content', () => {
  const state = ref<ContentState>('idle');
  const snapshot = ref<ContentSnapshot | null>(null);
  const archiveManifest = ref<ArchiveManifest | null>(null);
  let pendingRequest: Promise<void> | null = null;
  let pendingArchiveRequest: Promise<ArchiveManifest | null> | null = null;

  const isDemo = computed(() => snapshot.value?.snapshotKind === 'demo');

  function refresh(force = false): Promise<void> {
    if (!force && state.value === 'ready') return Promise.resolve();
    if (pendingRequest) return pendingRequest;

    pendingRequest = (async () => {
      state.value = 'loading';
      const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');

      try {
        const response = await fetch(`${basePath}/data/current.json`, {
          headers: { Accept: 'application/json' },
          cache: 'no-cache',
        });
        if (!response.ok) throw new Error(`snapshot request failed: ${response.status}`);
        const payload: unknown = await response.json();
        assertContentSnapshot(payload);
        snapshot.value = payload;
        state.value = 'ready';
      } catch {
        state.value = 'error';
      } finally {
        pendingRequest = null;
      }
    })();

    return pendingRequest;
  }

  function dataUrl(path: string): string {
    const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');
    return `${basePath}/data/${path.replace(/^\//, '')}`;
  }

  function loadArchiveManifest(): Promise<ArchiveManifest | null> {
    if (archiveManifest.value) return Promise.resolve(archiveManifest.value);
    if (pendingArchiveRequest) return pendingArchiveRequest;
    pendingArchiveRequest = (async () => {
      try {
        const response = await fetch(dataUrl('archive/manifest.json'), {
          headers: { Accept: 'application/json' },
          cache: 'no-cache',
        });
        if (!response.ok) return null;
        const value = (await response.json()) as Partial<ArchiveManifest>;
        if (value.schemaVersion !== '1.0.0' || !Array.isArray(value.articles)) return null;
        const articles = value.articles.filter(
          (item): item is ArchiveArticleEntry =>
            Boolean(
              item &&
                typeof item.id === 'string' &&
                typeof item.title === 'string' &&
                typeof item.originalTitle === 'string' &&
                typeof item.sourceId === 'string' &&
                typeof item.snapshotPath === 'string' &&
                /^versions\/[a-zA-Z0-9._-]+\.json$/.test(item.snapshotPath),
            ),
        );
        archiveManifest.value = {
          schemaVersion: '1.0.0',
          updatedAt: typeof value.updatedAt === 'string' ? value.updatedAt : '',
          articles,
        };
        return archiveManifest.value;
      } catch {
        return null;
      } finally {
        pendingArchiveRequest = null;
      }
    })();
    return pendingArchiveRequest;
  }

  async function loadArchivedSnapshotForArticle(articleId: string): Promise<ContentSnapshot | null> {
    const manifest = await loadArchiveManifest();
    const entry = manifest?.articles.find((item) => item.id === articleId);
    if (!entry) return null;
    try {
      const response = await fetch(dataUrl(entry.snapshotPath), {
        headers: { Accept: 'application/json' },
        cache: 'force-cache',
      });
      if (!response.ok) return null;
      const payload: unknown = await response.json();
      assertContentSnapshot(payload);
      return payload.articles.some((item) => item.id === articleId) ? payload : null;
    } catch {
      return null;
    }
  }

  async function searchArchive(query: string, limit = 8): Promise<ArchiveArticleEntry[]> {
    const normalized = query.trim().toLocaleLowerCase();
    if (normalized.length < 2) return [];
    const manifest = await loadArchiveManifest();
    const currentIds = new Set(snapshot.value?.articles.map((article) => article.id) ?? []);
    return (
      manifest?.articles.filter(
        (item) =>
          !currentIds.has(item.id) &&
          `${item.title} ${item.originalTitle} ${item.sourceId}`
            .toLocaleLowerCase()
            .includes(normalized),
      ) ?? []
    ).slice(0, Math.max(1, Math.min(limit, 20)));
  }

  return {
    archiveManifest,
    isDemo,
    loadArchivedSnapshotForArticle,
    refresh,
    searchArchive,
    snapshot,
    state,
  };
});
