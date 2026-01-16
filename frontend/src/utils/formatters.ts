/**
 * Utility functions for formatting numbers and values in the deck
 * NOW USES UNIFIED FORMATTER - matches backend formatting
 */

import { DeckFormatter } from '@/lib/formatters';

/**
 * Format large numbers with appropriate suffixes (K, M, B, T)
 * Uses unified $5M format (no decimals for whole numbers)
 */
export function formatNumber(value: any): string {
  // Handle null/undefined/empty - return intelligent defaults
  if (value === null || value === undefined || value === '') {
    return '$0';  // Return $0 instead of N/A for monetary values
  }

  // If already a string with formatting, return it
  if (typeof value === 'string' && (value.includes('$') || value.includes('%') || value === 'N/A')) {
    return value;
  }

  // Convert to number
  const num = typeof value === 'number' ? value : parseFloat(value);
  
  // Check if valid number
  if (isNaN(num) || !isFinite(num)) {
    return String(value); // Return original if not a number
  }

  // Use unified formatter - $5M format
  try {
    return DeckFormatter.formatCurrency(num);
  } catch (e) {
    console.error('DeckFormatter error:', e);
    return String(value); // Fallback
  }
}

/**
 * Format percentage values
 * Uses unified percentage formatter
 */
export function formatPercentage(value: any): string {
  if (value === null || value === undefined || value === '') {
    return '0%';  // Return 0% instead of N/A for percentages
  }

  const num = typeof value === 'number' ? value : parseFloat(value);
  
  if (isNaN(num)) {
    return String(value);
  }

  // Use unified formatter
  return DeckFormatter.formatPercentage(num);
}

/**
 * Format metric values based on the key name
 */
export function formatMetricValue(key: string, value: any): string {
  // Handle objects by converting to string or extracting value
  if (typeof value === 'object' && value !== null) {
    if (value.value !== undefined) {
      value = value.value;
    } else if (value.amount !== undefined) {
      value = value.amount;
    } else if (typeof value.toString === 'function' && value.toString() !== '[object Object]') {
      return value.toString();
    } else {
      // Try to extract first numeric value from object
      const firstNumericValue = Object.values(value).find(v => typeof v === 'number');
      if (firstNumericValue !== undefined) {
        value = firstNumericValue;
      } else {
        return '$0';  // Return $0 instead of N/A for objects without values
      }
    }
  }

  const lowerKey = key.toLowerCase();

  // Percentage metrics
  if (lowerKey.includes('rate') || 
      lowerKey.includes('margin') || 
      lowerKey.includes('growth') ||
      lowerKey.includes('irr') ||
      lowerKey.includes('ownership') ||
      lowerKey.includes('dilution') ||
      lowerKey.includes('stake')) {
    return formatPercentage(value);
  }

  // Currency metrics
  if (lowerKey.includes('revenue') ||
      lowerKey.includes('valuation') ||
      lowerKey.includes('funding') ||
      lowerKey.includes('check') ||
      lowerKey.includes('tam') ||
      lowerKey.includes('sam') ||
      lowerKey.includes('som') ||
      lowerKey.includes('arr') ||
      lowerKey.includes('burn') ||
      lowerKey.includes('proceeds') ||
      lowerKey.includes('exit')) {
    return formatNumber(value);
  }

  // Multiple metrics - use unified formatter
  if (lowerKey.includes('multiple') || lowerKey.includes('moic')) {
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (!isNaN(num)) {
      return DeckFormatter.formatMultiple(num);
    }
  }

  // Team size / employee count
  if (lowerKey.includes('team') || lowerKey.includes('employee')) {
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (!isNaN(num)) {
      return num.toLocaleString();
    }
  }

  // Year metrics
  if (lowerKey.includes('year') || lowerKey.includes('timeline')) {
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (!isNaN(num)) {
      return `${num.toFixed(1)} years`;
    }
  }

  // Default: return as string
  return String(value);
}

/**
 * Format currency in compact form (e.g., $1.2M)
 */
export function formatCurrencyCompact(value: any): string {
  return formatNumber(value);
}

/**
 * Safe chart data formatting
 */
export function formatChartData(data: any): any {
  if (!data) return null;

  // Handle datasets format
  if (data.datasets && Array.isArray(data.datasets)) {
    return {
      ...data,
      datasets: data.datasets.map((dataset: any) => ({
        ...dataset,
        data: dataset.data?.map((v: any) => {
          const num = typeof v === 'number' ? v : parseFloat(v);
          return isNaN(num) ? 0 : num;
        })
      }))
    };
  }

  // Handle array format
  if (Array.isArray(data)) {
    return data.map((item: any) => {
      const processed: any = { ...item };
      Object.keys(processed).forEach(key => {
        if (key !== 'name' && key !== 'label' && typeof processed[key] !== 'number') {
          const num = parseFloat(processed[key]);
          if (!isNaN(num)) {
            processed[key] = num;
          }
        }
      });
      return processed;
    });
  }

  return data;
}