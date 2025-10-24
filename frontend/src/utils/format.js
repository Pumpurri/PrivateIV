export const formatCurrency = (value) => {
  const num = Number(value ?? 0);
  return `S/. ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatPercent = (value) => {
  const num = Number(value ?? 0);
  return `${num.toFixed(2)}%`;
};

export const formatNumber = (value, decimals = 2) => {
  const num = Number(value ?? 0);
  return num.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

