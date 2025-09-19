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

// Validate backend URL in production
if (process.env.NODE_ENV === 'production' && BACKEND_URL.includes('localhost')) {
  console.error('WARNING: Using localhost backend URL in production!');
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Forward to backend unified-brain endpoint
    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: body.prompt,
        output_format: body.outputFormat || 'analysis',
        context: {
          ...body.context,
          company: body.company,
          gridState: body.gridState,
          includeFormulas: body.includeFormulas,
          includeCitations: body.includeCitations
        },
        stream: body.stream || false,
        options: body.options || {}
      })
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Backend error:', error);
      return NextResponse.json(
        { error: 'Backend request failed', details: error },
        { status: response.status }
      );
    }

    // Handle streaming response with proper error handling
    if (body.stream) {
      const stream = new ReadableStream({
        async start(controller) {
          const reader = response.body?.getReader();
          if (!reader) {
            controller.error(new Error('No response body available for streaming'));
            return;
          }

          const decoder = new TextDecoder();
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                controller.close();
                break;
              }
              
              const text = decoder.decode(value, { stream: true });
              controller.enqueue(new TextEncoder().encode(text));
            }
          } catch (error) {
            console.error('Stream reading error:', error);
            controller.error(error);
          } finally {
            try {
              reader.releaseLock();
            } catch (e) {
              // Reader might already be released
            }
          }
        },
        cancel() {
          // Clean up on stream cancellation
          console.log('Stream cancelled by client');
        }
      });

      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive'
        }
      });
    }

    // Non-streaming response
    const data = await response.json();
    
    // Save to Supabase
    if (data.success && data.result) {
      const sessionId = body.sessionId || uuidv4();
      await saveToSupabase(
        sessionId,
        body.prompt,
        data.result,
        body.outputFormat || 'analysis',
        {
          company: body.company,
          context: body.context,
          timestamp: new Date().toISOString()
        }
      );
      
      // Add sessionId to response for feedback tracking
      data.sessionId = sessionId;
    }
    
    return NextResponse.json(data);

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