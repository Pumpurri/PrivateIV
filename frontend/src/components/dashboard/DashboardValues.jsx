import { hasValue, money, percent } from './dashboardFormat';

export const ChangePill = ({ label, portfolio, amountKey, percentKey, mode, currency }) => {
  const source = portfolio || {};
  const value = mode === 'percent' ? source[percentKey] : source[amountKey];
  const isPositive = hasValue(value) ? Number(value) >= 0 : null;
  const formatted = mode === 'percent'
    ? percent(Math.abs(value))
    : money(Math.abs(value), currency);

  return (
    <span className="badge">
      <span className="muted">{label}</span>
      <span className={isPositive === null ? '' : isPositive ? 'up' : 'down'} style={{ fontWeight: 600 }}>
        {isPositive === null ? '' : isPositive ? '+' : '−'}
        {hasValue(value) ? formatted : '-'}
      </span>
    </span>
  );
};

export const MoneyValue = ({ portfolio, field, currency, style }) => (
  <span style={style}>{money(portfolio?.[field], currency)}</span>
);

export const SignedMoneyValue = ({ portfolio, field, currency }) => {
  const value = portfolio?.[field];
  const colorClass = hasValue(value) ? (Number(value) >= 0 ? 'up' : 'down') : '';
  return <span className={colorClass}>{money(value, currency)}</span>;
};
