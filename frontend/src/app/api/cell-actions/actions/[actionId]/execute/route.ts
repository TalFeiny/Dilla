import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

// source_companies with web discovery can take 2+ minutes
export const maxDuration = 300;

/**
 * POST /api/cell-actions/actions/[actionId]/execute
 * Proxy to backend execute. Body: ActionExecutionRequest (action_id, row_id, column_id, inputs, mode, fund_id, company_id).
 * Returns ActionExecutionResponse (success, action_id, value, display_value, metadata, error).
 */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ actionId: string }> }
) {
  try {
    const { actionId } = await context.params;
    if (!actionId) {
      return NextResponse.json({ error: 'actionId required' }, { status: 400 });
    }
    console.log('[cell-actions] Route invoked', actionId, 'proxying to backend');

    const body = await request.json();
    const payload = {
      action_id: body.action_id ?? actionId,
      row_id: body.row_id ?? '',
      column_id: body.column_id ?? '',
      inputs: body.inputs ?? {},
      mode: body.mode ?? 'portfolio',
      fund_id: body.fund_id ?? null,
      company_id: body.company_id ?? null,
      trace_id: body.trace_id ?? undefined,
    };

    if (body.trace_id) {
      console.log('[cell-actions] traceId=%s action=%s', body.trace_id, actionId);
    }

    const backendUrl = getBackendUrl();
    const path = `/api/cell-actions/actions/${encodeURIComponent(actionId)}/execute`;
    console.log('[cell-actions] Proxying POST to backend', backendUrl, path);
    const res = await fetch(
      `${backendUrl}${path}`,
      {
        method: 'POST',
        headers: getBackendHeaders(),
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(270_000), // 4.5 min — under maxDuration
      }
    );

    let data: Record<string, unknown>;
    try {
      const text = await res.text();
      data = text ? (JSON.parse(text) as Record<string, unknown>) : {};
    } catch {
      data = {};
    }

    if (!res.ok) {
      const err = data as { error?: string; detail?: string | Array<{ msg?: string }> };
      let errorMsg: string = err.error ?? 'Action execution failed';
      if (typeof err.detail === 'string') errorMsg = err.detail;
      else if (Array.isArray(err.detail) && err.detail[0]?.msg) errorMsg = String(err.detail[0].msg);
      return NextResponse.json(
        { error: errorMsg, details: data },
        { status: res.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Cell-actions proxy POST /actions/[actionId]/execute:', error);
    const msg = error instanceof Error ? error.message : String(error);
    const isNetwork =
      msg.includes('fetch') ||
      msg.includes('ECONNREFUSED') ||
      msg.includes('ENOTFOUND') ||
      msg.includes('network');
    return NextResponse.json(
      {
        error: isNetwork ? 'Backend unreachable. Start backend and set BACKEND_URL.' : msg,
        details: msg,
      },
      { status: 503 }
    );
  }
}
