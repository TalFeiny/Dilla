import { NextRequest, NextResponse } from 'next/server';
import { getSupabaseServer } from '@/lib/supabase/server';

export interface AuthenticatedRequest extends NextRequest {
  userId?: string;
  organizationId?: string;
}

/**
 * Authentication middleware for API routes.
 * Checks if user is authenticated via Supabase session.
 */
export function withAuth(
  handler: (req: AuthenticatedRequest) => Promise<Response>
) {
  return async (req: NextRequest) => {
    try {
      const supabase = await getSupabaseServer();
      const { data: { user }, error } = await supabase.auth.getUser();

      if (error || !user) {
        return NextResponse.json(
          { error: 'Unauthorized - Please sign in' },
          { status: 401 }
        );
      }

      // Look up org from public.users (id = auth.uid())
      const { data: profile } = await supabase
        .from('users')
        .select('organization_id')
        .eq('id', user.id)
        .single();

      (req as AuthenticatedRequest).userId = user.id;
      (req as AuthenticatedRequest).organizationId = profile?.organization_id;

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

// Rate limiting store
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

export function withRateLimit(
  handler: (req: AuthenticatedRequest) => Promise<Response>,
  options: { requests: number; window: number } = { requests: 10, window: 60 }
) {
  return async (req: AuthenticatedRequest) => {
    const userId = req.userId || 'anonymous';
    const now = Date.now();
    const windowMs = options.window * 1000;

    const userLimit = rateLimitStore.get(userId) || { count: 0, resetTime: now + windowMs };

    if (now > userLimit.resetTime) {
      userLimit.count = 0;
      userLimit.resetTime = now + windowMs;
    }

    if (userLimit.count >= options.requests) {
      const retryAfter = Math.ceil((userLimit.resetTime - now) / 1000);
      return NextResponse.json(
        { error: 'Too many requests', retryAfter },
        {
          status: 429,
          headers: {
            'Retry-After': retryAfter.toString(),
            'X-RateLimit-Limit': options.requests.toString(),
            'X-RateLimit-Remaining': '0',
          },
        }
      );
    }

    userLimit.count++;
    rateLimitStore.set(userId, userLimit);

    const response = await handler(req);
    const newResponse = new NextResponse(response.body, response);
    newResponse.headers.set('X-RateLimit-Limit', options.requests.toString());
    newResponse.headers.set('X-RateLimit-Remaining', (options.requests - userLimit.count).toString());
    return newResponse;
  };
}

export function withAuthAndRateLimit(
  handler: (req: AuthenticatedRequest) => Promise<Response>,
  rateLimitOptions?: { requests: number; window: number }
) {
  return withAuth(withRateLimit(handler, rateLimitOptions));
}
