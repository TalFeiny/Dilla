/**
 * Safe formatting utilities to prevent NaNK values
 */

/**
 * Safely format a number as currency with proper null/NaN checks
 */
export const formatCurrency = (value: number | null | undefined, options?: {
  currency?: string;
  minimumFractionDigits?: number;
  maximumFractionDigits?: number;
}): string => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '-';
  }

  const defaultOptions = {
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
    ...options
  };

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: defaultOptions.currency,
    minimumFractionDigits: defaultOptions.minimumFractionDigits,
    maximumFractionDigits: defaultOptions.maximumFractionDigits,
  }).format(value);
};

/**
 * Safely format a number as a percentage
 */
export const formatPercentage = (value: number | null | undefined, decimals: number = 1): string => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '-';
  }

  return `${(value * 100).toFixed(decimals)}%`;
};

/**
 * Safely format a number with thousands separators
 */
export const formatNumber = (value: number | null | undefined): string => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '-';
  }

  return value.toLocaleString();
};

/**
 * Safely format currency in K/M format (e.g., $1.2M, $500K)
 */
export const formatCurrencyCompact = (value: number | null | undefined): string => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '-';
  }

  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  } else if (value >= 1000) {
    return `$${(value / 1000).toFixed(0)}K`;
  } else {
    return `$${value.toFixed(0)}`;
  }
};

/**
 * Safely format a number with a specific number of decimal places
 */
export const formatDecimal = (value: number | null | undefined, decimals: number = 2): string => {
  if (value === null || value === undefined || typeof value !== 'number' || isNaN(value)) {
    return '-';
  }

  return value.toFixed(decimals);
}; 