import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Single source of truth: same resolution as getBackendUrl() so proxy and API routes use same host
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.FASTAPI_URL || 'http://localhost:8000'

// Security headers configuration - relaxed for development
const isDevelopment = process.env.NODE_ENV !== 'production'

const SECURITY_HEADERS = isDevelopment ? {
  // Minimal security in development for faster iteration
  'X-Frame-Options': 'SAMEORIGIN',
} : {
  // Production security headers
  'X-XSS-Protection': '1; mode=block',
  'X-Frame-Options': 'DENY',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
  'Content-Security-Policy': [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' data: http://localhost:* https://fonts.googleapis.com https://api.fontshare.com",
    "img-src 'self' data: https: blob:",
    "font-src 'self' data: https://fonts.gstatic.com https://api.fontshare.com",
    "connect-src 'self' https://api.anthropic.com https://api.tavily.com https://api.firecrawl.dev https://*.supabase.co wss://*.supabase.co http://localhost:8000 https://dilla-production.up.railway.app",
    "frame-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests"
  ].join('; '),
}

// Rate limiting store
const rateLimitStore = new Map<string, { count: number; resetTime: number }>()

// Clean up old rate limit entries periodically
if (typeof setInterval !== 'undefined') {
  setInterval(() => {
    const now = Date.now()
    Array.from(rateLimitStore.entries()).forEach(([key, value]) => {
      if (value.resetTime < now) {
        rateLimitStore.delete(key)
      }
    })
  }, 60000) // Clean every minute
}

// Routes that should be proxied to FastAPI backend
// NOTE: /api/documents and /api/documents/* are NOT here – upload/list/process live in Next.js;
// the Next.js process route then calls the backend. Do not add /api/documents/ here.
const PYTHON_API_ROUTES = [
  '/api/v2/',              // New versioned API
  '/api/orchestrator/',    // Agent orchestrator
  '/api/agents/',          // Agent endpoints
  '/api/agent/',           // Dynamic data matrix agent
  '/api/pwerm/',           // PWERM analysis
  '/api/companies/',        // Companies endpoints (excludes /portfolio - see NEXTJS_ONLY)
  // /api/portfolio/ REMOVED - portfolio CRUD + companies use Next.js + Supabase; backend has mock stub only
  '/api/market-research/', // Market intelligence
  '/api/dashboard/',       // Dashboard analytics
  '/api/compliance/',      // Compliance/KYC
  '/api/streaming/',       // Streaming endpoints
  '/api/python/',          // Python script execution
  '/api/rl/',              // Reinforcement learning
  '/api/data/',            // Data queries
  '/api/scenarios/',       // Scenario analysis
  '/api/advanced-analytics/', // Advanced analytics (NEW)
  '/api/mcp/',             // MCP orchestrator
  '/api/brain/',           // Agent brain
  '/api/investment/',      // Investment analysis
  '/api/analyst/',         // Analyst endpoints
  '/api/health',           // Health check endpoint
]

// Routes that should be handled by Next.js (not proxied)
// Portfolio CRUD + companies use Next.js + Supabase; FastAPI has no POST /portfolio/:id/companies
const NEXTJS_ONLY_ROUTES = [
  '/api/auth',   // NextAuth session, signin, etc.
  '/api/agent/spreadsheet-direct',
  '/api/agent/spreadsheet-stream',  // New streaming endpoint
  '/api/agent/cim-generator',  // CIM generator
  '/api/agent/company-cim',  // Company CIM
  '/api/agent/dynamic-data-v2',
  '/api/agent/dynamic-data',
  '/api/agent/test-orchestration',  // Add our test endpoint
  '/api/agent/tools/',
  '/api/agent/unified-brain',  // Unified brain has its own Next.js route handler
  '/api/cell-actions',  // Cell actions: Next.js route proxies to backend (execute/route.ts)
  '/api/portfolio',   // Portfolio + companies: Next.js + Supabase (must NOT proxy to backend)
  '/api/matrix',      // Matrix columns, cells, suggestions: Next.js + Supabase
  '/api/documents',   // Document upload/fetch/delete: Next.js + Supabase
  '/api/funds',       // Fund CRUD: Next.js + Supabase
]

// Performance-optimized middleware with API gateway functionality and security
export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname
  
  // Skip middleware for static assets and fast paths
  if (pathname.startsWith('/_next/') || pathname === '/favicon.ico' || pathname.includes('.')) {
    return NextResponse.next()
  }
  const clientId = request.headers.get('x-forwarded-for') || 
                   request.headers.get('x-real-ip') || 
                   request.ip || 
                   'unknown'
  
  // Skip security checks in development for speed
  if (process.env.NODE_ENV === 'production') {
    // Security: Check for suspicious patterns in URL
    const url = pathname + request.nextUrl.search
    const suspiciousPatterns = [
      /(\.\.|\/\/)/,  // Directory traversal
      /[<>\"']/,       // XSS attempts
      /(\%00|\x00)/,   // Null bytes
      /union.*select/i, // SQL injection
      /javascript:/i,   // JavaScript protocol
      /on\w+\s*=/i,    // Event handlers
    ]

    for (const pattern of suspiciousPatterns) {
      if (pattern.test(url)) {
        console.warn(`Array.from(urity) Suspicious request blocked: ${url} from ${clientId}`)
        return NextResponse.json(
          { error: 'Invalid request' },
          { status: 400, headers: SECURITY_HEADERS }
        )
      }
    }
  }

  // Rate limiting for API routes
  if (pathname.startsWith('/api/')) {
    const now = Date.now()
    const windowMs = 60000 // 1 minute
    const maxRequests = 100 // 100 requests per minute per IP
    
    const rateLimitKey = `${clientId}_${Math.floor(now / windowMs)}`
    const current = rateLimitStore.get(rateLimitKey) || { count: 0, resetTime: now + windowMs }
    
    if (current.count >= maxRequests) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        { 
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((current.resetTime - now) / 1000)),
            ...SECURITY_HEADERS,
          }
        }
      )
    }
    
    current.count++
    rateLimitStore.set(rateLimitKey, current)

    // Validate request size (skip for document upload – route allows 100MB)
    const contentLength = request.headers.get('content-length')
    const maxSize = 10 * 1024 * 1024 // 10MB
    const isDocumentUpload = pathname === '/api/documents' && request.method === 'POST'

    if (!isDocumentUpload && contentLength && parseInt(contentLength, 10) > maxSize) {
      return NextResponse.json(
        { error: 'Request entity too large' },
        { status: 413, headers: SECURITY_HEADERS }
      )
    }
  }
  
  // Check if this is a Next.js-only route (should NOT be proxied)
  const isNextJSOnly = NEXTJS_ONLY_ROUTES.some(route => pathname.startsWith(route))
  
  // Check if this request should be proxied to FastAPI
  const shouldProxy = !isNextJSOnly && PYTHON_API_ROUTES.some(route => pathname.startsWith(route))
  
  if (shouldProxy) {
    // Proxy to FastAPI backend
    const backendUrl = `${BACKEND_URL}${pathname}${request.nextUrl.search}`
    
    // Log the proxy for debugging
    console.log(`[Middleware] Proxying ${pathname} to ${backendUrl}`)
    
    // Create a rewrite response to FastAPI
    const response = NextResponse.rewrite(backendUrl)
    
    // Add security headers to proxied responses
    Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
      response.headers.set(key, value)
    })
    
    // Add CORS headers for FastAPI responses
    const origin = request.headers.get('origin')
    const allowedOrigins = ['http://localhost:3000', 'http://localhost:3001', 'https://dilla-ai.com', 'https://www.dilla-ai.com']

    if (origin && allowedOrigins.includes(origin)) {
      response.headers.set('Access-Control-Allow-Origin', origin)
      response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
      response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token')
    }
    
    // Add request ID for tracing
    response.headers.set('X-Request-ID', globalThis.crypto.randomUUID())
    
    return response
  }
  
  // Regular Next.js request handling
  const response = NextResponse.next()

  // Add all security headers
  Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
    response.headers.set(key, value)
  })
  
  // Add request ID for tracing
  response.headers.set('X-Request-ID', globalThis.crypto.randomUUID())
  
  // Cache static assets aggressively
  if (pathname.startsWith('/_next/')) {
    response.headers.set('Cache-Control', 'public, max-age=31536000, immutable')
  }
  
  // API routes - no cache
  if (pathname.startsWith('/api/')) {
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
    
    // CORS handling for API routes
    const origin = request.headers.get('origin')
    const allowedOrigins = ['http://localhost:3000', 'http://localhost:3001', 'https://dilla-ai.com', 'https://www.dilla-ai.com']

    if (origin && allowedOrigins.includes(origin)) {
      response.headers.set('Access-Control-Allow-Origin', origin)
      response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
      response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token, X-Request-ID')
      response.headers.set('Access-Control-Max-Age', '86400')
    }
    
    // Handle preflight requests
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 200, headers: response.headers })
    }
    
    // Warn about legacy routes during migration (skip known Next.js routes)
    if (!shouldProxy && !pathname.startsWith('/api/auth')) {
      console.warn(`[Middleware] Legacy API route accessed: ${pathname}`)
    }
  }
  
  // Static pages - cache for 1 hour
  if (pathname === '/' || pathname.startsWith('/documents/')) {
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