// @vitest-environment jsdom
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import BrandMark from './BrandMark.vue';

describe('BrandMark', () => {
  it('renders the selected Signal N geometry as a decorative SVG', () => {
    const wrapper = mount(BrandMark);
    const svg = wrapper.get('svg');

    expect(svg.attributes('viewBox')).toBe('0 0 32 32');
    expect(svg.attributes('aria-hidden')).toBe('true');
    expect(wrapper.findAll('.brand__mark-line')).toHaveLength(2);
    expect(wrapper.get('.brand__mark-node').attributes('r')).toBe('3.25');
  });
});
