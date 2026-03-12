import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/fpa/balance-sheet?company_id=...&start=2025-01&end=2025-12
 * Fetch Balance Sheet data for the grid view.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const backendUrl = getBackendUrl();

    const res = await fetch(
      `${backendUrl}/api/fpa/balance-sheet?${searchParams.toString()}`,
      { method: 'GET', headers: getBackendHeaders() }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch Balance Sheet data' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch Balance Sheet data' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA Balance Sheet fetch error:', error);
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
 * POST /api/fpa/balance-sheet
 * Update a Balance Sheet line item (manual override).
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/fpa/balance-sheet`, {
      method: 'POST',
      headers: getBackendHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update Balance Sheet' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to update Balance Sheet' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA Balance Sheet update error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
