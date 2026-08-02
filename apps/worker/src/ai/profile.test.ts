import type { ProfileEnhanceRequest } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import { parseProfileCompletion, validateProfileRequest } from './profile';

const input: ProfileEnhanceRequest = {
  role: 'AI 产品经理',
  work: '数据中台',
  goal: '跟踪 Data Agent',
  description: '',
};

describe('profile enhancement', () => {
  it('requires explicit non-empty user input', () => {
    expect(() => validateProfileRequest({ role: '', work: '', goal: '', description: '' })).toThrow(
      'At least one profile field',
    );
  });

  it('filters unknown topics and preserves a reviewable structure', () => {
    const result = parseProfileCompletion(
      JSON.stringify({
        ...input,
        interests: [
          { topicId: 'data-agent', weight: 5, reason: '与当前目标直接相关' },
          { topicId: 'sensitive-profile', weight: 5, reason: '不应接受' },
        ],
        inferredTerms: ['语义层'],
        warnings: ['请勿填写公司敏感信息'],
      }),
      input,
      ['data-agent'],
      'mock-model',
    );

    expect(result.interests).toHaveLength(1);
    expect(result.interests[0]?.topicId).toBe('data-agent');
    expect(result.promptVersion).toBe('profile-enhancement-v1');
  });
});
