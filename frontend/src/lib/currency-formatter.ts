/**
 * Multi-Currency Formatting System with Live Exchange Rates
 * Provides intelligent number formatting with proper separators
 */

export interface CurrencyConfig {
  code: string;
  symbol: string;
  symbolPosition: 'before' | 'after';
  thousandSeparator: string;
  decimalSeparator: string;
  decimals: number;
  format: string; // e.g., "symbol value" or "value symbol"
}

export class CurrencyFormatter {
  private static instance: CurrencyFormatter;
  private exchangeRates: Map<string, number> = new Map();
  private lastFetchTime: Date | null = null;
  private baseCurrency: string = 'USD';
  private cacheDuration: number = 3600000; // 1 hour in ms

  // Currency configurations
  private currencies: Map<string, CurrencyConfig> = new Map([
    ['USD', {
      code: 'USD',
      symbol: '$',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['EUR', {
      code: 'EUR',
      symbol: '€',
      symbolPosition: 'before',
      thousandSeparator: '.',
      decimalSeparator: ',',
      decimals: 2,
      format: 'symbol value'
    }],
    ['GBP', {
      code: 'GBP',
      symbol: '£',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['JPY', {
      code: 'JPY',
      symbol: '¥',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 0,
      format: 'symbol value'
    }],
    ['CNY', {
      code: 'CNY',
      symbol: '¥',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['INR', {
      code: 'INR',
      symbol: '₹',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['CHF', {
      code: 'CHF',
      symbol: 'CHF',
      symbolPosition: 'after',
      thousandSeparator: "'",
      decimalSeparator: '.',
      decimals: 2,
      format: 'value symbol'
    }],
    ['CAD', {
      code: 'CAD',
      symbol: 'C$',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['AUD', {
      code: 'AUD',
      symbol: 'A$',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['SGD', {
      code: 'SGD',
      symbol: 'S$',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['HKD', {
      code: 'HKD',
      symbol: 'HK$',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['SEK', {
      code: 'SEK',
      symbol: 'kr',
      symbolPosition: 'after',
      thousandSeparator: ' ',
      decimalSeparator: ',',
      decimals: 2,
      format: 'value symbol'
    }],
    ['NOK', {
      code: 'NOK',
      symbol: 'kr',
      symbolPosition: 'after',
      thousandSeparator: ' ',
      decimalSeparator: ',',
      decimals: 2,
      format: 'value symbol'
    }],
    ['DKK', {
      code: 'DKK',
      symbol: 'kr',
      symbolPosition: 'after',
      thousandSeparator: '.',
      decimalSeparator: ',',
      decimals: 2,
      format: 'value symbol'
    }],
    ['PLN', {
      code: 'PLN',
      symbol: 'zł',
      symbolPosition: 'after',
      thousandSeparator: ' ',
      decimalSeparator: ',',
      decimals: 2,
      format: 'value symbol'
    }],
    ['KRW', {
      code: 'KRW',
      symbol: '₩',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 0,
      format: 'symbol value'
    }],
    ['BRL', {
      code: 'BRL',
      symbol: 'R$',
      symbolPosition: 'before',
      thousandSeparator: '.',
      decimalSeparator: ',',
      decimals: 2,
      format: 'symbol value'
    }],
    ['ZAR', {
      code: 'ZAR',
      symbol: 'R',
      symbolPosition: 'before',
      thousandSeparator: ' ',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['ILS', {
      code: 'ILS',
      symbol: '₪',
      symbolPosition: 'before',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'symbol value'
    }],
    ['AED', {
      code: 'AED',
      symbol: 'د.إ',
      symbolPosition: 'after',
      thousandSeparator: ',',
      decimalSeparator: '.',
      decimals: 2,
      format: 'value symbol'
    }]
  ]);

  private constructor() {}

  static getInstance(): CurrencyFormatter {
    if (!CurrencyFormatter.instance) {
      CurrencyFormatter.instance = new CurrencyFormatter();
    }
    return CurrencyFormatter.instance;
  }

  /**
   * Fetch live exchange rates
   */
  async fetchExchangeRates(): Promise<void> {
    // Check cache
    if (this.lastFetchTime && 
        Date.now() - this.lastFetchTime.getTime() < this.cacheDuration) {
      return;
    }

    try {
      // Using exchangerate-api.com (free tier available)
      const response = await fetch(
        `https://api.exchangerate-api.com/v4/latest/${this.baseCurrency}`
      );
      
      if (response.ok) {
        const data = await response.json();
        this.exchangeRates.clear();
        
        for (const [currency, rate] of Object.entries(data.rates)) {
          this.exchangeRates.set(currency, rate as number);
        }
        
        this.lastFetchTime = new Date();
      }
    } catch (error) {
      console.error('Failed to fetch exchange rates:', error);
      // Fall back to static rates
      this.useStaticRates();
    }
  }

  /**
   * Use static exchange rates as fallback
   */
  private useStaticRates() {
    // Approximate rates as of 2025
    this.exchangeRates.set('USD', 1);
    this.exchangeRates.set('EUR', 0.92);
    this.exchangeRates.set('GBP', 0.79);
    this.exchangeRates.set('JPY', 148.5);
    this.exchangeRates.set('CNY', 7.24);
    this.exchangeRates.set('INR', 83.2);
    this.exchangeRates.set('CHF', 0.88);
    this.exchangeRates.set('CAD', 1.36);
    this.exchangeRates.set('AUD', 1.52);
    this.exchangeRates.set('SGD', 1.34);
    this.exchangeRates.set('HKD', 7.82);
    this.exchangeRates.set('SEK', 10.9);
    this.exchangeRates.set('NOK', 10.8);
    this.exchangeRates.set('DKK', 6.89);
    this.exchangeRates.set('PLN', 4.02);
    this.exchangeRates.set('KRW', 1298);
    this.exchangeRates.set('BRL', 5.05);
    this.exchangeRates.set('ZAR', 18.4);
    this.exchangeRates.set('ILS', 3.68);
    this.exchangeRates.set('AED', 3.67);
  }

  /**
   * Format a number with proper separators
   */
  formatNumber(
    value: number,
    options: {
      currency?: string;
      decimals?: number;
      compact?: boolean;
      showCurrency?: boolean;
    } = {}
  ): string {
    const currency = options.currency || 'USD';
    const config = this.currencies.get(currency) || this.currencies.get('USD')!;
    const decimals = options.decimals ?? config.decimals;
    
    // Handle compact notation (K, M, B)
    if (options.compact) {
      return this.formatCompact(value, currency, options.showCurrency);
    }

    // Split into integer and decimal parts
    const parts = value.toFixed(decimals).split('.');
    const integerPart = parts[0];
    const decimalPart = parts[1];

    // Add thousand separators
    const formattedInteger = this.addThousandSeparators(
      integerPart,
      config.thousandSeparator
    );

    // Combine parts
    let formatted = formattedInteger;
    if (decimalPart && decimals > 0) {
      formatted += config.decimalSeparator + decimalPart;
    }

    // Add currency symbol if requested
    if (options.showCurrency !== false) {
      if (config.symbolPosition === 'before') {
        formatted = config.symbol + formatted;
      } else {
        formatted = formatted + ' ' + config.symbol;
      }
    }

    return formatted;
  }

  /**
   * Add thousand separators to a number string
   */
  private addThousandSeparators(value: string, separator: string): string {
    // Handle negative numbers
    const isNegative = value.startsWith('-');
    const absValue = isNegative ? value.slice(1) : value;
    
    // Add separators from right to left
    const result = absValue.replace(/\B(?=(\d{3})+(?!\d))/g, separator);
    
    return isNegative ? '-' + result : result;
  }

  /**
   * Format number in compact notation
   */
  formatCompact(value: number, currency: string = 'USD', showCurrency: boolean = true): string {
    const config = this.currencies.get(currency) || this.currencies.get('USD')!;
    const absValue = Math.abs(value);
    let formatted: string;
    let suffix: string;

    if (absValue >= 1e12) {
      formatted = (value / 1e12).toFixed(1);
      suffix = 'T';
    } else if (absValue >= 1e9) {
      formatted = (value / 1e9).toFixed(1);
      suffix = 'B';
    } else if (absValue >= 1e6) {
      formatted = (value / 1e6).toFixed(1);
      suffix = 'M';
    } else if (absValue >= 1e3) {
      formatted = (value / 1e3).toFixed(1);
      suffix = 'K';
    } else {
      formatted = value.toFixed(config.decimals);
      suffix = '';
    }

    // Remove unnecessary decimal zeros
    formatted = formatted.replace(/\.0$/, '');

    // Add suffix
    formatted += suffix;

    // Add currency symbol if requested
    if (showCurrency) {
      if (config.symbolPosition === 'before') {
        formatted = config.symbol + formatted;
      } else {
        formatted = formatted + ' ' + config.symbol;
      }
    }

    return formatted;
  }

  /**
   * Convert between currencies
   */
  async convert(
    amount: number,
    fromCurrency: string,
    toCurrency: string
  ): Promise<number> {
    // Fetch latest rates if needed
    await this.fetchExchangeRates();

    if (fromCurrency === toCurrency) {
      return amount;
    }

    const fromRate = this.exchangeRates.get(fromCurrency) || 1;
    const toRate = this.exchangeRates.get(toCurrency) || 1;

    // Convert to base currency (USD) first, then to target
    const inBase = amount / fromRate;
    return inBase * toRate;
  }

  /**
   * Format with conversion
   */
  async formatWithConversion(
    amount: number,
    fromCurrency: string,
    toCurrency: string,
    options: {
      showOriginal?: boolean;
      compact?: boolean;
    } = {}
  ): Promise<string> {
    const converted = await this.convert(amount, fromCurrency, toCurrency);
    const formatted = this.formatNumber(converted, {
      currency: toCurrency,
      compact: options.compact
    });

    if (options.showOriginal && fromCurrency !== toCurrency) {
      const original = this.formatNumber(amount, {
        currency: fromCurrency,
        compact: options.compact
      });
      return `${formatted} (${original})`;
    }

    return formatted;
  }

  /**
   * Parse formatted number back to numeric value
   */
  parseFormattedNumber(formatted: string, currency?: string): number {
    const config = currency ? 
      (this.currencies.get(currency) || this.currencies.get('USD')!) :
      this.currencies.get('USD')!;

    // Remove currency symbol
    let cleaned = formatted.replace(config.symbol, '').trim();

    // Handle compact notation
    const multipliers: { [key: string]: number } = {
      'K': 1e3,
      'M': 1e6,
      'B': 1e9,
      'T': 1e12
    };

    for (const [suffix, multiplier] of Object.entries(multipliers)) {
      if (cleaned.endsWith(suffix)) {
        cleaned = cleaned.slice(0, -1);
        const base = parseFloat(
          cleaned
            .replace(new RegExp(`\\${config.thousandSeparator}`, 'g'), '')
            .replace(config.decimalSeparator, '.')
        );
        return base * multiplier;
      }
    }

    // Remove thousand separators and normalize decimal separator
    cleaned = cleaned
      .replace(new RegExp(`\\${config.thousandSeparator}`, 'g'), '')
      .replace(config.decimalSeparator, '.');

    return parseFloat(cleaned) || 0;
  }

  /**
   * Get available currencies
   */
  getAvailableCurrencies(): string[] {
    return Array.from(this.currencies.keys());
  }

  /**
   * Format for Excel export
   */
  formatForExcel(value: number, currency: string = 'USD'): {
    value: number;
    format: string;
  } {
    const config = this.currencies.get(currency) || this.currencies.get('USD')!;
    
    // Excel format codes
    const excelFormats: { [key: string]: string } = {
      'USD': '$#,##0.00',
      'EUR': '€#,##0.00',
      'GBP': '£#,##0.00',
      'JPY': '¥#,##0',
      'CNY': '¥#,##0.00',
      'INR': '₹#,##0.00'
    };

    return {
      value,
      format: excelFormats[currency] || '#,##0.00'
    };
  }
}

// Export singleton instance
export const currencyFormatter = CurrencyFormatter.getInstance();

// Helper functions for common use cases
export const formatUSD = (value: number, compact: boolean = false) => 
  currencyFormatter.formatNumber(value, { currency: 'USD', compact });

export const formatEUR = (value: number, compact: boolean = false) => 
  currencyFormatter.formatNumber(value, { currency: 'EUR', compact });

export const formatGBP = (value: number, compact: boolean = false) => 
  currencyFormatter.formatNumber(value, { currency: 'GBP', compact });

export const formatCompact = (value: number, currency: string = 'USD') =>
  currencyFormatter.formatCompact(value, currency);

export const formatWithCommas = (value: number) =>
  currencyFormatter.formatNumber(value, { showCurrency: false });

// React hook for currency formatting
export function useCurrencyFormatter(defaultCurrency: string = 'USD') {
  const format = (value: number, options?: any) => 
    currencyFormatter.formatNumber(value, { ...options, currency: defaultCurrency });
  
  const formatCompact = (value: number) =>
    currencyFormatter.formatCompact(value, defaultCurrency);
  
  return { format, formatCompact };
}