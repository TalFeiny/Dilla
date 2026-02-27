import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * PUT /api/fpa/models/[id]/formula
 * Update a formula for a specific step
 */
export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    const body = await request.json();
    const { step_id, formula } = body;

    if (!step_id || !formula) {
      return NextResponse.json(
        { error: 'step_id and formula are required' },
        { status: 400 }
      );
    }

    const backendUrl = getBackendUrl();
    const res = await fetch(
      `${backendUrl}/api/fpa/models/${encodeURIComponent(id)}/formula?step_id=${encodeURIComponent(step_id)}&formula=${encodeURIComponent(formula)}`,
      {
        method: 'PUT',
        headers: getBackendHeaders(),
      }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update formula' }));
      return NextResponse.json(
        { error: err.detail ?? 'Failed to update formula' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA formula update error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
