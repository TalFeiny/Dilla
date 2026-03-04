/**
 * CFO Brain API Route - Proxies to FastAPI Backend
 * Same architecture as unified-brain but hits the CFO agent endpoint.
 * Handles FP&A, budgeting, cash flow, variance analysis, and scenario planning.
 */

import { NextRequest, NextResponse } from 'next/server';
import { saveToSupabase } from '../unified-brain/save-to-supabase';

// CFO agent may run multi-step FPA workflows — needs long timeout
export const maxDuration = 300;

const uuidv4 = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  return Array.from(bytes, b => b.toString(16).padStart(2, '0'))
    .join('')
    .replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/, '$1-$2-$3-$4-$5');
};

import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();
type AnyRecord = Record<string, any>;

const normalizeAgentResponse = (backendJson: AnyRecord): AnyRecord => {
  const agentPayload =
    backendJson?.data ??
    backendJson?.result ??
    backendJson?.results ??
    backendJson ??
    {};

  const nestedResult = agentPayload?.result ?? agentPayload?.results ?? agentPayload ?? {};

  const mergedResult = nestedResult === agentPayload
    ? nestedResult
    : { ...agentPayload, ...nestedResult };

  return {
    ...agentPayload,
    success:
      typeof agentPayload?.success === 'boolean'
        ? agentPayload.success
        : Boolean(backendJson?.success),
    task_id: backendJson?.task_id ?? agentPayload?.task_id,
    error: agentPayload?.error ?? backendJson?.error,
    format: mergedResult?.format ?? agentPayload?.format,
    data: mergedResult,
    result: mergedResult,
    results: mergedResult,
    agent: 'cfo',
  };
};

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 600000);

    const backendEndpoint = body.stream
      ? `${BACKEND_URL}/api/agent/cfo-brain-stream`
      : `${BACKEND_URL}/api/agent/cfo-brain`;

    const response = await fetch(backendEndpoint, {
      method: 'POST',
      headers: getBackendHeaders(),
      body: JSON.stringify({
        prompt: body.prompt,
        output_format: body.output_format || body.outputFormat || 'analysis',
        context: {
          ...body.context,
          company: body.company,
          // Company FPA context for system prompt personalization
          company_fpa_context: body.context?.company_fpa_context ?? body.company_fpa_context,
          gridState: body.gridState,
          matrixContext: body.context?.matrixContext ?? body.matrixContext,
          matrix_context: body.context?.matrixContext ?? body.matrixContext,
          fundId: body.context?.fundId ?? body.fundId,
          plan_steps: body.context?.plan_steps || undefined,
          plan_mode: body.context?.plan_mode || undefined,
          memo_artifacts: body.context?.memo_artifacts || undefined,
          analysis_manifest: body.context?.analysis_manifest ?? body.analysis_manifest ?? undefined,
          datetime: body.context?.datetime || {
            iso: new Date().toISOString(),
            date: new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
            quarter: `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${new Date().getFullYear()}`,
          },
        },
        agent_context: {
          ...(body.agent_context || {}),
          memo_sections: body.agent_context?.memo_sections || [],
          memo_title: body.agent_context?.memo_title || '',
          current_datetime: body.agent_context?.current_datetime || new Date().toISOString(),
        },
        output_format_hint: body.output_format_hint || body.output_format || 'analysis',
        approved_plan: body.approved_plan || undefined,
        stream: body.stream || false,
        options: body.options || {},
      }),
      signal: controller.signal,
    }).finally(() => {
      clearTimeout(timeout);
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('CFO backend error:', error);
      return NextResponse.json(
        { error: 'CFO backend request failed', details: error, agent: 'cfo' },
        { status: response.status }
      );
    }

    // Streaming path
    if (body.stream && response.body) {
      return new Response(response.body, {
        headers: {
          'Content-Type': 'application/x-ndjson',
          'Transfer-Encoding': 'chunked',
          'Cache-Control': 'no-cache',
        },
      });
    }

    // Non-streaming response
    const responseText = await response.text();

    let backendJson: AnyRecord | null = null;
    try {
      backendJson = JSON.parse(responseText);
    } catch (parseError) {
      console.error('Failed to parse CFO backend JSON:', parseError);
      return NextResponse.json(
        { error: 'Invalid response from CFO backend', details: 'Non-JSON payload', agent: 'cfo' },
        { status: 502 }
      );
    }

    if (backendJson === null || typeof backendJson !== 'object') {
      return NextResponse.json(
        { error: 'Invalid response from CFO backend', details: 'Empty payload', agent: 'cfo' },
        { status: 502 }
      );
    }

    const normalizedResponse = normalizeAgentResponse(backendJson);

    if (!normalizedResponse) {
      return NextResponse.json(
        { error: 'Empty response from CFO backend', agent: 'cfo' },
        { status: 500 }
      );
    }

    // Save to Supabase asynchronously
    if (normalizedResponse.success && normalizedResponse.result) {
      const sessionId = body.sessionId || uuidv4();

      saveToSupabase(
        sessionId,
        body.prompt,
        normalizedResponse.result,
        body.outputFormat || body.output_format || 'analysis',
        {
          company: body.company,
          context: body.context,
          agent: 'cfo',
          timestamp: new Date().toISOString(),
        }
      ).catch((err) => {
        console.error('[cfo-brain] Background Supabase save failed:', err?.message || err);
      });

      normalizedResponse.sessionId = sessionId;
    }

    return NextResponse.json(normalizedResponse);

  } catch (error) {
    console.error('CFO brain route error:', error);
    return NextResponse.json(
      {
        error: 'Failed to process CFO request',
        details: error instanceof Error ? error.message : 'Unknown error',
        agent: 'cfo',
      },
      { status: 500 }
    );
  }
}
