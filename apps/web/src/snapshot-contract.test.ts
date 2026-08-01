import { assertContentSnapshot } from '@newseviday/contracts';
import { describe, expect, it } from 'vitest';

import snapshot from '../public/data/current.json';

describe('published static snapshot', () => {
  it('conforms to the shared runtime contract', () => {
    expect(() => assertContentSnapshot(snapshot)).not.toThrow();
  });
});
