<script setup lang="ts">
import {
  PhArrowRight,
  PhDownloadSimple,
  PhFloppyDisk,
  PhLockKey,
  PhSparkle,
  PhTrash,
  PhUploadSimple,
} from '@phosphor-icons/vue';
import { API_PATHS, type ApiResponse, type ProfileEnhanceData } from '@newseviday/contracts';
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import InnerPageHero from '../components/InnerPageHero.vue';
import TurnstileWidget from '../components/TurnstileWidget.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import { useContentStore } from '../stores/content';
import { useProfileStore } from '../stores/profile';
import { useRuntimeStore } from '../stores/runtime';

const router = useRouter();
const content = useContentStore();
const profileStore = useProfileStore();
const runtime = useRuntimeStore();
const role = ref('');
const work = ref('');
const goal = ref('');
const description = ref('');
const interests = ref<Record<string, number>>({});
const message = ref('');
const importError = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const enhancement = ref<ProfileEnhanceData | null>(null);
const enhancementError = ref('');
const enhancing = ref(false);
const turnstileToken = ref('');
const turnstileResetKey = ref(0);

const topics = computed(() => content.snapshot?.topics ?? []);
const selectedTopics = computed(() =>
  topics.value.filter((topic) => (interests.value[topic.id] ?? 0) > 0),
);
const canSave = computed(
  () =>
    Boolean(
      role.value.trim() || work.value.trim() || goal.value.trim() || description.value.trim(),
    ) || selectedTopics.value.length > 0,
);
const aiAvailable = computed(
  () => runtime.status?.ai.state === 'available' || runtime.status?.ai.state === 'saving-mode',
);
const turnstileRequired = computed(
  () =>
    runtime.status?.protection?.turnstile === 'enabled' ||
    Boolean(runtime.config?.features.turnstile),
);
const turnstileSiteKey = computed(() => runtime.config?.protection?.turnstileSiteKey ?? '');
const verificationReady = computed(
  () => !turnstileRequired.value || Boolean(turnstileSiteKey.value),
);
const canEnhance = computed(
  () =>
    aiAvailable.value &&
    verificationReady.value &&
    !enhancing.value &&
    (!turnstileRequired.value || Boolean(turnstileToken.value)) &&
    Boolean(
      role.value.trim() || work.value.trim() || goal.value.trim() || description.value.trim(),
    ),
);

function loadSavedProfile(): void {
  const saved = profileStore.profile;
  if (!saved) return;
  role.value = saved.role;
  work.value = saved.work;
  goal.value = saved.goal;
  description.value = saved.description;
  interests.value = { ...saved.interests };
}

function toggleTopic(topicId: string): void {
  interests.value = {
    ...interests.value,
    [topicId]: (interests.value[topicId] ?? 0) > 0 ? 0 : 3,
  };
}

function updateWeight(topicId: string, value: string): void {
  interests.value = { ...interests.value, [topicId]: Number(value) };
}

function saveProfile(): void {
  if (!canSave.value) return;
  profileStore.save({
    role: role.value.trim(),
    work: work.value.trim(),
    goal: goal.value.trim(),
    description: description.value.trim(),
    interests: Object.fromEntries(
      Object.entries(interests.value).filter(([, weight]) => weight > 0),
    ),
  });
  message.value = '关注偏好已保存在当前浏览器。';
  void router.push({ path: '/', query: { view: 'recommended' } });
}

async function requestEnhancement(): Promise<void> {
  if (!canEnhance.value) return;
  enhancement.value = null;
  enhancementError.value = '';
  enhancing.value = true;
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';
  try {
    const response = await fetch(`${baseUrl}${API_PATHS.profileEnhance}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'Idempotency-Key': crypto.randomUUID(),
        ...(turnstileToken.value ? { 'X-Turnstile-Token': turnstileToken.value } : {}),
      },
      body: JSON.stringify({
        role: role.value,
        work: work.value,
        goal: goal.value,
        description: description.value,
      }),
    });
    const payload = (await response.json()) as ApiResponse<ProfileEnhanceData>;
    if (!response.ok || !payload.ok) {
      throw new Error(payload.ok ? 'request_failed' : payload.error.code);
    }
    enhancement.value = payload.data;
  } catch (error) {
    const code = error instanceof Error ? error.message : '';
    if (code === 'ai_unavailable') {
      enhancementError.value = '智能整理当前暂不可用，你仍可手动设置关注偏好。';
    } else if (code === 'rate_limited') {
      enhancementError.value = '今天的智能整理额度已用完，你仍可继续手动编辑。';
    } else if (code === 'budget_paused') {
      enhancementError.value = '本月生成额度已暂停，你仍可继续手动编辑。';
    } else if (code === 'verification_required' || code === 'verification_failed') {
      enhancementError.value = '安全验证未通过，请重新验证后再试。';
    } else if (code === 'guardrails_unavailable') {
      enhancementError.value = '生成保护服务暂时不可用，你仍可继续手动编辑。';
    } else if (code === 'request_conflict') {
      enhancementError.value = '本次请求凭证已使用，请重新验证后再试。';
    } else {
      enhancementError.value = '增强失败，原有输入没有改变，请稍后重试或继续手动编辑。';
    }
  } finally {
    enhancing.value = false;
    if (turnstileRequired.value) turnstileResetKey.value += 1;
  }
}

function applyEnhancement(): void {
  if (!enhancement.value) return;
  role.value = enhancement.value.role;
  work.value = enhancement.value.work;
  goal.value = enhancement.value.goal;
  description.value = enhancement.value.description;
  interests.value = {
    ...interests.value,
    ...Object.fromEntries(enhancement.value.interests.map((item) => [item.topicId, item.weight])),
  };
  enhancement.value = null;
  message.value = '整理建议已填入表单，尚未保存。请检查后再确认保存。';
}

function clearProfile(): void {
  if (!profileStore.hasProfile) return;
  if (!window.confirm('确认清除当前浏览器中的关注偏好？')) return;
  profileStore.clear();
  role.value = '';
  work.value = '';
  goal.value = '';
  description.value = '';
  interests.value = {};
  message.value = '关注偏好已清除，推荐恢复为通用排序。';
}

function exportProfile(): void {
  const blob = new Blob([profileStore.exportJson()], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'newseviday-preferences-v1.json';
  link.click();
  URL.revokeObjectURL(url);
  message.value = '关注偏好设置已导出。';
}

async function importProfile(event: Event): Promise<void> {
  importError.value = '';
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    profileStore.importJson(await file.text());
    loadSavedProfile();
    message.value = '关注偏好已导入并保存在当前浏览器。';
  } catch {
    importError.value = '导入失败：文件格式不正确，现有关注偏好未被覆盖。';
  } finally {
    input.value = '';
  }
}

onMounted(() => {
  profileStore.hydrate();
  loadSavedProfile();
});
</script>

<template>
  <main id="main-content">
    <InnerPageHero
      eyebrow="LOCAL PREFERENCES"
      title="让推荐更接近你正在解决的问题"
      description="关注偏好完全可选，只保存在当前浏览器。即使不设置，最新情报仍然可以正常浏览。"
    />

    <section class="page-container profile-layout">
      <div class="profile-form-column">
        <InlineNotice
          title="你的输入不会同步到账号"
          description="当前没有账号同步。保存、备份和清除都只影响本机浏览器，请勿填写公司敏感信息。"
        />

        <form class="profile-form" @submit.prevent="saveProfile">
          <section>
            <div class="form-section-heading">
              <span>01</span>
              <div>
                <h2>关注背景</h2>
                <p>至少填写一项，所有字段都可以留空。</p>
              </div>
            </div>
            <div class="form-grid">
              <label>
                <span>你的角色</span>
                <input v-model="role" type="text" placeholder="例如：AI 产品经理" />
              </label>
              <label>
                <span>当前工作</span>
                <input v-model="work" type="text" placeholder="例如：数据中台与 Data Agent" />
              </label>
              <label class="form-grid__wide">
                <span>希望解决的问题</span>
                <input
                  v-model="goal"
                  type="text"
                  placeholder="例如：跟踪统一语义与智能数据湖的产品变化"
                />
              </label>
              <label class="form-grid__wide">
                <span>补充描述</span>
                <textarea
                  v-model="description"
                  rows="4"
                  placeholder="可以写关注方向、少看内容或学习目标"
                ></textarea>
              </label>
            </div>
          </section>

          <section>
            <div class="form-section-heading">
              <span>02</span>
              <div>
                <h2>关注主题</h2>
                <p>选择主题后可以调整权重，1 表示偶尔关注，5 表示重点关注。</p>
              </div>
            </div>
            <div class="profile-topic-picker">
              <button
                v-for="topic in topics"
                :key="topic.id"
                type="button"
                :aria-pressed="(interests[topic.id] ?? 0) > 0"
                @click="toggleTopic(topic.id)"
              >
                {{ topic.label }}
              </button>
            </div>
            <div v-if="selectedTopics.length" class="weight-list">
              <label v-for="topic in selectedTopics" :key="topic.id">
                <span>{{ topic.label }}</span>
                <input
                  type="range"
                  min="1"
                  max="5"
                  :value="interests[topic.id]"
                  @input="updateWeight(topic.id, ($event.target as HTMLInputElement).value)"
                />
                <output>{{ interests[topic.id] }}</output>
              </label>
            </div>
          </section>

          <section>
            <div class="form-section-heading">
              <span>03</span>
              <div>
                <h2>智能整理（可选）</h2>
                <p>把自由描述整理成关注主题建议；预览和确认后才会写入表单。</p>
              </div>
            </div>
            <button
              class="button button--secondary"
              type="button"
              :disabled="!canEnhance"
              @click="requestEnhancement"
            >
              <PhSparkle :size="17" aria-hidden="true" />
              {{ enhancing ? '正在整理…' : aiAvailable ? '整理关注方向' : '智能整理暂不可用' }}
            </button>
            <TurnstileWidget
              v-if="aiAvailable && turnstileRequired && turnstileSiteKey"
              :site-key="turnstileSiteKey"
              :reset-key="turnstileResetKey"
              @token="turnstileToken = $event"
            />
            <p v-else-if="aiAvailable && turnstileRequired" class="form-error" role="status">
              安全验证配置暂时不可用，智能整理保持关闭。
            </p>
            <p v-if="enhancementError" class="form-error" role="alert">
              {{ enhancementError }}
            </p>
            <div v-if="enhancement" class="profile-ai-review" aria-live="polite">
              <div>
                <strong>整理建议待确认</strong>
                <p>
                  {{ enhancement.role || '未补充角色' }} ·
                  {{ enhancement.interests.length }} 个主题建议
                </p>
              </div>
              <ul v-if="enhancement.interests.length">
                <li v-for="item in enhancement.interests" :key="item.topicId">
                  <span>{{
                    topics.find((topic) => topic.id === item.topicId)?.label ?? item.topicId
                  }}</span>
                  <strong>{{ item.weight }} / 5</strong>
                  <small>{{ item.reason }}</small>
                </li>
              </ul>
              <div class="profile-ai-review__actions">
                <button class="button button--primary" type="button" @click="applyEnhancement">
                  应用建议
                </button>
                <button class="button button--secondary" type="button" @click="enhancement = null">
                  放弃
                </button>
              </div>
            </div>
          </section>

          <div class="profile-form__actions">
            <button class="button button--primary" type="submit" :disabled="!canSave">
              <PhFloppyDisk :size="17" aria-hidden="true" />
              保存并查看推荐
            </button>
            <button
              class="button button--secondary"
              type="button"
              :disabled="!profileStore.hasProfile"
              @click="clearProfile"
            >
              <PhTrash :size="17" aria-hidden="true" />
              恢复默认推荐
            </button>
          </div>
          <p class="form-message" aria-live="polite">{{ message }}</p>
        </form>

        <section class="profile-portability">
          <div>
            <PhLockKey :size="20" aria-hidden="true" />
            <div>
              <h2>备份与迁移</h2>
              <p>可以导出设置文件，在另一台设备恢复关注偏好。</p>
            </div>
          </div>
          <div class="profile-portability__actions">
            <button
              class="button button--secondary"
              type="button"
              :disabled="!profileStore.hasProfile"
              @click="exportProfile"
            >
              <PhDownloadSimple :size="17" aria-hidden="true" />
              导出设置
            </button>
            <button class="button button--secondary" type="button" @click="fileInput?.click()">
              <PhUploadSimple :size="17" aria-hidden="true" />
              导入设置
            </button>
            <input
              ref="fileInput"
              class="visually-hidden"
              type="file"
              accept="application/json"
              @change="importProfile"
            />
          </div>
          <p v-if="importError" class="form-error" role="alert">{{ importError }}</p>
        </section>
      </div>

      <aside class="profile-preview" aria-labelledby="profile-preview-title">
        <p class="section-kicker">LOCAL PREVIEW</p>
        <h2 id="profile-preview-title">关注偏好预览</h2>
        <p v-if="!canSave" class="profile-preview__empty">
          填写任意信息或选择主题后，这里会显示保存前的结构化结果。
        </p>
        <dl v-else>
          <div>
            <dt>角色</dt>
            <dd>{{ role || '未填写' }}</dd>
          </div>
          <div>
            <dt>当前工作</dt>
            <dd>{{ work || '未填写' }}</dd>
          </div>
          <div>
            <dt>目标</dt>
            <dd>{{ goal || '未填写' }}</dd>
          </div>
          <div>
            <dt>补充描述</dt>
            <dd>{{ description || '未填写' }}</dd>
          </div>
        </dl>
        <div class="profile-preview__topics">
          <h3>主题权重</h3>
          <p v-if="!selectedTopics.length">未选择主题，将使用通用排序。</p>
          <div v-for="topic in selectedTopics" :key="topic.id">
            <span>{{ topic.label }}</span>
            <strong>{{ interests[topic.id] }} / 5</strong>
          </div>
        </div>
        <RouterLink v-if="profileStore.hasProfile" class="text-link" to="/?view=recommended">
          查看当前推荐
          <PhArrowRight :size="16" aria-hidden="true" />
        </RouterLink>
      </aside>
    </section>
  </main>
</template>
