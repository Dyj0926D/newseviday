// @vitest-environment jsdom
import { mount, shallowMount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import HomeImmersiveHero from './HomeImmersiveHero.vue';
import TrackedEcosystem from './TrackedEcosystem.vue';

describe('HomeImmersiveHero', () => {
  it('keeps the approved message and both primary routes', () => {
    const wrapper = shallowMount(HomeImmersiveHero, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="to"><slot /></a>',
          },
        },
      },
    });

    expect(wrapper.get('h1').text()).toBe('发现变化，看见脉络');
    expect(wrapper.text()).toContain('汇集海内外 AI、数据与开发工具动态');
    const links = wrapper.findAll('[data-to]');
    expect(links.map((link) => link.attributes('data-to'))).toEqual(['/profile', '/product']);
  });

  it('uses the immersive wrapper as the header observation boundary', () => {
    const wrapper = shallowMount(HomeImmersiveHero, {
      global: { stubs: { RouterLink: true } },
    });

    expect(wrapper.get('[data-page-intro]').attributes('class')).toContain('home-immersive-intro');
    expect(wrapper.get('[data-home-hero]').attributes('aria-labelledby')).toBe('home-hero-title');
  });
});

describe('TrackedEcosystem', () => {
  it('renders locally bundled ecosystem assets and a non-partnership disclosure', () => {
    const wrapper = mount(TrackedEcosystem);
    const images = wrapper.findAll('img');

    expect(wrapper.text()).toContain('持续追踪的公开生态');
    expect(wrapper.text()).toContain('不代表合作或隶属关系');
    expect(images.length).toBeGreaterThan(10);
    expect(images.every((item) => item.attributes('src')?.startsWith('/assets/ecosystem/'))).toBe(
      true,
    );
  });
});
