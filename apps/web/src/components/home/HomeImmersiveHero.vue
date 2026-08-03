<script setup lang="ts">
import { PhArrowRight, PhSparkle } from '@phosphor-icons/vue';

import SignalParticleField from './SignalParticleField.vue';
import TrackedEcosystem from './TrackedEcosystem.vue';
</script>

<template>
  <div class="home-immersive-intro" data-page-intro>
    <section class="home-hero" data-home-hero aria-labelledby="home-hero-title">
      <SignalParticleField />
      <div class="home-hero__glow" aria-hidden="true"></div>
      <div class="home-hero__orbit home-hero__orbit--wide" aria-hidden="true"></div>
      <div class="home-hero__orbit home-hero__orbit--tight" aria-hidden="true"></div>

      <div class="page-container home-hero__inner">
        <p class="home-hero__eyebrow">
          <span aria-hidden="true"></span>
          AI &amp; DATA INTELLIGENCE
        </p>
        <h1 id="home-hero-title">发现变化，看见脉络</h1>
        <p class="home-hero__description">
          汇集海内外 AI、数据与开发工具动态，提供中文整理、主题筛选和原文回链。
        </p>
        <div class="home-hero__actions">
          <RouterLink class="button home-hero__primary" to="/profile">
            <PhSparkle :size="17" weight="fill" aria-hidden="true" />
            设置关注偏好
          </RouterLink>
          <RouterLink class="home-hero__secondary" to="/product">
            查看产品介绍
            <PhArrowRight :size="16" aria-hidden="true" />
          </RouterLink>
        </div>
      </div>
    </section>

    <TrackedEcosystem />
    <div class="home-hero-transition" aria-hidden="true"></div>
  </div>
</template>

<style scoped>
.home-immersive-intro {
  position: relative;
  background: #07091a;
}

.home-hero {
  position: relative;
  min-height: clamp(32rem, calc(100dvh - 8.5rem), 42rem);
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(circle at 50% 42%, rgb(110 72 214 / 22%), transparent 30%),
    radial-gradient(circle at 72% 16%, rgb(41 88 183 / 14%), transparent 28%),
    linear-gradient(180deg, #07091a 0%, #090a1f 72%, #07091a 100%);
  color: #f7f5ff;
}

.home-hero::before {
  position: absolute;
  z-index: 0;
  inset: 0;
  background-image:
    linear-gradient(rgb(255 255 255 / 1.8%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 1.8%) 1px, transparent 1px);
  background-size: 5.25rem 5.25rem;
  content: '';
  mask-image: radial-gradient(circle at center, #000 0%, transparent 70%);
  pointer-events: none;
}

.home-hero__glow {
  position: absolute;
  z-index: 0;
  top: 48%;
  left: 50%;
  width: min(48rem, 76vw);
  aspect-ratio: 1.8;
  border-radius: 50%;
  background: rgb(128 91 232 / 11%);
  filter: blur(52px);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

.home-hero__orbit {
  position: absolute;
  z-index: 0;
  top: 49%;
  left: 50%;
  border: 1px solid rgb(171 144 255 / 12%);
  border-radius: 50%;
  pointer-events: none;
  transform: translate(-50%, -50%) rotate(-9deg);
}

.home-hero__orbit::after {
  position: absolute;
  top: 16%;
  right: 10%;
  width: 0.32rem;
  height: 0.32rem;
  border-radius: 50%;
  background: #b49aff;
  box-shadow: 0 0 1.25rem rgb(180 154 255 / 72%);
  content: '';
}

.home-hero__orbit--wide {
  width: min(72rem, 92vw);
  aspect-ratio: 2.35;
  animation: orbit-breathe-wide 13s ease-in-out infinite alternate;
}

.home-hero__orbit--tight {
  width: min(48rem, 72vw);
  aspect-ratio: 2.05;
  border-color: rgb(116 150 255 / 10%);
  transform: translate(-50%, -50%) rotate(14deg);
  animation: orbit-breathe-tight 16s ease-in-out infinite alternate;
}

.home-hero__orbit--tight::after {
  top: auto;
  right: auto;
  bottom: 13%;
  left: 15%;
  width: 0.24rem;
  height: 0.24rem;
  background: #809cff;
}

.home-hero__inner {
  position: relative;
  z-index: 2;
  display: flex;
  min-height: inherit;
  max-width: 58rem;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-block: 6rem 4.5rem;
  text-align: center;
}

.home-hero__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  margin: 0 0 1.5rem;
  color: rgb(218 207 255 / 78%);
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.18em;
}

.home-hero__eyebrow span {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: #9a77ff;
  box-shadow: 0 0 1rem rgb(154 119 255 / 82%);
}

.home-hero h1 {
  max-width: 12ch;
  margin: 0;
  color: #f8f6ff;
  font-size: clamp(3.4rem, 6.6vw, 6rem);
  font-weight: 610;
  letter-spacing: -0.065em;
  line-height: 0.98;
  text-wrap: balance;
  text-shadow: 0 1rem 4rem rgb(83 45 183 / 28%);
}

.home-hero__description {
  max-width: 38rem;
  margin: 1.75rem 0 0;
  color: rgb(226 222 241 / 72%);
  font-size: clamp(1rem, 1.5vw, 1.12rem);
  line-height: 1.75;
  text-wrap: balance;
}

.home-hero__actions {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  margin-top: 2.25rem;
}

.home-hero__primary {
  border-color: rgb(210 198 255 / 16%);
  background: #7855df;
  color: #fff;
  box-shadow: 0 0.75rem 2.75rem rgb(107 70 214 / 34%);
}

.home-hero__primary:hover {
  background: #8969eb;
  transform: translateY(-1px);
}

.home-hero__secondary {
  display: inline-flex;
  min-height: var(--ne-control-height-md);
  align-items: center;
  gap: 0.5rem;
  padding-inline: 0.35rem;
  color: rgb(239 235 255 / 82%);
  font-size: var(--ne-font-size-body);
  font-weight: 620;
  text-decoration: none;
}

.home-hero__secondary:hover {
  color: #fff;
  text-decoration: underline;
  text-underline-offset: 0.3em;
}

.home-hero-transition {
  position: relative;
  z-index: 1;
  height: clamp(5.5rem, 9vw, 8.5rem);
  background: linear-gradient(180deg, #07091a 0%, #18152b 36%, #ebe8f1 82%, #f5f3fa 100%);
}

@keyframes orbit-breathe-wide {
  from {
    opacity: 0.58;
    transform: translate(-50%, -50%) rotate(-9deg) scale(0.985);
  }
  to {
    opacity: 0.92;
    transform: translate(-50%, -50%) rotate(-7deg) scale(1.015);
  }
}

@keyframes orbit-breathe-tight {
  from {
    opacity: 0.45;
    transform: translate(-50%, -50%) rotate(14deg) scale(1.01);
  }
  to {
    opacity: 0.8;
    transform: translate(-50%, -50%) rotate(12deg) scale(0.99);
  }
}

@media (max-width: 767px) {
  .home-hero {
    min-height: clamp(31rem, calc(100dvh - 6.5rem), 38rem);
  }

  .home-hero::before {
    background-size: 3.5rem 3.5rem;
  }

  .home-hero__inner {
    align-items: flex-start;
    padding-block: 5rem 3.5rem;
    text-align: left;
  }

  .home-hero h1 {
    max-width: 8ch;
    font-size: clamp(3rem, 14vw, 4.25rem);
    letter-spacing: -0.07em;
    line-height: 1.02;
    text-wrap: wrap;
  }

  .home-hero__description {
    max-width: 31rem;
    text-wrap: wrap;
  }

  .home-hero__actions {
    width: 100%;
    align-items: flex-start;
    flex-direction: column;
    gap: 0.75rem;
  }

  .home-hero__primary {
    width: 100%;
  }

  .home-hero__orbit--wide {
    width: 155vw;
  }

  .home-hero__orbit--tight {
    width: 110vw;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-hero__orbit {
    animation: none;
  }
}
</style>
