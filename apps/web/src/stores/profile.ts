import { computed, ref } from 'vue';
import { defineStore } from 'pinia';

const STORAGE_KEY = 'newseviday-profile-v1';
const FIELD_LIMITS = { role: 80, work: 200, goal: 240, description: 500 } as const;
const TOPIC_ID = /^[a-z0-9-]{2,80}$/;

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
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Partial<LocalProfile>;
  const validFields = (Object.keys(FIELD_LIMITS) as Array<keyof typeof FIELD_LIMITS>).every(
    (key) =>
      typeof candidate[key] === 'string' && (candidate[key] as string).length <= FIELD_LIMITS[key],
  );
  const interestEntries =
    candidate.interests &&
    typeof candidate.interests === 'object' &&
    !Array.isArray(candidate.interests)
      ? Object.entries(candidate.interests)
      : [];
  return (
    candidate.version === 1 &&
    validFields &&
    interestEntries.length <= 12 &&
    interestEntries.every(
      ([topicId, weight]) =>
        TOPIC_ID.test(topicId) &&
        Number.isInteger(weight) &&
        Number(weight) >= 1 &&
        Number(weight) <= 5,
    ) &&
    typeof candidate.updatedAt === 'string' &&
    candidate.updatedAt.length <= 35 &&
    Number.isFinite(Date.parse(candidate.updatedAt))
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
