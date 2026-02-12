import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * GET /api/fpa/models/[id]
 * Get an FPA model by ID
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: 'Model ID required' }, { status: 400 });
    }

    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/fpa/models/${encodeURIComponent(id)}`, {
      headers: { Accept: 'application/json' },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Model not found' }));
      return NextResponse.json(
        { error: err.detail ?? `Model ${id} not found` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('FPA model fetch error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
