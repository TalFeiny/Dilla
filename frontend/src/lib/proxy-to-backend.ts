import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * Generic proxy helper — forwards a Next.js API request to the FastAPI backend.
 * Injects X-Backend-Secret and routes through the server so the browser never
 * talks to the backend directly.
 */
export async function proxyToBackend(
  request: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  try {
    const backendUrl = getBackendUrl();
    const url = `${backendUrl}${backendPath}`;

    const init: RequestInit = {
      method: request.method,
      headers: getBackendHeaders(),
    };

    if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
      init.body = await request.text();
    }

    const res = await fetch(url, init);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Backend error: ${res.status}` }));
      return NextResponse.json(
        { error: err.detail ?? `Backend error: ${res.status}` },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error(`Proxy error for ${backendPath}:`, error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}

/** Build backend path with query string from the incoming request */
export function withQuery(request: NextRequest, basePath: string): string {
  const qs = request.nextUrl.searchParams.toString();
  return qs ? `${basePath}?${qs}` : basePath;
}
