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

/**
 * Get headers that must be included on every server-side fetch to the backend.
 * Includes the backend API secret so the backend accepts the request.
 */
export function getBackendHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...extra,
  };
  const secret = process.env.BACKEND_API_SECRET;
  if (secret) {
    headers['X-Backend-Secret'] = secret;
  } else {
    console.error('[getBackendHeaders] BACKEND_API_SECRET is missing — backend will return 403');
  }
  return headers;
}

/**
 * Fetch wrapper for server-side calls to the backend.
 * Automatically prepends the backend URL and injects the API secret header.
 */
export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${getBackendUrl()}${path}`;
  const headers = new Headers(init?.headers);
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  const secret = process.env.BACKEND_API_SECRET;
  if (secret) headers.set('X-Backend-Secret', secret);
  return fetch(url, { ...init, headers });
}
