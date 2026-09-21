/** Formatting helpers. Every one returns a dash for an absent value rather
 *  than inventing a zero -- an unmeasured metric must not look like a result. */

export const DASH = '—';

export function ms(value: number | null | undefined): string {
  if (value == null) return DASH;
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(2)} s`;
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value == null) return DASH;
  return `${(value * 100).toFixed(digits)}%`;
}

export function decimal(value: number | null | undefined, digits = 3): string {
  if (value == null) return DASH;
  return value.toFixed(digits);
}

export function usd(value: number | null | undefined): string {
  if (value == null) return DASH;
  return `$${value.toFixed(4)}`;
}

export function timestamp(value: string | null | undefined): string {
  if (!value) return DASH;
  return new Date(value).toLocaleString();
}
