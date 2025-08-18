/**
 * Live Currency Service with Real-time Exchange Rates
 * Fast, cached, and reliable multi-currency support
 */

import { Redis } from '@upstash/redis';

// Initialize Redis for fast caching (if available)
let redis: Redis | null = null;
try {
  if (process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN) {
    redis = new Redis({
      url: process.env.UPSTASH_REDIS_REST_URL,
      token: process.env.UPSTASH_REDIS_REST_TOKEN
    });
  }
} catch (error) {
  console.log('Redis not available, using in-memory cache');
}

export interface ExchangeRate {
  from: string;
  to: string;
  rate: number;
  timestamp: Date;
  source: 'live' | 'cached' | 'fallback';
}

export class LiveCurrencyService {
  private static instance: LiveCurrencyService;
  private memoryCache: Map<string, { rate: number; timestamp: Date }> = new Map();
  private cacheDuration = 900000; // 15 minutes for live rates
  private providers: CurrencyProvider[] = [];
  
  private constructor() {
    this.initializeProviders();
  }

  static getInstance(): LiveCurrencyService {
    if (!LiveCurrencyService.instance) {
      LiveCurrencyService.instance = new LiveCurrencyService();
    }
    return LiveCurrencyService.instance;
  }

  private initializeProviders() {
    // Multiple providers for redundancy and speed
    this.providers = [
      new ECBProvider(), // European Central Bank (free, reliable)
      new ExchangeRateAPIProvider(), // exchangerate-api.com (free tier)
      new CurrencyAPIProvider(), // currencyapi.com (free tier)
      new FallbackProvider() // Static rates as last resort
    ];
  }

  /**
   * Get exchange rate with caching and fallback
   */
  async getRate(from: string, to: string): Promise<ExchangeRate> {
    const cacheKey = `${from}_${to}`;
    
    // 1. Check Redis cache (fastest)
    if (redis) {
      try {
        const cached = await redis.get(cacheKey);
        if (cached && typeof cached === 'object' && 'rate' in cached) {
          const cachedData = cached as any;
          if (Date.now() - new Date(cachedData.timestamp).getTime() < this.cacheDuration) {
            return {
              from,
              to,
              rate: cachedData.rate,
              timestamp: new Date(cachedData.timestamp),
              source: 'cached'
            };
          }
        }
      } catch (error) {
        // Redis error, continue to memory cache
      }
    }

    // 2. Check memory cache
    const memoryCached = this.memoryCache.get(cacheKey);
    if (memoryCached && Date.now() - memoryCached.timestamp.getTime() < this.cacheDuration) {
      return {
        from,
        to,
        rate: memoryCached.rate,
        timestamp: memoryCached.timestamp,
        source: 'cached'
      };
    }

    // 3. Fetch from providers (parallel for speed)
    const rate = await this.fetchFromProviders(from, to);
    
    // 4. Cache the result
    await this.cacheRate(cacheKey, rate);
    
    return rate;
  }

  /**
   * Fetch from multiple providers in parallel
   */
  private async fetchFromProviders(from: string, to: string): Promise<ExchangeRate> {
    // Try all providers in parallel
    const promises = this.providers.map(provider => 
      provider.getRate(from, to).catch(() => null)
    );
    
    const results = await Promise.race([
      Promise.all(promises),
      new Promise<null[]>(resolve => setTimeout(() => resolve([null]), 2000)) // 2s timeout
    ]);
    
    // Find first successful result
    for (const result of results) {
      if (result) {
        return result;
      }
    }
    
    // All failed, use fallback
    return new FallbackProvider().getRate(from, to);
  }

  /**
   * Cache rate in both Redis and memory
   */
  private async cacheRate(key: string, rate: ExchangeRate) {
    // Memory cache
    this.memoryCache.set(key, {
      rate: rate.rate,
      timestamp: rate.timestamp
    });
    
    // Redis cache
    if (redis) {
      try {
        await redis.setex(key, Math.floor(this.cacheDuration / 1000), {
          rate: rate.rate,
          timestamp: rate.timestamp.toISOString()
        });
      } catch (error) {
        // Redis error, continue without caching
      }
    }
  }

  /**
   * Batch convert multiple amounts efficiently
   */
  async batchConvert(conversions: Array<{
    amount: number;
    from: string;
    to: string;
  }>): Promise<number[]> {
    // Group by currency pair to minimize API calls
    const rateMap = new Map<string, Promise<ExchangeRate>>();
    
    for (const conv of conversions) {
      const key = `${conv.from}_${conv.to}`;
      if (!rateMap.has(key)) {
        rateMap.set(key, this.getRate(conv.from, conv.to));
      }
    }
    
    // Fetch all unique rates in parallel
    const rates = new Map<string, ExchangeRate>();
    for (const [key, promise] of rateMap) {
      rates.set(key, await promise);
    }
    
    // Apply rates to amounts
    return conversions.map(conv => {
      const key = `${conv.from}_${conv.to}`;
      const rate = rates.get(key)!;
      return conv.amount * rate.rate;
    });
  }

  /**
   * Get all available currencies
   */
  async getAvailableCurrencies(): Promise<string[]> {
    // Common currencies supported by most providers
    return [
      'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD',
      'CNY', 'INR', 'KRW', 'SGD', 'HKD', 'NOK', 'SEK', 'DKK',
      'PLN', 'THB', 'IDR', 'HUF', 'CZK', 'ILS', 'CLP', 'PHP',
      'AED', 'COP', 'SAR', 'MYR', 'RON', 'ZAR', 'BRL', 'MXN'
    ];
  }
}

/**
 * Currency Provider Interface
 */
interface CurrencyProvider {
  getRate(from: string, to: string): Promise<ExchangeRate>;
}

/**
 * European Central Bank Provider (Free, reliable)
 */
class ECBProvider implements CurrencyProvider {
  async getRate(from: string, to: string): Promise<ExchangeRate> {
    try {
      const response = await fetch(
        'https://api.frankfurter.app/latest?from=' + from + '&to=' + to,
        { signal: AbortSignal.timeout(1500) } // 1.5s timeout
      );
      
      if (response.ok) {
        const data = await response.json();
        return {
          from,
          to,
          rate: data.rates[to],
          timestamp: new Date(),
          source: 'live'
        };
      }
    } catch (error) {
      // Provider failed
    }
    throw new Error('ECB provider failed');
  }
}

/**
 * ExchangeRate-API Provider
 */
class ExchangeRateAPIProvider implements CurrencyProvider {
  async getRate(from: string, to: string): Promise<ExchangeRate> {
    try {
      const response = await fetch(
        `https://api.exchangerate-api.com/v4/latest/${from}`,
        { signal: AbortSignal.timeout(1500) }
      );
      
      if (response.ok) {
        const data = await response.json();
        return {
          from,
          to,
          rate: data.rates[to] || 1,
          timestamp: new Date(),
          source: 'live'
        };
      }
    } catch (error) {
      // Provider failed
    }
    throw new Error('ExchangeRate-API provider failed');
  }
}

/**
 * CurrencyAPI Provider
 */
class CurrencyAPIProvider implements CurrencyProvider {
  async getRate(from: string, to: string): Promise<ExchangeRate> {
    if (!process.env.CURRENCY_API_KEY) {
      throw new Error('No API key');
    }
    
    try {
      const response = await fetch(
        `https://api.currencyapi.com/v3/latest?apikey=${process.env.CURRENCY_API_KEY}&base_currency=${from}&currencies=${to}`,
        { signal: AbortSignal.timeout(1500) }
      );
      
      if (response.ok) {
        const data = await response.json();
        return {
          from,
          to,
          rate: data.data[to].value,
          timestamp: new Date(),
          source: 'live'
        };
      }
    } catch (error) {
      // Provider failed
    }
    throw new Error('CurrencyAPI provider failed');
  }
}

/**
 * Fallback Provider with static rates
 */
class FallbackProvider implements CurrencyProvider {
  private rates: Map<string, number> = new Map([
    ['USD_EUR', 0.92],
    ['USD_GBP', 0.79],
    ['USD_JPY', 148.5],
    ['USD_CHF', 0.88],
    ['USD_CAD', 1.36],
    ['USD_AUD', 1.52],
    ['USD_CNY', 7.24],
    ['USD_INR', 83.2],
    ['USD_KRW', 1298],
    ['USD_SGD', 1.34],
    ['USD_HKD', 7.82],
    ['USD_BRL', 5.05],
    ['USD_MXN', 17.2],
    ['USD_ZAR', 18.4],
    ['USD_SEK', 10.9],
    ['USD_NOK', 10.8],
    ['USD_DKK', 6.89],
    ['USD_PLN', 4.02],
    ['USD_ILS', 3.68],
    ['USD_AED', 3.67],
    ['EUR_USD', 1.087],
    ['GBP_USD', 1.266],
    ['JPY_USD', 0.00673],
    ['CHF_USD', 1.136],
    ['CAD_USD', 0.735],
    ['AUD_USD', 0.658],
    ['CNY_USD', 0.138],
    ['INR_USD', 0.012],
    ['KRW_USD', 0.00077],
    ['SGD_USD', 0.746],
    ['HKD_USD', 0.128],
    ['BRL_USD', 0.198],
    ['MXN_USD', 0.058],
    ['ZAR_USD', 0.054],
    ['SEK_USD', 0.092],
    ['NOK_USD', 0.093],
    ['DKK_USD', 0.145],
    ['PLN_USD', 0.249],
    ['ILS_USD', 0.272],
    ['AED_USD', 0.272]
  ]);

  async getRate(from: string, to: string): Promise<ExchangeRate> {
    if (from === to) {
      return { from, to, rate: 1, timestamp: new Date(), source: 'fallback' };
    }
    
    // Try direct rate
    const directKey = `${from}_${to}`;
    if (this.rates.has(directKey)) {
      return {
        from,
        to,
        rate: this.rates.get(directKey)!,
        timestamp: new Date(),
        source: 'fallback'
      };
    }
    
    // Try inverse rate
    const inverseKey = `${to}_${from}`;
    if (this.rates.has(inverseKey)) {
      return {
        from,
        to,
        rate: 1 / this.rates.get(inverseKey)!,
        timestamp: new Date(),
        source: 'fallback'
      };
    }
    
    // Try via USD
    const fromUSD = this.rates.get(`USD_${from}`) || 1;
    const toUSD = this.rates.get(`USD_${to}`) || 1;
    
    return {
      from,
      to,
      rate: toUSD / fromUSD,
      timestamp: new Date(),
      source: 'fallback'
    };
  }
}

// Export singleton
export const liveCurrencyService = LiveCurrencyService.getInstance();

// React hook for live currency
export function useLiveCurrency(from: string, to: string) {
  const [rate, setRate] = React.useState<ExchangeRate | null>(null);
  const [loading, setLoading] = React.useState(true);
  
  React.useEffect(() => {
    let cancelled = false;
    
    liveCurrencyService.getRate(from, to).then(r => {
      if (!cancelled) {
        setRate(r);
        setLoading(false);
      }
    });
    
    return () => { cancelled = true; };
  }, [from, to]);
  
  return { rate, loading };
}