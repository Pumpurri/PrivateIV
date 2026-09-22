export const formatCurrency = (value) => {
  const num = Number(value ?? 0);
  return `S/. ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatPercent = (value) => {
  const num = Number(value ?? 0);
  return `${num.toFixed(2)}%`;
};

// Portfolio TWR is stored as a fractional rate (0.05 means 5%).
export const formatRatePercent = (value) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(2)}%`;
};

export const formatNumber = (value, decimals = 2) => {
  const num = Number(value ?? 0);
  return num.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};
