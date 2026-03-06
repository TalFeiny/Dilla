import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

// Single source of truth: same resolution as getBackendUrl() so proxy and API routes use same host
const BACKEND_URL = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.FASTAPI_URL || 'http://localhost:8000').replace(/\/+$/, '')

// Security headers — only applied in production
const SECURITY_HEADERS: Record<string, string> = process.env.NODE_ENV !== 'production' ? {
  'X-Frame-Options': 'SAMEORIGIN',
} : {
  'X-XSS-Protection': '1; mode=block',
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
  'Content-Security-Policy': [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' data: http://localhost:* https://fonts.googleapis.com https://api.fontshare.com https://cdn.fontshare.com",
    "img-src 'self' data: https: blob:",
    "font-src 'self' data: https://fonts.gstatic.com https://api.fontshare.com https://cdn.fontshare.com",
    "connect-src 'self' https://api.anthropic.com https://api.tavily.com https://api.firecrawl.dev https://*.supabase.co wss://*.supabase.co http://localhost:8000 https://dilla-copy-production.up.railway.app https://dilla-ai.com https://www.dilla-ai.com",
    "frame-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests"
  ].join('; '),
}

// Routes that should be proxied to FastAPI backend
const PYTHON_API_ROUTES = [
  '/api/v2/',
  '/api/orchestrator/',
  '/api/agents/',
  '/api/agent/',
  '/api/pwerm/',
  '/api/companies/',
  '/api/market-research/',
  '/api/dashboard/',
  '/api/compliance/',
  '/api/streaming/',
  '/api/python/',
  '/api/rl/',
  '/api/data/',
  '/api/scenarios/',
  '/api/advanced-analytics/',
  '/api/mcp/',
  '/api/brain/',
  '/api/investment/',
  '/api/analyst/',
  '/api/health',
]

// Routes that should be handled by Next.js (not proxied)
const NEXTJS_ONLY_ROUTES = [
  '/api/auth',
  '/api/agent/spreadsheet-direct',
  '/api/agent/spreadsheet-stream',
  '/api/agent/cim-generator',
  '/api/agent/company-cim',
  '/api/agent/dynamic-data-v2',
  '/api/agent/dynamic-data',
  '/api/agent/test-orchestration',
  '/api/agent/tools/',
  '/api/agent/unified-brain',
  '/api/cell-actions',
  '/api/portfolio',
  '/api/matrix',
  '/api/documents',
  '/api/funds',
  '/api/fpa',
]

const PUBLIC_ROUTES = ['/login', '/signup', '/forgot-password', '/auth/callback', '/auth/error', '/']

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  // Skip middleware for static assets
  if (pathname.startsWith('/_next/') || pathname === '/favicon.ico' || pathname.includes('.')) {
    return NextResponse.next()
  }

  const isApiRoute = pathname.startsWith('/api/')

  // ── Backend proxy (API routes only) ──
  // Returns early so we never hit updateSession for proxied routes.
  // This is critical: the backend fetch can take seconds, and adding a
  // Supabase getUser() call on top would blow past Vercel's Edge timeout.
  if (isApiRoute) {
    // Handle CORS preflight immediately — no network calls needed
    if (request.method === 'OPTIONS') {
      const origin = request.headers.get('origin')
      const allowedOrigins = ['http://localhost:3000', 'http://localhost:3001', 'https://dilla-ai.com', 'https://www.dilla-ai.com', 'https://dilla.ai']
      const headers: Record<string, string> = {
        ...SECURITY_HEADERS,
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-CSRF-Token, X-Request-ID',
        'Access-Control-Max-Age': '86400',
      }
      if (origin && allowedOrigins.includes(origin)) {
        headers['Access-Control-Allow-Origin'] = origin
        headers['Access-Control-Allow-Credentials'] = 'true'
      }
      return new Response(null, { status: 200, headers })
    }

    // Check if this should be proxied to FastAPI
    const isNextJSOnly = NEXTJS_ONLY_ROUTES.some(route => pathname.startsWith(route))
    const shouldProxy = !isNextJSOnly && PYTHON_API_ROUTES.some(route => pathname.startsWith(route))

    if (shouldProxy) {
      const backendUrl = `${BACKEND_URL}${pathname}${request.nextUrl.search}`

      try {
        const headers = new Headers(request.headers)
        headers.set('host', new URL(BACKEND_URL).host)
        headers.delete('connection')

        const backendSecret = process.env.BACKEND_API_SECRET
        if (backendSecret) {
          headers.set('X-Backend-Secret', backendSecret)
        }

        let body: string | null = null
        if (request.method !== 'GET' && request.method !== 'HEAD') {
          body = await request.text()
        }

        const proxyRes = await fetch(backendUrl, {
          method: request.method,
          headers,
          body,
        })

        const responseHeaders = new Headers(proxyRes.headers)
        Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
          responseHeaders.set(key, value)
        })

        // CORS
        const origin = request.headers.get('origin')
        const proxyAllowedOrigins = ['http://localhost:3000', 'http://localhost:3001', 'https://dilla-ai.com', 'https://www.dilla-ai.com']
        if (origin && proxyAllowedOrigins.includes(origin)) {
          responseHeaders.set('Access-Control-Allow-Origin', origin)
          responseHeaders.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
          responseHeaders.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token')
          responseHeaders.set('Access-Control-Allow-Credentials', 'true')
        }

        responseHeaders.set('X-Request-ID', globalThis.crypto.randomUUID())

        return new Response(proxyRes.body, {
          status: proxyRes.status,
          statusText: proxyRes.statusText,
          headers: responseHeaders,
        })
      } catch {
        return NextResponse.json(
          { error: 'Backend unreachable', path: pathname },
          { status: 502, headers: SECURITY_HEADERS }
        )
      }
    }

    // Next.js API route — pass through with CORS + no-cache headers, no auth check needed
    const response = NextResponse.next()
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
    Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
      response.headers.set(key, value)
    })

    const origin = request.headers.get('origin')
    const allowedOrigins = ['http://localhost:3000', 'http://localhost:3001', 'https://dilla-ai.com', 'https://www.dilla-ai.com', 'https://dilla.ai']
    if (origin && allowedOrigins.includes(origin)) {
      response.headers.set('Access-Control-Allow-Origin', origin)
      response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
      response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token, X-Request-ID')
      response.headers.set('Access-Control-Max-Age', '86400')
    }

    return response
  }

  // ── Page routes: Supabase Auth session refresh ──
  // Only page routes call updateSession (one network call to Supabase).
  // API routes are handled above and never reach here.
  const isPublicRoute = PUBLIC_ROUTES.includes(pathname)

  const { user, response } = await updateSession(request)

  // Protect app routes — redirect unauthenticated users to /login
  if (!user && !isPublicRoute) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/login'
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Add security headers
  Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
    response.headers.set(key, value)
  })

  response.headers.set('X-Request-ID', globalThis.crypto.randomUUID())

  // Static pages - cache for 1 hour
  if (pathname === '/' || pathname.startsWith('/documents/')) {
    response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=3600')
  }

  return response
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
}
