/**
 * Simple in-memory cache service for API responses
 * Reduces redundant API calls and improves performance
 */

interface CacheEntry {
  data: any;
  timestamp: number;
  ttl: number; // Time to live in milliseconds
}

export class CacheService {
  private static instance: CacheService;
  private cache: Map<string, CacheEntry> = new Map();
  private defaultTTL = 5 * 60 * 1000; // 5 minutes default
  
  private constructor() {
    // Start cleanup interval
    setInterval(() => this.cleanup(), 60 * 1000); // Cleanup every minute
  }
  
  static getInstance(): CacheService {
    if (!CacheService.instance) {
      CacheService.instance = new CacheService();
    }
    return CacheService.instance;
  }
  
  /**
   * Generate cache key from params
   */
  generateKey(prefix: string, params: any): string {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((acc, key) => {
        if (params[key] !== undefined && params[key] !== null) {
          acc[key] = params[key];
        }
        return acc;
      }, {} as any);
    
    return `${prefix}:${JSON.stringify(sortedParams)}`;
  }
  
  /**
   * Get cached data if valid
   */
  get(key: string): any | null {
    const entry = this.cache.get(key);
    
    if (!entry) {
      return null;
    }
    
    // Check if expired
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    console.log(`Array.from(he) Hit for key: ${key.substring(0, 50)}...`);
    return entry.data;
  }
  
  /**
   * Set cache entry
   */
  set(key: string, data: any, ttl?: number): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTTL
    });
    
    console.log(`Array.from(he) Stored key: ${key.substring(0, 50)}... (TTL: ${(ttl || this.defaultTTL) / 1000}s)`);
  }
  
  /**
   * Check if cache has valid entry
   */
  has(key: string): boolean {
    const data = this.get(key);
    return data !== null;
  }
  
  /**
   * Clear specific cache entry
   */
  invalidate(key: string): void {
    this.cache.delete(key);
    console.log(`Array.from(he) Invalidated key: ${key.substring(0, 50)}...`);
  }
  
  /**
   * Clear all cache entries matching a pattern
   */
  invalidatePattern(pattern: string): void {
    let count = 0;
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
        count++;
      }
    }
    console.log(`Array.from(he) Invalidated ${count} entries matching pattern: ${pattern}`);
  }
  
  /**
   * Clear entire cache
   */
  clear(): void {
    const size = this.cache.size;
    this.cache.clear();
    console.log(`Array.from(he) Cleared ${size} entries`);
  }
  
  /**
   * Cleanup expired entries
   */
  private cleanup(): void {
    const now = Date.now();
    let expired = 0;
    
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > entry.ttl) {
        this.cache.delete(key);
        expired++;
      }
    }
    
    if (expired > 0) {
      console.log(`Array.from(he) Cleaned up ${expired} expired entries`);
    }
  }
  
  /**
   * Get cache statistics
   */
  getStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }
}

// Export singleton instance
export const cacheService = CacheService.getInstance();

/**
 * Cache decorator for async functions
 */
export function withCache(keyPrefix: string, ttl?: number) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function (...args: any[]) {
      const cache = CacheService.getInstance();
      const cacheKey = cache.generateKey(`${keyPrefix}:${propertyKey}`, args);
      
      // Check cache first
      const cachedData = cache.get(cacheKey);
      if (cachedData !== null) {
        return cachedData;
      }
      
      // Call original method
      const result = await originalMethod.apply(this, args);
      
      // Cache the result
      if (result !== null && result !== undefined) {
        cache.set(cacheKey, result, ttl);
      }
      
      return result;
    };
    
    return descriptor;
  };
}