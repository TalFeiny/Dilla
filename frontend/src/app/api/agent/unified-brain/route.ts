/**
 * Unified Brain API Route - Proxies to FastAPI Backend
 * This bridges all frontend requests to the backend unified orchestrator
 */

import { NextRequest, NextResponse } from 'next/server';
import { saveToSupabase } from './save-to-supabase';
// Generate secure UUID using crypto API
const uuidv4 = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments (still more secure than Math.random)
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 10
  return Array.from(bytes, b => b.toString(16).padStart(2, '0'))
    .join('')
    .replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/, '$1-$2-$3-$4-$5');
};

import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();
type AnyRecord = Record<string, any>;

const pickSlides = (...candidates: Array<AnyRecord | undefined>): any[] => {
  for (const candidate of candidates) {
    if (candidate && Array.isArray(candidate.slides) && candidate.slides.length > 0) {
      return candidate.slides;
    }
  }
  return [];  // Return empty array instead of undefined
};

const attachSlides = (target: AnyRecord | undefined, slides: any[]): AnyRecord => {
  if (target && Array.isArray(target.slides)) {
    return target;
  }
  return { ...(target ?? {}), slides };
};

const normalizeAgentResponse = (backendJson: AnyRecord): AnyRecord => {
  const agentPayload =
    backendJson?.data ??
    backendJson?.result ??
    backendJson?.results ??
    backendJson ??
    {};

  const nestedResult = agentPayload?.result ?? agentPayload?.results ?? agentPayload ?? {};
  const slides =
    pickSlides(agentPayload, nestedResult, agentPayload?.result, agentPayload?.results, backendJson?.data, backendJson?.result, backendJson?.results) ?? [];

  // Merge agentPayload fields into nestedResult so sibling fields
  // (market_analysis, companies, investment_thesis, etc.) are not dropped
  // when the backend nests the main response under result/results.
  const mergedResult = nestedResult === agentPayload
    ? nestedResult
    : { ...agentPayload, ...nestedResult };
  const resultWithSlides = attachSlides(mergedResult, slides);
  const resultsWithSlides = agentPayload?.results ? attachSlides({ ...agentPayload, ...agentPayload.results }, slides) : resultWithSlides;

  return {
    ...agentPayload,
    success:
      typeof agentPayload?.success === 'boolean'
        ? agentPayload.success
        : Boolean(backendJson?.success),
    task_id: backendJson?.task_id ?? agentPayload?.task_id,
    error: agentPayload?.error ?? backendJson?.error,
    format: resultWithSlides?.format ?? agentPayload?.format,
    slides: resultWithSlides?.slides ?? [],
    data: resultWithSlides,
    result: resultWithSlides,
    results: resultsWithSlides
  };
};

// Validate backend URL in production
if (process.env.NODE_ENV === 'production' && BACKEND_URL.includes('localhost')) {
  console.error('WARNING: Using localhost backend URL in production!');
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Forward to backend unified-brain endpoint with timeout
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 600000); // 10 minute timeout for deck generation
    
    const backendEndpoint = body.stream
      ? `${BACKEND_URL}/api/agent/unified-brain-stream`
      : `${BACKEND_URL}/api/agent/unified-brain`;
    const response = await fetch(backendEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
        body: JSON.stringify({
        prompt: body.prompt,
        output_format: body.output_format || body.outputFormat || 'analysis',
        context: {
          ...body.context,
          company: body.company,
          gridState: body.gridState,
          includeFormulas: body.includeFormulas,
          includeCitations: body.includeCitations,
          // Grid (matrixContext) so the agent can read rows, resolve @mentions to rowIds, and emit grid_commands
          matrixContext: body.context?.matrixContext ?? body.matrixContext,
          matrix_context: body.context?.matrixContext ?? body.matrixContext,
          fundId: body.context?.fundId ?? body.fundId,
          // Forward approved plan steps so backend can execute them in order
          plan_steps: body.context?.plan_steps || undefined,
          // Analysis manifest for state persistence — tells backend which derived
          // data (cap_table_history, scenarios, etc.) was computed in prior requests
          analysis_manifest: body.context?.analysis_manifest ?? body.analysis_manifest ?? undefined,
          // Datetime context for time-aware analysis
          datetime: body.context?.datetime || {
            iso: new Date().toISOString(),
            date: new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
            quarter: `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${new Date().getFullYear()}`,
          },
        },
        // Agent context for conversation continuity (recent analyses, active company, summary, memo)
        agent_context: {
          ...(body.agent_context || {}),
          memo_sections: body.agent_context?.memo_sections || [],
          memo_title: body.agent_context?.memo_title || '',
          current_datetime: body.agent_context?.current_datetime || new Date().toISOString(),
        },
        // Output format hint — backend determines final format from prompt + tool results
        output_format_hint: body.output_format_hint || body.output_format || 'analysis',
        // Approved plan from plan approval flow (ephemeral)
        approved_plan: body.approved_plan || undefined,
        stream: body.stream || false,
        options: body.options || {}
      }),
      signal: controller.signal
    }).finally(() => {
      clearTimeout(timeout);
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Backend error:', error);
      return NextResponse.json(
        { error: 'Backend request failed', details: error },
        { status: response.status }
      );
    }

    // Streaming path: pipe NDJSON progress events from backend to frontend
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
      console.error('Failed to parse backend JSON response:', parseError);
      return NextResponse.json(
        {
          error: 'Invalid response from backend',
          details: 'Backend returned non-JSON payload'
        },
        { status: 502 }
      );
    }

    if (backendJson === null || typeof backendJson !== 'object') {
      console.error('Backend returned null/invalid payload:', backendJson);
      return NextResponse.json(
        {
          error: 'Invalid response from backend',
          details: 'Backend returned an empty payload'
        },
        { status: 502 }
      );
    }
    
    const normalizedResponse = normalizeAgentResponse(backendJson);
    
    // Null safety check
    if (!normalizedResponse) {
      return NextResponse.json(
        { error: 'Empty response from backend' },
        { status: 500 }
      );
    }
    
    // Save to Supabase asynchronously (don't block response)
    if (normalizedResponse.success && normalizedResponse.result) {
      const sessionId = body.sessionId || uuidv4();
      
      // For deck format, only save metadata due to size
      const saveData = (body.outputFormat || body.output_format) === 'deck' 
        ? { 
            format: 'deck',
            slide_count: normalizedResponse.result.slides?.length || 0,
            companies: normalizedResponse.result.companies || [],
            timestamp: new Date().toISOString()
          }
        : normalizedResponse.result;
      
      // Don't await - let it run in background
      saveToSupabase(
        sessionId,
        body.prompt,
        saveData,
        body.outputFormat || body.output_format || 'analysis',
        {
          company: body.company,
          context: body.context,
          timestamp: new Date().toISOString()
        }
      ).catch((err) => {
        console.error('[unified-brain] Background Supabase save failed:', err?.message || err);
      });
      
      // Add sessionId to response for feedback tracking
      normalizedResponse.sessionId = sessionId;
    }
    
    return NextResponse.json(normalizedResponse);

  } catch (error) {
    console.error('Unified brain route error:', error);
    return NextResponse.json(
      { 
        error: 'Failed to process request',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}