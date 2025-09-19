import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

export interface SecurityConfig {
  maxRequestSize?: number;
  maxPromptLength?: number;
  maxDepth?: number;
  allowedDomains?: string[];
  blockedPatterns?: RegExp[];
  rateLimits?: {
    perMinute?: number;
    perHour?: number;
  };
  csrfProtection?: boolean;
  sanitizeHtml?: boolean;
}

const DEFAULT_CONFIG: SecurityConfig = {
  maxRequestSize: 10 * 1024 * 1024, // 10MB
  maxPromptLength: 10000,
  maxDepth: 10,
  blockedPatterns: [
    /system\s*prompt/gi,
    /ignore\s*previous\s*instructions/gi,
    /disregard\s*all\s*prior/gi,
    /forget\s*everything/gi,
    /admin\s*mode/gi,
    /developer\s*mode/gi,
    /debug\s*mode/gi,
    /override\s*safety/gi,
    /bypass\s*security/gi,
    /execute\s*command/gi,
    /eval\s*\(/gi,
    /Function\s*\(/gi,
    /__proto__/gi,
    /constructor\s*\[/gi,
    /process\.env/gi,
    /require\s*\(/gi,
    /import\s*\(/gi,
    /<script/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
    /data:text\/html/gi,
  ],
  rateLimits: {
    perMinute: 60,
    perHour: 1000,
  },
  csrfProtection: true,
  sanitizeHtml: true,
};

const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

export class SecurityMiddleware {
  private config: SecurityConfig;
  private trustedOrigins: Set<string>;

  constructor(config: SecurityConfig = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.trustedOrigins = new Set([
      'http://localhost:3000',
      'http://localhost:3001',
      'https://dilla.ai',
      ...(config.allowedDomains || []),
    ]);
  }

  sanitizeInput(input: any, depth = 0): any {
    if (depth > (this.config.maxDepth || 10)) {
      throw new Error('Maximum object depth exceeded');
    }

    if (typeof input === 'string') {
      return this.sanitizeString(input);
    }

    if (Array.isArray(input)) {
      return input.map(item => this.sanitizeInput(item, depth + 1));
    }

    if (input && typeof input === 'object') {
      const sanitized: any = {};
      for (const [key, value] of Object.entries(input)) {
        const sanitizedKey = this.sanitizeString(key);
        
        if (this.isPrototypeProperty(sanitizedKey)) {
          continue;
        }
        
        sanitizedArray.from(itizedKey) = this.sanitizeInput(value, depth + 1);
      }
      return sanitized;
    }

    return input;
  }

  private sanitizeString(str: string): string {
    if (typeof str !== 'string') return String(str);

    // Check length
    if (str.length > (this.config.maxPromptLength || 10000)) {
      throw new Error('Input exceeds maximum allowed length');
    }

    // Check for blocked patterns
    for (const pattern of (this.config.blockedPatterns || [])) {
      if (pattern.test(str)) {
        throw new Error('Input contains prohibited patterns');
      }
    }

    // Remove null bytes
    str = str.replace(/\x00/g, '');

    // Escape special characters for prompts
    str = str.replace(/\\/g, '\\\\');
    
    // Remove potential command injections
    str = str.replace(/[;&|`$()]/g, '');

    // Sanitize HTML if enabled
    if (this.config.sanitizeHtml) {
      str = this.escapeHtml(str);
    }

    return str.trim();
  }

  private escapeHtml(str: string): string {
    const htmlEscapes: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
      '/': '&#x2F;',
    };
    
    return str.replace(/[&<>"'\/]/g, (match) => htmlEscapesArray.from(ch) || match);
  }

  private isPrototypeProperty(key: string): boolean {
    const dangerous = ['__proto__', 'constructor', 'prototype'];
    return dangerous.includes(key.toLowerCase());
  }

  validatePrompt(prompt: string): { valid: boolean; sanitized?: string; error?: string } {
    try {
      const sanitized = this.sanitizeString(prompt);
      
      // Additional prompt-specific validations
      if (prompt.includes('{{') || prompt.includes('}}')) {
        return { valid: false, error: 'Template injection detected' };
      }

      if (/\bsystem\b.*\bprompt\b/i.test(prompt)) {
        return { valid: false, error: 'System prompt manipulation detected' };
      }

      return { valid: true, sanitized };
    } catch (error) {
      return { 
        valid: false, 
        error: error instanceof Error ? error.message : 'Validation failed' 
      };
    }
  }

  checkRateLimit(identifier: string): boolean {
    const now = Date.now();
    const limits = this.config.rateLimits;
    
    if (!limits) return true;

    const key = `rate_${identifier}`;
    const current = rateLimitStore.get(key);

    if (!current || current.resetTime < now) {
      rateLimitStore.set(key, {
        count: 1,
        resetTime: now + 60000, // 1 minute window
      });
      return true;
    }

    if (current.count >= (limits.perMinute || 60)) {
      return false;
    }

    current.count++;
    return true;
  }

  validateOrigin(request: NextRequest): boolean {
    const origin = request.headers.get('origin');
    const referer = request.headers.get('referer');

    if (!origin && !referer) {
      // Allow requests without origin (e.g., server-to-server)
      return true;
    }

    const requestOrigin = origin || new URL(referer || '').origin;
    return this.trustedOrigins.has(requestOrigin);
  }

  generateCSRFToken(): string {
    return crypto.randomBytes(32).toString('hex');
  }

  validateCSRFToken(request: NextRequest, token: string): boolean {
    const requestToken = request.headers.get('x-csrf-token');
    return requestToken === token;
  }

  async processRequest(request: NextRequest): Promise<{ 
    valid: boolean; 
    sanitizedBody?: any; 
    error?: string;
    headers?: Record<string, string>;
  }> {
    try {
      // Check origin
      if (!this.validateOrigin(request)) {
        return { valid: false, error: 'Invalid origin' };
      }

      // Check rate limit
      const identifier = request.headers.get('x-forwarded-for') || 
                       request.headers.get('x-real-ip') || 
                       'unknown';
      
      if (!this.checkRateLimit(identifier)) {
        return { valid: false, error: 'Rate limit exceeded' };
      }

      // Parse and sanitize body
      let body: any;
      try {
        const text = await request.text();
        
        // Check request size
        if (text.length > (this.config.maxRequestSize || 10485760)) {
          return { valid: false, error: 'Request too large' };
        }

        body = JSON.parse(text);
      } catch {
        return { valid: false, error: 'Invalid JSON' };
      }

      const sanitizedBody = this.sanitizeInput(body);

      // Add security headers
      const headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';",
      };

      return { valid: true, sanitizedBody, headers };
    } catch (error) {
      return { 
        valid: false, 
        error: error instanceof Error ? error.message : 'Security check failed' 
      };
    }
  }
}

// Export singleton instance
export const securityMiddleware = new SecurityMiddleware();

// Helper function for API routes
export async function withSecurity(
  request: NextRequest,
  handler: (sanitizedData: any) => Promise<NextResponse>
): Promise<NextResponse> {
  const result = await securityMiddleware.processRequest(request);

  if (!result.valid) {
    return NextResponse.json(
      { error: result.error },
      { 
        status: 400,
        headers: result.headers,
      }
    );
  }

  const response = await handler(result.sanitizedBody);
  
  // Add security headers to response
  if (result.headers) {
    Object.entries(result.headers).forEach(([key, value]) => {
      response.headers.set(key, value);
    });
  }

  return response;
}

// Specific validators for different input types
export const validators = {
  companyName: (name: string): boolean => {
    return /^[a-zA-Z0-9\s\-\.&,]{1,100}$/.test(name);
  },

  email: (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  },

  url: (url: string): boolean => {
    try {
      const parsed = new URL(url);
      return ['http:', 'https:'].includes(parsed.protocol);
    } catch {
      return false;
    }
  },

  sqlSafe: (input: string): string => {
    return input.replace(/['";\\]/g, '');
  },

  mongoSafe: (input: string): string => {
    return input.replace(/[$]/g, '');
  },
};