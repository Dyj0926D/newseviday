// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';

import { routes } from './router';

describe('public routes', () => {
  it('keeps the eight PRD routes in the engineering skeleton', () => {
    expect(routes.map((route) => route.path)).toEqual([
      '/',
      '/article/:id',
      '/ask',
      '/brief',
      '/profile',
      '/eval',
      '/status',
      '/product',
    ]);
  });
});
