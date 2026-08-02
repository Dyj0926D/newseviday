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
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import InnerPageHero from '../components/InnerPageHero.vue';
import InlineNotice from '../components/home/InlineNotice.vue';
import { useContentStore } from '../stores/content';
import { useProfileStore } from '../stores/profile';

const router = useRouter();
const content = useContentStore();
const profileStore = useProfileStore();
const role = ref('');
const work = ref('');
const goal = ref('');
const description = ref('');
const interests = ref<Record<string, number>>({});
const message = ref('');
const importError = ref('');
const fileInput = ref<HTMLInputElement | null>(null);

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
  message.value = '画像已保存在当前浏览器。';
  void router.push({ path: '/', query: { view: 'recommended' } });
}

function clearProfile(): void {
  if (!profileStore.hasProfile) return;
  if (!window.confirm('确认清除当前浏览器中的个人画像？')) return;
  profileStore.clear();
  role.value = '';
  work.value = '';
  goal.value = '';
  description.value = '';
  interests.value = {};
  message.value = '画像已清除，推荐恢复为通用排序。';
}

function exportProfile(): void {
  const blob = new Blob([profileStore.exportJson()], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'newseviday-profile-v1.json';
  link.click();
  URL.revokeObjectURL(url);
  message.value = '画像 JSON 已导出。';
}

async function importProfile(event: Event): Promise<void> {
  importError.value = '';
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    profileStore.importJson(await file.text());
    loadSavedProfile();
    message.value = '画像已导入并保存在当前浏览器。';
  } catch {
    importError.value = '导入失败：文件不是 NewsEviday v1 画像，现有画像未被覆盖。';
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
      eyebrow="OPTIONAL LOCAL PROFILE"
      title="让推荐更接近你正在解决的问题"
      description="画像完全可选，只保存在当前浏览器。即使不设置，通用情报流仍然可以正常使用。"
    />

    <section class="page-container profile-layout">
      <div class="profile-form-column">
        <InlineNotice
          title="你的输入不会同步到账号"
          description="当前项目没有登录体系。保存、导入和清除都只影响本机浏览器，请勿填写公司敏感信息。"
        />

        <form class="profile-form" @submit.prevent="saveProfile">
          <section>
            <div class="form-section-heading">
              <span>01</span>
              <div>
                <h2>基础信息</h2>
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
                <h2>可选语义增强</h2>
                <p>未来可将自由描述整理成结构化画像，结果必须由用户确认后才生效。</p>
              </div>
            </div>
            <button class="button button--secondary" type="button" disabled>
              <PhSparkle :size="17" aria-hidden="true" />
              AI 增强当前暂停
            </button>
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
              清除画像
            </button>
          </div>
          <p class="form-message" aria-live="polite">{{ message }}</p>
        </form>

        <section class="profile-portability">
          <div>
            <PhLockKey :size="20" aria-hidden="true" />
            <div>
              <h2>迁移与控制</h2>
              <p>可以导出版本化 JSON，在另一台设备导入。</p>
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
              导出画像
            </button>
            <button class="button button--secondary" type="button" @click="fileInput?.click()">
              <PhUploadSimple :size="17" aria-hidden="true" />
              导入画像
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
        <h2 id="profile-preview-title">结构化画像预览</h2>
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
