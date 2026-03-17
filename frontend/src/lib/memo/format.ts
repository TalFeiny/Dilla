/**
 * Shared formatting utilities for memo sections.
 *
 * All currency / percentage / metric formatting lives here.
 * Sections import from this file instead of defining local copies.
 */

/** Format a number as compact currency: $1.2B, $3.4M, $50K, $123 */
export function fmtCurrency(v: number): string {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

/** Format a decimal as percentage: 0.1234 → "12.34%" */
export function fmtPct(v: number, decimals: number = 2): string {
  return `${(v * 100).toFixed(decimals)}%`;
}

/** Format a number as a multiple: 1.5 → "1.50x" */
export function fmtMultiple(v: number, decimals: number = 2): string {
  return `${v.toFixed(decimals)}x`;
}

/** Format a number as months: 18.3 → "18 mo" */
export function fmtMonths(v: number): string {
  return `${v.toFixed(0)} mo`;
}

export type MetricUnit = 'currency' | 'percentage' | 'months' | 'ratio' | 'number';

/** Format a metric value based on its unit type */
export function formatMetricValue(v: number, unit: MetricUnit): string {
  switch (unit) {
    case 'currency': return fmtCurrency(v);
    case 'percentage': return fmtPct(v, 1);
    case 'months': return fmtMonths(v);
    case 'ratio': return fmtMultiple(v);
    default: return v.toLocaleString();
  }
}
