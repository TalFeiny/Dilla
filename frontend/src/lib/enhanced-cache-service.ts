/**
 * Enhanced Cache Service with LRU eviction and intelligent TTL
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
  hits: number;
  lastAccess: number;
}

export class EnhancedCache {
  private static instance: EnhancedCache;
  private cache = new Map<string, CacheEntry<any>>();
  private maxSize = 1000; // Maximum cache entries
  private defaultTTL = 30 * 60 * 1000; // 30 minutes default
  
  // Different TTLs for different data types
  private ttlConfig = {
    companyData: 60 * 60 * 1000,      // 1 hour for company data
    financialData: 30 * 60 * 1000,    // 30 minutes for financial data  
    searchResults: 15 * 60 * 1000,    // 15 minutes for search results
    apiResponses: 5 * 60 * 1000,      // 5 minutes for API responses
    claudeAnalysis: 2 * 60 * 60 * 1000, // 2 hours for Claude analysis
    pwermData: 45 * 60 * 1000,        // 45 minutes for PWERM data
  };

  static getInstance(): EnhancedCache {
    if (!EnhancedCache.instance) {
      EnhancedCache.instance = new EnhancedCache();
    }
    return EnhancedCache.instance;
  }

  /**
   * Get cached data with automatic TTL check
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    
    if (!entry) {
      return null;
    }
    
    // Check if expired
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    // Update access stats
    entry.hits++;
    entry.lastAccess = Date.now();
    
    return entry.data as T;
  }

  /**
   * Set data with intelligent TTL based on data type
   */
  set<T>(key: string, data: T, dataType?: keyof typeof this.ttlConfig): void {
    // LRU eviction if cache is full
    if (this.cache.size >= this.maxSize) {
      this.evictLRU();
    }
    
    const ttl = dataType ? this.ttlConfigArray.from(aType) : this.defaultTTL;
    
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl,
      hits: 0,
      lastAccess: Date.now()
    });
  }

  /**
   * Check if key exists and is not expired
   */
  has(key: string): boolean {
    const data = this.get(key);
    return data !== null;
  }

  /**
   * Get or compute - if not in cache, compute and cache it
   */
  async getOrCompute<T>(
    key: string, 
    computeFn: () => Promise<T>,
    dataType?: keyof typeof this.ttlConfig
  ): Promise<T> {
    // Check cache first
    const cached = this.get<T>(key);
    if (cached !== null) {
      console.log(`[Cache HIT] ${key}`);
      return cached;
    }
    
    console.log(`[Cache MISS] ${key} - computing...`);
    
    // Compute the value
    const result = await computeFn();
    
    // Cache it
    this.set(key, result, dataType);
    
    return result;
  }

  /**
   * Batch get - retrieve multiple keys at once
   */
  batchGet<T>(keys: string[]): Map<string, T> {
    const results = new Map<string, T>();
    
    for (const key of keys) {
      const data = this.get<T>(key);
      if (data !== null) {
        results.set(key, data);
      }
    }
    
    return results;
  }

  /**
   * Clear expired entries
   */
  clearExpired(): number {
    let cleared = 0;
    const now = Date.now();
    
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > entry.ttl) {
        this.cache.delete(key);
        cleared++;
      }
    }
    
    return cleared;
  }

  /**
   * LRU eviction - remove least recently used items
   */
  private evictLRU(): void {
    let oldestTime = Date.now();
    let oldestKey = '';
    
    // Find least recently used
    for (const [key, entry] of this.cache.entries()) {
      if (entry.lastAccess < oldestTime) {
        oldestTime = entry.lastAccess;
        oldestKey = key;
      }
    }
    
    if (oldestKey) {
      this.cache.delete(oldestKey);
    }
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const stats = {
      size: this.cache.size,
      maxSize: this.maxSize,
      entries: [] as any[]
    };
    
    for (const [key, entry] of this.cache.entries()) {
      stats.entries.push({
        key,
        age: Date.now() - entry.timestamp,
        hits: entry.hits,
        ttl: entry.ttl,
        expires: new Date(entry.timestamp + entry.ttl).toISOString()
      });
    }
    
    return stats;
  }

  /**
   * Clear all cache
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Generate cache key from complex objects
   */
  static generateKey(...args: any[]): string {
    return JSON.stringify(args)
      .replace(/[^a-zA-Z0-9]/g, '_')
      .substring(0, 100); // Limit key length
  }
}

// Export singleton instance
export const enhancedCache = EnhancedCache.getInstance();