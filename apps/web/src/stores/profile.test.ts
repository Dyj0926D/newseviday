// @vitest-environment jsdom
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useProfileStore } from './profile';

describe('profile store', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it('persists a versioned local profile and hydrates it in a new store', () => {
    const store = useProfileStore();
    store.save({
      role: 'AI 产品经理',
      work: 'Data Agent',
      goal: '跟踪统一语义',
      description: '',
      interests: { 'data-agent': 5, 'semantic-layer': 4 },
    });

    setActivePinia(createPinia());
    const restored = useProfileStore();
    restored.hydrate();

    expect(restored.profile?.version).toBe(1);
    expect(restored.profile?.role).toBe('AI 产品经理');
    expect(restored.profile?.interests['data-agent']).toBe(5);
  });

  it('imports a valid profile and does not accept another schema', () => {
    const store = useProfileStore();
    store.importJson(
      JSON.stringify({
        version: 1,
        role: '',
        work: '数据中台',
        goal: '',
        description: '',
        interests: { 'intelligent-lakehouse': 3 },
        updatedAt: '2026-08-02T00:00:00.000Z',
      }),
    );

    expect(store.profile?.work).toBe('数据中台');
    expect(() => store.importJson(JSON.stringify({ version: 2 }))).toThrow(
      'invalid_profile_schema',
    );
    expect(store.profile?.work).toBe('数据中台');
  });

  it('clears the local profile', () => {
    const store = useProfileStore();
    store.save({ role: 'PM', work: '', goal: '', description: '', interests: {} });

    store.clear();

    expect(store.profile).toBeNull();
    expect(store.hasProfile).toBe(false);
  });
});
