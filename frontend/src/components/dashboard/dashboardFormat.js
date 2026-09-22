export const NUMBER_FORMAT = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const CURRENCY_PREFIX = { PEN: 'S/ ', USD: '$ ' };

export const money = (value, currency = 'PEN') => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${CURRENCY_PREFIX[currency] ?? ''}${NUMBER_FORMAT.format(Number(value))}`;
};

export const percent = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return `${Number(value).toFixed(2)}%`;
};

export const hasValue = (value) => (
  value !== null && value !== undefined && !Number.isNaN(Number(value))
);

export const readStoredCurrencyMode = () => {
  try {
    const raw = localStorage.getItem('dashboardCurrencyMode');
    if (raw === 'PEN' || raw === 'USD') return raw;
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
  return 'PEN';
};

export const normalizeText = (value) => (value || '')
  .toString()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/\s+/g, ' ')
  .trim();

export const formatTimeHHMM = (value) => {
  if (!value) return '--:--';
  const date = new Date(value);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
};

export const formatDateDDMM = (value) => {
  if (!value) return '';
  const date = new Date(value);
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  return `${day}/${month}`;
};

export const isMarketOpen = (date, timeZone, openHour, openMinute, closeHour, closeMinute) => {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const getPart = (type) => parts.find((part) => part.type === type)?.value || '';
  const weekday = getPart('weekday');
  if (weekday === 'Sat' || weekday === 'Sun') return false;

  const hour = Number(getPart('hour'));
  const minute = Number(getPart('minute'));
  if (Number.isNaN(hour) || Number.isNaN(minute)) return false;

  const currentMinutes = hour * 60 + minute;
  const openMinutes = openHour * 60 + openMinute;
  const closeMinutes = closeHour * 60 + closeMinute;
  return currentMinutes >= openMinutes && currentMinutes < closeMinutes;
};
