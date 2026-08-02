import type {
  ProfileEnhanceData,
  ProfileEnhanceRequest,
  ProfileInterestSuggestion,
} from '@newseviday/contracts';

import type { Env } from '../config';
import { deepSeekConfig, publicTopicIds } from '../config';
import { HttpInputError } from '../http';
import { DeepSeekClient } from './deepseek';
import { NoopUsageRecorder, type TokenPrice, type UsageRecorder } from './types';

export const PROFILE_PROMPT_VERSION = 'profile-enhancement-v1';

const FIELD_LIMITS = {
  role: 80,
  work: 200,
  goal: 240,
  description: 500,
} as const;

type ProfileField = keyof typeof FIELD_LIMITS;

function stringField(value: unknown, name: ProfileField): string {
  if (typeof value !== 'string') {
    throw new HttpInputError('bad_request', `${name} must be a string`, 400);
  }
  const normalized = value.trim();
  if (normalized.length > FIELD_LIMITS[name]) {
    throw new HttpInputError('bad_request', `${name} exceeds its length limit`, 400);
  }
  return normalized;
}

export function validateProfileRequest(value: unknown): ProfileEnhanceRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new HttpInputError('bad_request', 'Profile input must be an object', 400);
  }
  const candidate = value as Record<string, unknown>;
  const result: ProfileEnhanceRequest = {
    role: stringField(candidate.role, 'role'),
    work: stringField(candidate.work, 'work'),
    goal: stringField(candidate.goal, 'goal'),
    description: stringField(candidate.description, 'description'),
  };
  if (!Object.values(result).some(Boolean)) {
    throw new HttpInputError('bad_request', 'At least one profile field is required', 400);
  }
  return result;
}

function stripJsonFence(value: string): string {
  return value
    .trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/, '');
}

function boundedString(value: unknown, maximum: number): string {
  return typeof value === 'string' ? value.trim().slice(0, maximum) : '';
}

function stringList(value: unknown, maximumItems: number, maximumLength: number): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim().slice(0, maximumLength))
    .filter(Boolean)
    .slice(0, maximumItems);
}

function interests(
  value: unknown,
  allowedTopics: ReadonlySet<string>,
): ProfileInterestSuggestion[] {
  if (!Array.isArray(value)) return [];
  const unique = new Set<string>();
  const result: ProfileInterestSuggestion[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const item = raw as Record<string, unknown>;
    const topicId = boundedString(item.topicId, 80);
    const weight = Number(item.weight);
    const reason = boundedString(item.reason, 120);
    if (
      !allowedTopics.has(topicId) ||
      unique.has(topicId) ||
      !Number.isInteger(weight) ||
      weight < 1 ||
      weight > 5 ||
      !reason
    ) {
      continue;
    }
    unique.add(topicId);
    result.push({ topicId, weight, reason });
    if (result.length === 8) break;
  }
  return result;
}

export function parseProfileCompletion(
  content: string,
  input: ProfileEnhanceRequest,
  allowedTopicIds: string[],
  model: string,
): ProfileEnhanceData {
  let payload: unknown;
  try {
    payload = JSON.parse(stripJsonFence(content));
  } catch {
    throw new Error('invalid_model_output');
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('invalid_model_output');
  }
  const candidate = payload as Record<string, unknown>;
  return {
    role: boundedString(candidate.role, FIELD_LIMITS.role) || input.role,
    work: boundedString(candidate.work, FIELD_LIMITS.work) || input.work,
    goal: boundedString(candidate.goal, FIELD_LIMITS.goal) || input.goal,
    description:
      boundedString(candidate.description, FIELD_LIMITS.description) || input.description,
    interests: interests(candidate.interests, new Set(allowedTopicIds)),
    inferredTerms: stringList(candidate.inferredTerms, 12, 80),
    warnings: stringList(candidate.warnings, 5, 120),
    model,
    promptVersion: PROFILE_PROMPT_VERSION,
  };
}

export async function enhanceProfile(
  input: ProfileEnhanceRequest,
  env: Env,
  requestId: string,
  signal?: AbortSignal,
  usageRecorder: UsageRecorder = new NoopUsageRecorder(),
  tokenPrice: TokenPrice | null = null,
): Promise<ProfileEnhanceData> {
  const allowedTopicIds = publicTopicIds(env);
  const client = new DeepSeekClient(deepSeekConfig(env), fetch, usageRecorder, tokenPrice);
  const completion = await client.complete({
    requestId,
    signal,
    temperature: 0.1,
    maxTokens: 900,
    messages: [
      {
        role: 'system',
        content:
          '你负责把用户主动填写的职业与兴趣整理成结构化画像。不得推断年龄、性别、公司、地点、健康、政治、财务或其他敏感属性。只输出 JSON 对象。',
      },
      {
        role: 'user',
        content: [
          `允许的 topicId：${allowedTopicIds.join(', ')}`,
          `用户输入：${JSON.stringify(input)}`,
          '输出 role、work、goal、description、interests、inferredTerms、warnings。',
          'interests 每项包含 topicId、1-5 的 weight 和简短 reason。',
        ].join('\n'),
      },
    ],
  });
  return parseProfileCompletion(completion.content, input, allowedTopicIds, completion.model);
}
