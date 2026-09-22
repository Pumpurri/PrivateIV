import { expect, it } from 'vitest';
import { formatRatePercent } from './format';

it('formats fractional annualized returns as percentages', () => {
  expect(formatRatePercent('0.1250')).toBe('12.50%');
  expect(formatRatePercent('-0.0250')).toBe('-2.50%');
  expect(formatRatePercent(null)).toBe('—');
});
