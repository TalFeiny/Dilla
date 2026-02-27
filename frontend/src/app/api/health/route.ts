import { NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/health
 * Proxies to backend /api/health. Returns status and loaded routers (e.g. cell_actions).
 * Used by matrix control panel to show "Cell actions unavailable" when backend is down or cell_actions router not loaded.
 */
export async function GET() {
  try {
    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/health`, {
      headers: getBackendHeaders(),
      next: { revalidate: 0 },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(
        { status: 'unhealthy', routers: {}, error: data.detail ?? data.error ?? 'Backend health check failed' },
        { status: res.status }
      );
    }
    return NextResponse.json({
      status: data.status ?? 'healthy',
      service: data.service,
      routers: data.routers ?? {},
    });
  } catch (error) {
    console.error('Health proxy error:', error);
    return NextResponse.json(
      {
        status: 'unhealthy',
        routers: {},
        error: error instanceof Error ? error.message : 'Backend unreachable',
      },
      { status: 503 }
    );
  }
}
