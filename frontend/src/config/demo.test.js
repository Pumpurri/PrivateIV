import { describe, expect, it } from 'vitest';
import { isDemoPaused } from './demo';

describe('demo availability', () => {
  it('keeps production paused unless explicitly re-enabled', () => {
    expect(isDemoPaused({ PROD: true })).toBe(true);
    expect(isDemoPaused({ PROD: true, VITE_DEMO_PAUSED: 'true' })).toBe(true);
    expect(isDemoPaused({ PROD: true, VITE_DEMO_PAUSED: 'false' })).toBe(false);
  });

  it('allows local development', () => {
    expect(isDemoPaused({ PROD: false })).toBe(false);
  });
});
