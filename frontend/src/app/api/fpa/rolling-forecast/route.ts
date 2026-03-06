import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/fpa/rolling-forecast?company_id=...&granularity=monthly&window=24
 * Proxy to backend RollingForecastService.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const backendUrl = getBackendUrl();

    const res = await fetch(
      `${backendUrl}/api/fpa/rolling-forecast?${searchParams.toString()}`,
      { method: 'GET', headers: getBackendHeaders() }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch rolling forecast' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch rolling forecast' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Rolling forecast fetch error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
