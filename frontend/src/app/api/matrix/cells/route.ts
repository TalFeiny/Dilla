import { NextRequest, NextResponse } from 'next/server';
import { applyCellUpdate } from '@/lib/matrix/apply-cell-server';

/**
 * POST /api/matrix/cells
 * Update a matrix cell value with audit trail.
 * Delegates to shared applyCellUpdate (used also by suggestions accept).
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      company_id,
      column_id,
      old_value,
      new_value,
      fund_id,
      user_id,
      data_source,
      metadata,
      source_document_id: bodySourceDocId,
    } = body;
    const sourceDocumentId =
      bodySourceDocId ??
      (metadata &&
      typeof metadata === 'object' &&
      (metadata as Record<string, unknown>).sourceDocumentId != null
        ? (metadata as Record<string, unknown>).sourceDocumentId
        : null);

    const result = await applyCellUpdate({
      company_id,
      column_id,
      old_value,
      new_value,
      fund_id: fund_id ?? null,
      user_id: user_id ?? null,
      data_source,
      metadata: metadata && typeof metadata === 'object' ? (metadata as Record<string, unknown>) : undefined,
      source_document_id: sourceDocumentId,
    });

    if (result.success) {
      return NextResponse.json({ success: true, company: result.company });
    }
    const fail = result as { success: false; error: string; status: number; code?: string };
    return NextResponse.json(
      { error: fail.error, ...(fail.code ? { code: fail.code } : {}) },
      { status: fail.status }
    );
  } catch (error) {
    console.error('[matrix/cells] POST error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
