import { formatCurrency } from '../../utils/format';

export const DISPLAY_CURRENCY_NATIVE = 'NATIVE';
export const PAGE_SIZE_ALL = 'ALL';
export const PAGE_SIZE_OPTIONS = [25, 50, 100, PAGE_SIZE_ALL];

export const toNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
};

export const startOfMonth = (dateObj) => new Date(dateObj.getFullYear(), dateObj.getMonth(), 1);

export const subtractMonths = (dateObj, count) => {
  const base = startOfMonth(dateObj);
  base.setMonth(base.getMonth() - count);
  return base;
};

export const parseDisplayDate = (iso) => {
  if (!iso) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [year, month, day] = iso.split('-').map(Number);
    return new Date(year, month - 1, day);
  }
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export const formatMoney = (value, currency = 'PEN') => {
  if ((currency || 'PEN').toUpperCase() === 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value ?? 0));
  }
  return formatCurrency(value);
};

const NICE_TICK_FACTORS = [1, 2, 2.5, 5, 10];

const getNiceStep = (rawStep) => {
  if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
  const exponent = Math.floor(Math.log10(rawStep));
  const magnitude = 10 ** exponent;
  const fraction = rawStep / magnitude;
  const chosenFactor = NICE_TICK_FACTORS.find((candidate) => fraction <= candidate)
    || NICE_TICK_FACTORS[NICE_TICK_FACTORS.length - 1];
  return chosenFactor * magnitude;
};

export const buildNiceTicks = (minValue, maxValue, targetIntervals = 4) => {
  let min = Number.isFinite(minValue) ? minValue : 0;
  let max = Number.isFinite(maxValue) ? maxValue : 0;

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.05, 1);
    min -= pad;
    max += pad;
  }

  const range = Math.max(max - min, 1e-9);
  let step = getNiceStep(range / targetIntervals);
  let tickMin = Math.floor(min / step) * step;
  let tickMax = Math.ceil(max / step) * step;

  while (((tickMax - tickMin) / step) > targetIntervals) {
    const nextStep = getNiceStep(step * 1.5);
    step = nextStep <= step ? step * 2 : nextStep;
    tickMin = Math.floor(min / step) * step;
    tickMax = Math.ceil(max / step) * step;
  }

  const ticks = [];
  for (let value = tickMin; value <= tickMax + (step / 10); value += step) {
    ticks.push(Number(value.toFixed(6)));
  }

  return {
    ticks,
    min: ticks[0],
    max: ticks[ticks.length - 1],
    step,
  };
};

export const valueColor = (value) => {
  if (value === 0) return 'var(--text)';
  return value > 0 ? 'var(--accent)' : 'var(--danger)';
};
