/**
 * Secure Proxy Route for Anthropic/Claude API
 * This route handles all Claude API calls server-side to protect API keys
 */

import { NextRequest, NextResponse } from 'next/server';
import { withRateLimit } from '@/lib/auth-middleware';
import { securityMiddleware } from '@/lib/security/security-middleware';

const ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages';

// Get API key from server-side environment only
function getApiKey(): string | undefined {
  // Try multiple possible env var names
  return process.env.ANTHROPIC_API_KEY || 
         process.env.CLAUDE_API_KEY ||
         process.env.NEXT_SERVER_ANTHROPIC_API_KEY;
}

const ANTHROPIC_API_KEY = getApiKey();

// Verify API key is available at startup
if (!ANTHROPIC_API_KEY && process.env.NODE_ENV !== 'test') {
  console.error('CRITICAL: ANTHROPIC_API_KEY not configured in server environment');
  console.error('Please ensure .env.local.server is loaded or environment variables are set');
}

export async function POST(request: NextRequest) {
  // Apply rate limiting (20 requests per minute for AI calls)
  return withRateLimit(request, handleRequest, { 
    maxRequests: 20, 
    windowMs: 60000,
    requireAuth: false // Allow anonymous for now, can change to true later
  });
}

async function handleRequest(request: NextRequest) {
  try {
    // Verify API key is available (re-check in case of hot reload)
    const apiKey = getApiKey();
    if (!apiKey) {
      console.error('Anthropic API key not found in server environment');
      return NextResponse.json(
        { error: 'Anthropic API not configured on server' },
        { status: 500 }
      );
    }

    // Validate and sanitize request
    const validation = await securityMiddleware.processRequest(request);
    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    const body = validation.sanitizedBody

    // Validate request data
    const { messages, model, max_tokens, temperature, stream } = body;

        if (!messages || !Array.isArray(messages)) {
          return NextResponse.json(
            { error: 'Invalid request: messages array required' },
            { status: 400 }
          );
        }

        // Prepare request to Anthropic
        const anthropicRequest = {
          messages,
          model: model || 'claude-3-5-sonnet-20241022',
          max_tokens: max_tokens || 4096,
          temperature: temperature || 0.7,
          stream: stream || false,
        };

        // Make request to Anthropic
        const response = await fetch(ANTHROPIC_API_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
          },
          body: JSON.stringify(anthropicRequest),
        });

        if (!response.ok) {
          const error = await response.text();
          console.error('Anthropic API error:', error);
          return NextResponse.json(
            { error: 'Failed to process AI request' },
            { status: response.status }
          );
        }

        // Handle streaming response
        if (stream) {
          const stream = new ReadableStream({
            async start(controller) {
              const reader = response.body?.getReader();
              if (!reader) {
                controller.error(new Error('No response body'));
                return;
              }

              try {
                while (true) {
                  const { done, value } = await reader.read();
                  if (done) {
                    controller.close();
                    break;
                  }
                  controller.enqueue(value);
                }
              } catch (error) {
                controller.error(error);
              }
            },
          });

          return new NextResponse(stream, {
            headers: {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache',
              'Connection': 'keep-alive',
            },
          });
        }

        // Non-streaming response
        const data = await response.json();
        return NextResponse.json(data);
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}