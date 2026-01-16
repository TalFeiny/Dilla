/**
 * Unified formatting utilities for deck display
 * Ensures consistent number formatting across web and PDF outputs
 */

export class DeckFormatter {
  /**
   * Format currency values - $5M format (no decimals for whole numbers)
   * @example formatCurrency(5000000) => "$5M"
   * @example formatCurrency(5500000) => "$6M" (rounds)
   * @example formatCurrency(500000) => "$500K"
   */
  static formatCurrency(value: number | null | undefined): string {
    // Defensive: handle all edge cases
    if (value === null || value === undefined) {
      return '$0';
    }
    
    // Convert to number if string
    if (typeof value === 'string') {
      value = parseFloat(value);
    }
    
    // Handle NaN or invalid
    if (isNaN(value) || !isFinite(value)) {
      return '$0';
    }
    
    if (value === 0) {
      return '$0';
    }

    const millions = value / 1_000_000;

    if (millions >= 1000) {
      // Billions
      const billions = millions / 1000;
      if (billions >= 10) {
        return `$${billions.toFixed(0)}B`;
      } else {
        return `$${billions.toFixed(1)}B`;
      }
    } else if (millions >= 10) {
      // Millions >= $10M - no decimal
      return `$${millions.toFixed(0)}M`;
    } else if (millions >= 1) {
      // Millions $1M-$10M - no decimal for whole numbers
      return `$${millions.toFixed(0)}M`;
    } else if (millions >= 0.01) {
      // Hundreds of thousands - show as decimal M or K
      const thousands = value / 1000;
      if (thousands >= 100) {
        return `$${millions.toFixed(1)}M`;
      }
      return `$${thousands.toFixed(0)}K`;
    } else {
      // Very small values
      return `$${value.toFixed(0)}`;
    }
  }

  /**
   * Format percentages
   * @example formatPercentage(0.156) => "15.6%"
   * @example formatPercentage(15.6, 0) => "16%"
   */
  static formatPercentage(
    value: number | null | undefined,
    decimals: number = 1
  ): string {
    if (value === null || value === undefined) {
      return 'N/A';
    }

    // Handle both decimal (0.156) and percentage (15.6) inputs
    const percentage = Math.abs(value) <= 1 ? value * 100 : value;

    return `${percentage.toFixed(decimals)}%`;
  }

  /**
   * Format multiples
   * @example formatMultiple(12.5) => "12.5x"
   * @example formatMultiple(2.0, 0) => "2x"
   */
  static formatMultiple(
    value: number | null | undefined,
    decimals: number = 1
  ): string {
    if (value === null || value === undefined) {
      return 'N/A';
    }
    return `${value.toFixed(decimals)}x`;
  }

  /**
   * Format axis values based on max scale (for chart Y-axis ticks)
   */
  static formatAxisValue(value: number, maxValue: number): string {
    if (maxValue >= 1_000_000) {
      return this.formatCurrency(value);
    } else if (maxValue >= 1000) {
      return `$${(value / 1000).toFixed(0)}K`;
    } else {
      return `$${value.toFixed(0)}`;
    }
  }

  /**
   * Get Y-axis formatter function for Chart.js
   */
  static getYAxisFormatter(maxValue: number): (value: number) => string {
    return (value: number) => this.formatAxisValue(value, maxValue);
  }

  /**
   * Format large numbers with K/M/B suffix (non-currency)
   * @example formatNumber(5000000) => "5M"
   */
  static formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined || value === 0) {
      return '0';
    }

    const abs = Math.abs(value);
    const sign = value < 0 ? '-' : '';

    if (abs >= 1_000_000_000) {
      return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`;
    } else if (abs >= 1_000_000) {
      return `${sign}${(abs / 1_000_000).toFixed(0)}M`;
    } else if (abs >= 1_000) {
      return `${sign}${(abs / 1_000).toFixed(0)}K`;
    } else {
      return `${sign}${abs.toFixed(0)}`;
    }
  }
}
