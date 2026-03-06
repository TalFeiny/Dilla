import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/fpa/variance?company_id=...&budget_id=...&start=2025-01&end=2025-12
 * Proxy to backend BudgetVarianceService.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = request.nextUrl;
    const backendUrl = getBackendUrl();

    const res = await fetch(
      `${backendUrl}/api/fpa/variance?${searchParams.toString()}`,
      { method: 'GET', headers: getBackendHeaders() }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch variance data' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to fetch variance data' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Variance fetch error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
