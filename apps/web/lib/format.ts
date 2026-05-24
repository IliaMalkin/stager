const SYMBOLS: Record<string, string> = { RUB: '₽', USD: '$', EUR: '€' };

export function formatAmount(minor: number, currency = 'RUB'): string {
  const sign = minor < 0 ? '-' : '';
  const abs = Math.abs(minor);
  const units = Math.floor(abs / 100);
  const cents = abs % 100;
  const unitsStr = units.toLocaleString('ru-RU').replace(/,/g, ' ');
  const symbol = SYMBOLS[currency] || currency;
  return `${sign}${unitsStr}.${cents.toString().padStart(2, '0')} ${symbol}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}
