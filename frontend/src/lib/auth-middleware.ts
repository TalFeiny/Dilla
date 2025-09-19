import { getServerSession } from 'next-auth';
import { NextRequest, NextResponse } from 'next/server';
import { authOptions } from '@/lib/auth';

/**
 * Middleware to protect API routes with authentication
 */
export async function withAuth(
  request: NextRequest,
  handler: (req: NextRequest, session: any) => Promise<NextResponse>
): Promise<NextResponse> {
  try {
    // Get session from NextAuth
    const session = await getServerSession(authOptions);
    
    // Check if user is authenticated
    if (!session) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    
    // Call the handler with the session
    return await handler(request, session);
  } catch (error) {
    console.error('Auth middleware error:', error);
    return NextResponse.json(
      { error: 'Authentication error' },
      { status: 500 }
    );
  }
}

/**
 * Rate limiting for authenticated users
 */
const userRateLimits = new Map<string, { count: number; resetTime: number }>();

export async function withRateLimit(
  request: NextRequest,
  handler: (req: NextRequest) => Promise<NextResponse>,
  options: { 
    maxRequests?: number; 
    windowMs?: number;
    requireAuth?: boolean;
  } = {}
): Promise<NextResponse> {
  const { maxRequests = 30, windowMs = 60000, requireAuth = true } = options;
  
  // Get user identifier
  let userId = 'anonymous';
  
  if (requireAuth) {
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }
    userId = session.user?.email || 'unknown';
  } else {
    // Use IP for anonymous users
    userId = request.headers.get('x-forwarded-for') || 
             request.headers.get('x-real-ip') || 
             'unknown';
  }
  
  // Check rate limit
  const now = Date.now();
  const key = `${userId}_${Math.floor(now / windowMs)}`;
  const current = userRateLimits.get(key) || { count: 0, resetTime: now + windowMs };
  
  if (current.count >= maxRequests) {
    return NextResponse.json(
      { error: 'Rate limit exceeded. Please try again later.' },
      { 
        status: 429,
        headers: {
          'Retry-After': String(Math.ceil((current.resetTime - now) / 1000)),
        }
      }
    );
  }
  
  // Update count
  current.count++;
  userRateLimits.set(key, current);
  
  // Clean up old entries periodically
  if (Math.random() < 0.01) { // 1% chance to clean
    const cutoff = now - windowMs * 2;
    for (const [k, v] of userRateLimits.entries()) {
      if (v.resetTime < cutoff) {
        userRateLimits.delete(k);
      }
    }
  }
  
  return await handler(request);
}

/**
 * Combined auth and rate limit middleware
 */
export async function withAuthAndRateLimit(
  request: NextRequest,
  handler: (req: NextRequest, session: any) => Promise<NextResponse>,
  rateLimitOptions?: { maxRequests?: number; windowMs?: number }
): Promise<NextResponse> {
  // First check authentication
  const session = await getServerSession(authOptions);
  
  if (!session) {
    return NextResponse.json(
      { error: 'Authentication required' },
      { status: 401 }
    );
  }
  
  // Then apply rate limiting
  return withRateLimit(
    request,
    async (req) => handler(req, session),
    { ...rateLimitOptions, requireAuth: false } // Already checked auth
  );
}