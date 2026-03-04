import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/fpa/pnl?fund_id=...&company_id=...&start=2025-01&end=2025-12
 * Fetch P&L actuals + forecast for the grid view.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const backendUrl = getBackendUrl();

    const res = await fetch(
      `${backendUrl}/api/fpa/pnl?${searchParams.toString()}`,
      { method: 'GET', headers: getBackendHeaders() }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch P&L data' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch P&L data' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA P&L fetch error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * POST /api/fpa/pnl
 * Update a P&L line item (manual override).
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/fpa/pnl`, {
      method: 'POST',
      headers: getBackendHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update P&L' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to update P&L' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA P&L update error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
