import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/integrations/xero/connections?company_id=...
 * Proxy to backend — avoids CORS issues from direct client→backend calls.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const backendUrl = getBackendUrl();

    const res = await fetch(
      `${backendUrl}/api/integrations/xero/connections?${searchParams.toString()}`,
      { method: 'GET', headers: getBackendHeaders() }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch Xero connections' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch Xero connections' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Xero connections proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
