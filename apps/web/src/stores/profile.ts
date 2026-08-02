import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

const STORAGE_KEY = 'newseviday-profile-v1';

export interface LocalProfile {
  version: 1;
  role: string;
  work: string;
  goal: string;
  description: string;
  interests: Record<string, number>;
  updatedAt: string;
}

function isLocalProfile(value: unknown): value is LocalProfile {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<LocalProfile>;
  return (
    candidate.version === 1 &&
    typeof candidate.role === 'string' &&
    typeof candidate.work === 'string' &&
    typeof candidate.goal === 'string' &&
    typeof candidate.description === 'string' &&
    Boolean(candidate.interests) &&
    typeof candidate.interests === 'object' &&
    typeof candidate.updatedAt === 'string'
  );
}

export const useProfileStore = defineStore('profile', () => {
  const profile = ref<LocalProfile | null>(null);
  const hydrated = ref(false);
  const hasProfile = computed(() => profile.value !== null);

  function hydrate(): void {
    if (hydrated.value) return;
    hydrated.value = true;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    try {
      const parsed: unknown = JSON.parse(stored);
      if (isLocalProfile(parsed)) profile.value = parsed;
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  function save(input: Omit<LocalProfile, 'version' | 'updatedAt'>): LocalProfile {
    const next: LocalProfile = {
      ...input,
      version: 1,
      updatedAt: new Date().toISOString(),
    };
    profile.value = next;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  function clear(): void {
    profile.value = null;
    localStorage.removeItem(STORAGE_KEY);
  }

  function exportJson(): string {
    if (!profile.value) throw new Error('profile_not_found');
    return `${JSON.stringify(profile.value, null, 2)}\n`;
  }

  function importJson(raw: string): LocalProfile {
    const parsed: unknown = JSON.parse(raw);
    if (!isLocalProfile(parsed)) throw new Error('invalid_profile_schema');
    profile.value = parsed;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed));
    return parsed;
  }

  return { clear, exportJson, hasProfile, hydrate, hydrated, importJson, profile, save };
});
