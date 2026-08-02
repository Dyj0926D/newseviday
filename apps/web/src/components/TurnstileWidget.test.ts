// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import TurnstileWidget from './TurnstileWidget.vue';

describe('TurnstileWidget', () => {
  afterEach(() => {
    delete window.turnstile;
    document.querySelectorAll('script[data-newseviday-turnstile]').forEach((item) => item.remove());
    vi.restoreAllMocks();
  });

  it('renders with the public site key and emits a verified token', async () => {
    const remove = vi.fn();
    const reset = vi.fn();
    const render = vi.fn((_element: HTMLElement, options: Record<string, unknown>) => {
      (options.callback as (token: string) => void)('verified-token');
      return 'widget-1';
    });
    window.turnstile = { render, remove, reset } as typeof window.turnstile;

    const wrapper = mount(TurnstileWidget, {
      props: { siteKey: 'public-site-key', resetKey: 0 },
    });
    await flushPromises();

    expect(render).toHaveBeenCalledOnce();
    expect(render.mock.calls[0]?.[1]).toMatchObject({
      sitekey: 'public-site-key',
      action: 'generate',
    });
    expect(wrapper.emitted('token')?.[0]).toEqual(['verified-token']);
    expect(wrapper.text()).toContain('安全验证已完成');

    await wrapper.setProps({ resetKey: 1 });
    expect(reset).toHaveBeenCalledWith('widget-1');
    wrapper.unmount();
    expect(remove).toHaveBeenCalledWith('widget-1');
  });
});
