<script setup lang="ts">
import {
  PhArrowUpRight,
  PhClockCounterClockwise,
  PhGlobeHemisphereWest,
} from '@phosphor-icons/vue';

defineProps<{
  sourceCount: number;
  overseasCount: number;
  newCount: number;
  updatedAt: string | null;
  topics: Array<{ id: string; label: string; count: number }>;
  demo: boolean;
}>();
</script>

<template>
  <aside class="signal-overview" aria-labelledby="signal-title">
    <div class="signal-overview__heading">
      <div>
        <p>SIGNAL OVERVIEW</p>
        <h2 id="signal-title">信号概览</h2>
      </div>
      <span>{{ demo ? '演示样例' : '实时快照' }}</span>
    </div>

    <dl class="signal-metrics">
      <div>
        <dt><PhGlobeHemisphereWest :size="17" aria-hidden="true" /> 海外信号</dt>
        <dd>{{ overseasCount }}</dd>
      </div>
      <div>
        <dt><PhArrowUpRight :size="17" aria-hidden="true" /> 本次新增</dt>
        <dd>{{ newCount }}</dd>
      </div>
      <div>
        <dt><PhClockCounterClockwise :size="17" aria-hidden="true" /> 已接入来源</dt>
        <dd>{{ sourceCount }}</dd>
      </div>
    </dl>

    <div class="topic-signals">
      <div class="topic-signals__heading">
        <h3>主题热度</h3>
        <span>按当前快照统计</span>
      </div>
      <ol>
        <li v-for="(topic, index) in topics" :key="topic.id">
          <span>{{ String(index + 1).padStart(2, '0') }}</span>
          <strong>{{ topic.label }}</strong>
          <small>{{ topic.count }} 条</small>
        </li>
      </ol>
    </div>

    <div class="signal-overview__footer">
      <span>快照时间</span>
      <time v-if="updatedAt" :datetime="updatedAt">
        {{
          new Intl.DateTimeFormat('zh-CN', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
          }).format(new Date(updatedAt))
        }}
      </time>
      <span v-else>暂无快照</span>
      <RouterLink to="/status">查看数据状态</RouterLink>
    </div>
  </aside>
</template>
