<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  alpha: number;
}

interface Ripple {
  x: number;
  y: number;
  radius: number;
  alpha: number;
}

const canvas = ref<HTMLCanvasElement | null>(null);
const particles: Particle[] = [];
const ripples: Ripple[] = [];
const pointer = { x: 0, y: 0, active: false };

let context: CanvasRenderingContext2D | null = null;
let host: HTMLElement | null = null;
let resizeObserver: ResizeObserver | null = null;
let visibilityObserver: IntersectionObserver | null = null;
let animationFrame = 0;
let width = 0;
let height = 0;
let lastFrame = 0;
let isVisible = true;
let reducedMotion = false;

function seededRandom(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let result = value;
    result = Math.imul(result ^ (result >>> 15), result | 1);
    result ^= result + Math.imul(result ^ (result >>> 7), result | 61);
    return ((result ^ (result >>> 14)) >>> 0) / 4294967296;
  };
}

function rebuildParticles(): void {
  const random = seededRandom(Math.round(width * 17 + height * 31));
  const count = width < 640 ? 28 : width < 1024 ? 42 : 72;
  particles.length = 0;
  for (let index = 0; index < count; index += 1) {
    particles.push({
      x: random() * width,
      y: random() * height,
      vx: (random() - 0.5) * 0.12,
      vy: (random() - 0.5) * 0.12,
      radius: 0.55 + random() * 1.15,
      alpha: 0.18 + random() * 0.48,
    });
  }
}

function resizeCanvas(): void {
  if (!canvas.value || !context) return;
  const bounds = canvas.value.getBoundingClientRect();
  const nextWidth = Math.max(1, Math.round(bounds.width));
  const nextHeight = Math.max(1, Math.round(bounds.height));
  if (nextWidth === width && nextHeight === height) return;

  width = nextWidth;
  height = nextHeight;
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
  canvas.value.width = Math.round(width * pixelRatio);
  canvas.value.height = Math.round(height * pixelRatio);
  context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  rebuildParticles();
  draw(0);
}

function draw(delta: number): void {
  if (!context) return;
  context.clearRect(0, 0, width, height);

  const connectionDistance = width < 640 ? 94 : 126;
  const pointerDistance = width < 640 ? 96 : 170;
  const positions = particles.map((particle) => {
    if (!reducedMotion && delta > 0) {
      particle.x += particle.vx * delta;
      particle.y += particle.vy * delta;
      if (particle.x < -8) particle.x = width + 8;
      if (particle.x > width + 8) particle.x = -8;
      if (particle.y < -8) particle.y = height + 8;
      if (particle.y > height + 8) particle.y = -8;
    }

    let offsetX = 0;
    let offsetY = 0;
    let pointerStrength = 0;
    if (pointer.active && !reducedMotion) {
      const dx = pointer.x - particle.x;
      const dy = pointer.y - particle.y;
      const distance = Math.hypot(dx, dy);
      pointerStrength = Math.max(0, 1 - distance / pointerDistance);
      if (distance > 0) {
        offsetX = (dx / distance) * pointerStrength * 5;
        offsetY = (dy / distance) * pointerStrength * 5;
      }
    }
    return { particle, x: particle.x + offsetX, y: particle.y + offsetY, pointerStrength };
  });

  for (let leftIndex = 0; leftIndex < positions.length; leftIndex += 1) {
    const left = positions[leftIndex];
    if (!left) continue;
    for (let rightIndex = leftIndex + 1; rightIndex < positions.length; rightIndex += 1) {
      const right = positions[rightIndex];
      if (!right) continue;
      const distance = Math.hypot(left.x - right.x, left.y - right.y);
      if (distance >= connectionDistance) continue;
      const alpha = (1 - distance / connectionDistance) * 0.12;
      context.beginPath();
      context.moveTo(left.x, left.y);
      context.lineTo(right.x, right.y);
      context.strokeStyle = `rgba(164, 139, 255, ${alpha})`;
      context.lineWidth = 0.65;
      context.stroke();
    }
  }

  for (const position of positions) {
    const glow = position.pointerStrength * 0.42;
    context.beginPath();
    context.arc(position.x, position.y, position.particle.radius + glow * 1.7, 0, Math.PI * 2);
    context.fillStyle = `rgba(222, 214, 255, ${Math.min(0.94, position.particle.alpha + glow)})`;
    context.fill();
  }

  for (let index = ripples.length - 1; index >= 0; index -= 1) {
    const ripple = ripples[index];
    if (!ripple) continue;
    ripple.radius += delta * 0.055;
    ripple.alpha -= delta * 0.00042;
    if (ripple.alpha <= 0) {
      ripples.splice(index, 1);
      continue;
    }
    context.beginPath();
    context.arc(ripple.x, ripple.y, ripple.radius, 0, Math.PI * 2);
    context.strokeStyle = `rgba(171, 144, 255, ${ripple.alpha})`;
    context.lineWidth = 1.2;
    context.stroke();
  }
}

function animate(time: number): void {
  const delta = Math.min(32, lastFrame ? time - lastFrame : 16);
  lastFrame = time;
  draw(delta);
  if (isVisible && !document.hidden && !reducedMotion) {
    animationFrame = window.requestAnimationFrame(animate);
  }
}

function startAnimation(): void {
  window.cancelAnimationFrame(animationFrame);
  if (!isVisible || document.hidden || reducedMotion) {
    draw(0);
    return;
  }
  lastFrame = 0;
  animationFrame = window.requestAnimationFrame(animate);
}

function updatePointer(event: PointerEvent): void {
  if (!host || reducedMotion) return;
  const bounds = host.getBoundingClientRect();
  pointer.x = event.clientX - bounds.left;
  pointer.y = event.clientY - bounds.top;
  pointer.active = true;
}

function clearPointer(): void {
  pointer.active = false;
}

function createRipple(event: PointerEvent): void {
  if (!host || reducedMotion) return;
  const bounds = host.getBoundingClientRect();
  ripples.push({
    x: event.clientX - bounds.left,
    y: event.clientY - bounds.top,
    radius: 12,
    alpha: 0.42,
  });
}

function handleVisibility(): void {
  startAnimation();
}

onMounted(() => {
  if (!canvas.value) return;
  context = canvas.value.getContext('2d');
  if (!context) return;
  host = canvas.value.closest<HTMLElement>('[data-home-hero]');
  reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(canvas.value);
  } else {
    window.addEventListener('resize', resizeCanvas);
  }

  if (typeof IntersectionObserver !== 'undefined') {
    visibilityObserver = new IntersectionObserver(([entry]) => {
      isVisible = entry?.isIntersecting ?? true;
      startAnimation();
    });
    visibilityObserver.observe(canvas.value);
  }

  host?.addEventListener('pointermove', updatePointer, { passive: true });
  host?.addEventListener('pointerleave', clearPointer, { passive: true });
  host?.addEventListener('pointerdown', createRipple, { passive: true });
  document.addEventListener('visibilitychange', handleVisibility);
  resizeCanvas();
  startAnimation();
});

onBeforeUnmount(() => {
  window.cancelAnimationFrame(animationFrame);
  resizeObserver?.disconnect();
  visibilityObserver?.disconnect();
  window.removeEventListener('resize', resizeCanvas);
  host?.removeEventListener('pointermove', updatePointer);
  host?.removeEventListener('pointerleave', clearPointer);
  host?.removeEventListener('pointerdown', createRipple);
  document.removeEventListener('visibilitychange', handleVisibility);
});
</script>

<template>
  <canvas ref="canvas" class="signal-particle-field" aria-hidden="true"></canvas>
</template>

<style scoped>
.signal-particle-field {
  position: absolute;
  z-index: 0;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
