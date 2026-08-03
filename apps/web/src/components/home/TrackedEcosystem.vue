<script setup lang="ts">
interface EcosystemItem {
  name: string;
  src: string;
}

const ecosystem: EcosystemItem[] = [
  { name: 'Anthropic', src: '/assets/ecosystem/anthropic.svg' },
  { name: 'DeepSeek', src: '/assets/ecosystem/deepseek.svg' },
  { name: 'Qwen', src: '/assets/ecosystem/qwen.svg' },
  { name: 'Hugging Face', src: '/assets/ecosystem/huggingface.svg' },
  { name: 'Databricks', src: '/assets/ecosystem/databricks.svg' },
  { name: 'arXiv', src: '/assets/ecosystem/arxiv.svg' },
  { name: 'GitHub', src: '/assets/ecosystem/github.svg' },
  { name: 'Alibaba Cloud', src: '/assets/ecosystem/alibabacloud.svg' },
  { name: 'Google', src: '/assets/ecosystem/google.svg' },
  { name: 'Meta', src: '/assets/ecosystem/meta.svg' },
  { name: 'Mistral AI', src: '/assets/ecosystem/mistralai.svg' },
];
</script>

<template>
  <section class="tracked-ecosystem" aria-labelledby="ecosystem-title">
    <div class="page-container tracked-ecosystem__heading">
      <span aria-hidden="true"></span>
      <p id="ecosystem-title">持续追踪的公开生态</p>
      <span aria-hidden="true"></span>
    </div>
    <div class="tracked-ecosystem__viewport">
      <div class="tracked-ecosystem__track">
        <ul class="tracked-ecosystem__list">
          <li v-for="item in ecosystem" :key="item.name">
            <img :src="item.src" alt="" width="24" height="24" loading="eager" />
            <span>{{ item.name }}</span>
          </li>
        </ul>
        <ul class="tracked-ecosystem__list" aria-hidden="true">
          <li v-for="item in ecosystem" :key="`duplicate-${item.name}`">
            <img :src="item.src" alt="" width="24" height="24" loading="lazy" />
            <span>{{ item.name }}</span>
          </li>
        </ul>
      </div>
    </div>
    <p class="visually-hidden">以上名称表示公开信息追踪范围，不代表合作或隶属关系。</p>
  </section>
</template>

<style scoped>
.tracked-ecosystem {
  position: relative;
  z-index: 2;
  padding-block: 1.25rem 2rem;
  overflow: hidden;
  background: #07091a;
  color: rgb(239 235 255 / 72%);
}

.tracked-ecosystem__heading {
  display: grid;
  max-width: 56rem;
  grid-template-columns: minmax(2rem, 1fr) auto minmax(2rem, 1fr);
  align-items: center;
  gap: 1.25rem;
}

.tracked-ecosystem__heading span {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgb(171 144 255 / 26%));
}

.tracked-ecosystem__heading span:last-child {
  background: linear-gradient(90deg, rgb(171 144 255 / 26%), transparent);
}

.tracked-ecosystem__heading p {
  margin: 0;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.tracked-ecosystem__viewport {
  position: relative;
  margin-top: 1.5rem;
  overflow: hidden;
  mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent);
}

.tracked-ecosystem__track {
  display: flex;
  width: max-content;
  animation: ecosystem-marquee 42s linear infinite;
}

.tracked-ecosystem__list {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2.75rem;
  margin: 0;
  padding: 0 1.375rem;
  list-style: none;
}

.tracked-ecosystem__list li {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  opacity: 0.46;
  white-space: nowrap;
  transition: opacity 180ms ease;
}

.tracked-ecosystem__list li:hover {
  opacity: 0.82;
}

.tracked-ecosystem__list img {
  width: 1.15rem;
  height: 1.15rem;
  object-fit: contain;
}

.tracked-ecosystem__list span {
  font-size: 0.77rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

@keyframes ecosystem-marquee {
  to {
    transform: translateX(-50%);
  }
}

@media (max-width: 767px) {
  .tracked-ecosystem {
    padding-block: 0.75rem 1.5rem;
  }

  .tracked-ecosystem__viewport {
    overflow-x: auto;
    mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent);
    scrollbar-width: none;
  }

  .tracked-ecosystem__viewport::-webkit-scrollbar {
    display: none;
  }

  .tracked-ecosystem__track {
    animation-duration: 58s;
  }

  .tracked-ecosystem__list {
    gap: 2rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tracked-ecosystem__viewport {
    overflow-x: auto;
    mask-image: none;
  }

  .tracked-ecosystem__track {
    animation: none;
  }

  .tracked-ecosystem__list[aria-hidden='true'] {
    display: none;
  }
}
</style>
