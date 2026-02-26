/**
 * Shared backend URL helper
 * Centralizes backend URL resolution for consistent usage across the app
 */

/**
 * Get the backend URL for server-side API routes (Next.js API routes proxying to FastAPI)
 * Must match middleware resolution so proxy and API routes use the same host.
 */
export function getBackendUrl(): string {
  // Server-side: same order as middleware (single source of truth)
  if (typeof window === 'undefined') {
    return (
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      process.env.FASTAPI_URL ||
      'http://localhost:8000'
    ).replace(/\/+$/, '');
  }
  // Client-side: only NEXT_PUBLIC_* (server vars not available in browser)
  return (process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000').replace(/\/+$/, '');
}

/**
 * Get the backend URL for client-side calls (browser)
 * Only uses NEXT_PUBLIC_ prefixed env vars
 */
export function getClientBackendUrl(): string {
  return (process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000').replace(/\/+$/, '');
}
