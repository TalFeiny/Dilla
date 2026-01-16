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

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
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

  const resultWithSlides = attachSlides(nestedResult, slides);
  const resultsWithSlides = agentPayload?.results ? attachSlides(agentPayload.results, slides) : resultWithSlides;

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
    
    // Debug logging
    console.log('[unified-brain route] Received body.output_format:', body.output_format);
    console.log('[unified-brain route] Received body.outputFormat:', body.outputFormat);
    console.log('[unified-brain route] Sending output_format:', body.output_format || body.outputFormat || 'analysis');
    console.log('[unified-brain route] Backend URL:', BACKEND_URL);
    
    // Quick health check before main request
    try {
      const healthResponse = await fetch(`${BACKEND_URL}/api/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000) // 5 second timeout for health check
      });
      
      if (!healthResponse.ok) {
        console.error('Backend health check failed:', healthResponse.status);
        return NextResponse.json(
          { 
            error: 'Backend is not responding', 
            details: `Health check failed with status ${healthResponse.status}`,
            backendUrl: BACKEND_URL
          },
          { status: 503 }
        );
      }
    } catch (healthError) {
      console.error('Backend health check error:', healthError);
      return NextResponse.json(
        { 
          error: 'Cannot connect to backend', 
          details: healthError instanceof Error ? healthError.message : 'Unknown error',
          backendUrl: BACKEND_URL
        },
        { status: 503 }
      );
    }
    
    // Forward to backend unified-brain endpoint with timeout
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 600000); // 10 minute timeout for deck generation
    
    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
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
          includeCitations: body.includeCitations
        },
        stream: false, // STREAMING DISABLED
        options: body.options || {}
      }),
      signal: controller.signal
    }).finally(() => {
      clearTimeout(timeout);
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Backend error:', error);
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:145','message':'Backend response not OK','data':{status:response.status,errorText:error?.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
      // #endregion
      return NextResponse.json(
        { error: 'Backend request failed', details: error },
        { status: response.status }
      );
    }

    // STREAMING DISABLED - Always use non-streaming response
    // if (body.stream) {
    //   // Streaming functionality has been disabled
    //   // Fall through to non-streaming response
    // }

    // Non-streaming response
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:161','message':'Before JSON parsing - checking response','data':{responseOk:response.ok,contentType:response.headers.get('content-type'),contentLength:response.headers.get('content-length')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    // Get raw response text first to check if it's empty
    const responseText = await response.text();
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:165','message':'Raw response text received','data':{textLength:responseText?.length,isEmpty:!responseText,firstChars:responseText?.substring(0,100)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
    // #endregion
    
    let backendJson: AnyRecord | null = null;
    try {
      backendJson = JSON.parse(responseText);
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:170','message':'JSON parsing succeeded','data':{isNull:backendJson===null,isObject:typeof backendJson==='object',keys:backendJson?Object.keys(backendJson):[],hasSuccess:!!backendJson?.success,hasResult:!!backendJson?.result,hasData:!!backendJson?.data},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
    } catch (parseError) {
      console.error('Failed to parse backend JSON response:', parseError);
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:174','message':'JSON parsing failed','data':{error:parseError instanceof Error?parseError.message:String(parseError),responseText:responseText?.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      return NextResponse.json(
        {
          error: 'Invalid response from backend',
          details: 'Backend returned non-JSON payload'
        },
        { status: 502 }
      );
    }

    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:183','message':'Before null check','data':{isNull:backendJson===null,isObject:typeof backendJson==='object',type:typeof backendJson,value:backendJson},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    if (backendJson === null || typeof backendJson !== 'object') {
      console.error('Backend returned null/invalid payload:', backendJson);
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:188','message':'Null check failed - empty payload error','data':{isNull:backendJson===null,isObject:typeof backendJson==='object',type:typeof backendJson,value:backendJson},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion
      return NextResponse.json(
        {
          error: 'Invalid response from backend',
          details: 'Backend returned an empty payload'
        },
        { status: 502 }
      );
    }
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:199','message':'Null check passed - backendJson structure','data':{keys:Object.keys(backendJson),hasSuccess:!!backendJson.success,hasResult:!!backendJson.result,hasData:!!backendJson.data,resultType:typeof backendJson.result,resultKeys:backendJson.result?Object.keys(backendJson.result):[]},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion

    const normalizedResponse = normalizeAgentResponse(backendJson);
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/15e454b3-6634-4381-8639-5526cecf63d1',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'unified-brain/route.ts:203','message':'After normalization','data':{normalizedSuccess:normalizedResponse.success,normalizedKeys:Object.keys(normalizedResponse),hasResult:!!normalizedResponse.result,hasResults:!!normalizedResponse.results,hasSlides:!!normalizedResponse.slides,resultFormat:normalizedResponse.result?.format,slidesCount:normalizedResponse.result?.slides?.length||normalizedResponse.slides?.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    // Add detailed response logging for deck debugging
    console.log('[unified-brain route] Backend response received:', {
      backendSuccess: backendJson?.success,
      backendHasDataObject: !!backendJson?.data,
      backendDataKeys: backendJson?.data ? Object.keys(backendJson.data) : [],
      normalizedSuccess: normalizedResponse.success,
      normalizedFormat: normalizedResponse.result?.format,
      normalizedSlides: normalizedResponse.result?.slides?.length,
      backendKeys: Object.keys(backendJson),
      normalizedKeys: Object.keys(normalizedResponse)
    });
    
    // CRITICAL DEBUG: Log slide count at each step
    if (normalizedResponse.result?.slides) {
      console.log(`[unified-brain route] ✅ Found ${normalizedResponse.result.slides.length} slides in normalizedResponse.result.slides`);
    } else if (normalizedResponse.results?.slides) {
      console.log(`[unified-brain route] ✅ Found ${normalizedResponse.results.slides.length} slides in normalizedResponse.results.slides`);
    } else if (normalizedResponse.slides) {
      console.log(`[unified-brain route] ✅ Found ${normalizedResponse.slides.length} slides at top level`);
    } else {
      console.log('[unified-brain route] ❌ No slides found in normalized payload');
    }
    
    // Pass through normalized response
    console.log('[unified-brain route] Returning normalized response to frontend');
    
    // Add null safety check
    if (!normalizedResponse) {
      console.error('Empty response from backend');
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
      ).then(result => {
        if (!result.success) {
          console.error('Background Supabase save failed:', result.error, result.details);
        } else {
          console.log('✅ Background Supabase save succeeded');
        }
      }).catch(error => {
        console.error('Background Supabase save error:', error);
        // Don't throw - we already have the response
      });
      
      // Add sessionId to response for feedback tracking
      normalizedResponse.sessionId = sessionId;
    }
    
    // CRITICAL DEBUG: Log final response being sent to frontend
    console.log('[unified-brain route] Sending response to frontend:', {
      success: normalizedResponse.success,
      hasResult: !!normalizedResponse.result,
      hasResults: !!normalizedResponse.results,
      hasDirectSlides: !!normalizedResponse.slides,
      resultFormat: normalizedResponse.result?.format || normalizedResponse.format,
      resultsFormat: normalizedResponse.results?.format,
      slidesCount: normalizedResponse.result?.slides?.length || normalizedResponse.slides?.length,
      resultsSlidesCount: normalizedResponse.results?.slides?.length,
      responseKeys: Object.keys(normalizedResponse)
    });
    
    if (normalizedResponse.result?.slides) {
      console.log(`[unified-brain route] ✅ Sending ${normalizedResponse.result.slides.length} slides to frontend via result.slides`);
    } else if (normalizedResponse.results?.slides) {
      console.log(`[unified-brain route] ✅ Sending ${normalizedResponse.results.slides.length} slides to frontend via results.slides`);
    } else if (normalizedResponse.slides) {
      console.log(`[unified-brain route] ✅ Sending ${normalizedResponse.slides.length} slides to frontend at top level`);
    } else {
      console.log('[unified-brain route] ❌ Sending response with NO slides to frontend');
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