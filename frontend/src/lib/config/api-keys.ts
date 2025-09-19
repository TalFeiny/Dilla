/**
 * Centralized API Key Configuration
 * All API keys should be accessed through this module
 */

interface ApiKeys {
  ANTHROPIC: string | undefined;
  TAVILY: string | undefined;
  FIRECRAWL: string | undefined;
  SUPABASE_URL: string | undefined;
  SUPABASE_KEY: string | undefined;
}

class ApiKeyManager {
  private static instance: ApiKeyManager;
  private keys: ApiKeys;
  private warnings = new Set<string>();

  private constructor() {
    this.keys = this.loadKeys();
    this.validateKeys();
  }

  static getInstance(): ApiKeyManager {
    if (!ApiKeyManager.instance) {
      ApiKeyManager.instance = new ApiKeyManager();
    }
    return ApiKeyManager.instance;
  }

  private loadKeys(): ApiKeys {
    return {
      ANTHROPIC: process.env.ANTHROPIC_API_KEY || 
                 process.env.CLAUDE_API_KEY || 
                 process.env.NEXT_PUBLIC_ANTHROPIC_API_KEY,
      
      TAVILY: process.env.TAVILY_API_KEY || 
              process.env.NEXT_PUBLIC_TAVILY_API_KEY,
      
      FIRECRAWL: process.env.FIRECRAWL_API_KEY || 
                 process.env.NEXT_PUBLIC_FIRECRAWL_API_KEY,
      
      SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
      
      SUPABASE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY || 
                    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    };
  }

  private validateKeys(): void {
    const missing: string[] = [];
    
    if (!this.keys.TAVILY) {
      missing.push('TAVILY_API_KEY');
    }
    
    if (!this.keys.ANTHROPIC) {
      missing.push('ANTHROPIC_API_KEY or CLAUDE_API_KEY');
    }
    
    if (!this.keys.SUPABASE_URL || !this.keys.SUPABASE_KEY) {
      missing.push('SUPABASE configuration');
    }
    
    if (missing.length > 0) {
      console.warn('⚠️ Missing API keys:', missing.join(', '));
      console.warn('Some features will be limited. Please configure your environment variables.');
    }
  }

  getKey(service: keyof ApiKeys): string | undefined {
    const key = this.keys[service];
    
    if (!key && !this.warnings.has(service)) {
      console.warn(`[API Keys] ${service} key not configured`);
      this.warnings.add(service);
    }
    
    return key;
  }

  hasKey(service: keyof ApiKeys): boolean {
    return !!this.keys[service];
  }

  getMissingKeys(): string[] {
    const missing: string[] = [];
    
    Object.entries(this.keys).forEach(([name, value]) => {
      if (!value) {
        missing.push(name);
      }
    });
    
    return missing;
  }

  getStatus(): Record<keyof ApiKeys, boolean> {
    return {
      ANTHROPIC: !!this.keys.ANTHROPIC,
      TAVILY: !!this.keys.TAVILY,
      FIRECRAWL: !!this.keys.FIRECRAWL,
      SUPABASE_URL: !!this.keys.SUPABASE_URL,
      SUPABASE_KEY: !!this.keys.SUPABASE_KEY
    };
  }
}

// Export singleton instance
export const apiKeyManager = ApiKeyManager.getInstance();

// Export convenience functions
export function getApiKey(service: keyof ApiKeys): string | undefined {
  return apiKeyManager.getKey(service);
}

export function hasApiKey(service: keyof ApiKeys): boolean {
  return apiKeyManager.hasKey(service);
}

export function getApiKeyStatus() {
  return apiKeyManager.getStatus();
}

export function getMissingApiKeys() {
  return apiKeyManager.getMissingKeys();
}