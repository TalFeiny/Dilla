import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Performance-optimized middleware
export function middleware(request: NextRequest) {
  const response = NextResponse.next()

  // Add performance headers
  response.headers.set('X-DNS-Prefetch-Control', 'on')
  response.headers.set('X-Frame-Options', 'DENY')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('Referrer-Policy', 'origin-when-cross-origin')
  
  // Cache static assets aggressively
  if (request.nextUrl.pathname.startsWith('/_next/') || 
      request.nextUrl.pathname.startsWith('/api/')) {
    response.headers.set('Cache-Control', 'public, max-age=31536000, immutable')
  }
  
  // API routes - no cache
  if (request.nextUrl.pathname.startsWith('/api/')) {
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
  }
  
  // Static pages - cache for 1 hour
  if (request.nextUrl.pathname === '/' || 
      request.nextUrl.pathname.startsWith('/documents/')) {
    response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=3600')
  }

  return response
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
} 