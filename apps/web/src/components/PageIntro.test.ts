// @vitest-environment jsdom
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import PageIntro from './PageIntro.vue';

describe('PageIntro', () => {
  it('renders the page title and description', () => {
    const wrapper = mount(PageIntro, {
      props: {
        title: '追踪值得关注的变化',
        description: '经过整理并可回到证据。',
      },
    });

    expect(wrapper.get('h1').text()).toBe('追踪值得关注的变化');
    expect(wrapper.text()).toContain('经过整理并可回到证据。');
  });
});
