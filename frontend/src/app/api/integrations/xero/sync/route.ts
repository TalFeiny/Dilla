import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * POST /api/integrations/xero/sync
 * Proxy to backend — avoids CORS issues from direct client→backend calls.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/integrations/xero/sync`, {
      method: 'POST',
      headers: getBackendHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Xero sync failed' }));
      return NextResponse.json(
        { error: err.detail ?? 'Xero sync failed' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Xero sync proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
