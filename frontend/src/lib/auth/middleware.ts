import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';

// Rate limiting store (in production, use Redis)
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

export interface AuthenticatedRequest extends NextRequest {
  userId?: string;
  session?: any;
}

/**
 * Authentication middleware for API routes
 * Checks if user is authenticated via NextAuth session
 */
export function withAuth(
  handler: (req: AuthenticatedRequest) => Promise<Response>
) {
  return async (req: NextRequest) => {
    try {
      // Get session from NextAuth
      const session = await getServerSession(authOptions);
      
      if (!session?.user) {
        return NextResponse.json(
          { error: 'Unauthorized - Please sign in' },
          { status: 401 }
        );
      }

      // Add session to request
      (req as AuthenticatedRequest).session = session;
      (req as AuthenticatedRequest).userId = session.user.id || session.user.email;

      // Process the request
      return await handler(req as AuthenticatedRequest);
    } catch (error) {
      console.error('Auth middleware error:', error);
      return NextResponse.json(
        { error: 'Authentication failed' },
        { status: 500 }
      );
    }
  };
}

/**
 * Rate limiting middleware
 * Limits requests per user per minute
 */
export function withRateLimit(
  handler: (req: AuthenticatedRequest) => Promise<Response>,
  options: {
    requests: number;  // Number of requests
    window: number;    // Time window in seconds
  } = { requests: 10, window: 60 }
) {
  return async (req: AuthenticatedRequest) => {
    const userId = req.userId || 'anonymous';
    const now = Date.now();
    const windowMs = options.window * 1000;
    
    // Get or create rate limit entry
    const userLimit = rateLimitStore.get(userId) || { count: 0, resetTime: now + windowMs };
    
    // Reset if window expired
    if (now > userLimit.resetTime) {
      userLimit.count = 0;
      userLimit.resetTime = now + windowMs;
    }
    
    // Check rate limit
    if (userLimit.count >= options.requests) {
      const retryAfter = Math.ceil((userLimit.resetTime - now) / 1000);
      return NextResponse.json(
        { 
          error: 'Too many requests', 
          retryAfter: retryAfter 
        },
        { 
          status: 429,
          headers: {
            'Retry-After': retryAfter.toString(),
            'X-RateLimit-Limit': options.requests.toString(),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': userLimit.resetTime.toString()
          }
        }
      );
    }
    
    // Increment counter
    userLimit.count++;
    rateLimitStore.set(userId, userLimit);
    
    // Add rate limit headers to response
    const response = await handler(req);
    const newResponse = new NextResponse(response.body, response);
    newResponse.headers.set('X-RateLimit-Limit', options.requests.toString());
    newResponse.headers.set('X-RateLimit-Remaining', (options.requests - userLimit.count).toString());
    newResponse.headers.set('X-RateLimit-Reset', userLimit.resetTime.toString());
    
    return newResponse;
  };
}

/**
 * Combined auth + rate limit middleware
 */
export function withAuthAndRateLimit(
  handler: (req: AuthenticatedRequest) => Promise<Response>,
  rateLimitOptions?: { requests: number; window: number }
) {
  // Compose: auth wraps rate limit wraps handler
  const rateLimitWrapped = withRateLimit(handler, rateLimitOptions);
  const authWrapped = withAuth(rateLimitWrapped);
  return authWrapped;
}

/**
 * API key validation for service-to-service calls
 * Used when external services need to call our API
 */
export async function withAPIKey(
  handler: (req: NextRequest) => Promise<Response>
) {
  return async (req: NextRequest) => {
    const apiKey = req.headers.get('x-api-key');
    
    if (!apiKey) {
      return NextResponse.json(
        { error: 'Missing API key' },
        { status: 401 }
      );
    }
    
    // In production, validate against database
    // For now, check against environment variable
    const validApiKey = process.env.INTERNAL_API_KEY;
    
    if (!validApiKey || apiKey !== validApiKey) {
      return NextResponse.json(
        { error: 'Invalid API key' },
        { status: 401 }
      );
    }
    
    return await handler(req);
  };
}

/**
 * CORS middleware for API routes
 */
export function withCORS(
  handler: (req: NextRequest) => Promise<Response>,
  options: {
    origins?: string[];
    methods?: string[];
  } = {}
) {
  return async (req: NextRequest) => {
    const origin = req.headers.get('origin');
    const allowedOrigins = options.origins || [process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001'];
    const allowedMethods = options.methods || ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'];
    
    // Handle preflight requests
    if (req.method === 'OPTIONS') {
      return new NextResponse(null, {
        status: 200,
        headers: {
          'Access-Control-Allow-Origin': allowedOrigins.includes(origin || '') ? origin! : allowedOrigins[0],
          'Access-Control-Allow-Methods': allowedMethods.join(', '),
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
          'Access-Control-Max-Age': '86400',
        },
      });
    }
    
    const response = await handler(req);
    
    // Add CORS headers to response
    if (origin && allowedOrigins.includes(origin)) {
      response.headers.set('Access-Control-Allow-Origin', origin);
      response.headers.set('Access-Control-Allow-Methods', allowedMethods.join(', '));
      response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    }
    
    return response;
  };
}