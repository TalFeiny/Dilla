import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * GET /api/cell-actions/actions/[actionId]
 * Proxy to backend – fetch single action by ID.
 */
export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ actionId: string }> }
) {
  try {
    const { actionId } = await context.params;
    if (!actionId) {
      return NextResponse.json({ error: 'actionId required' }, { status: 400 });
    }

    const backendUrl = getBackendUrl();
    const res = await fetch(
      `${backendUrl}/api/cell-actions/actions/${encodeURIComponent(actionId)}`,
      { headers: { Accept: 'application/json' } }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Action not found' }));
      return NextResponse.json(
        { error: err.detail ?? `Action ${actionId} not found` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Cell-actions proxy GET /actions/[actionId]:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
