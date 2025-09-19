/**
 * Secure Proxy Route for Tavily Search API
 * This route handles all Tavily API calls server-side to protect API keys
 */

import { NextRequest, NextResponse } from 'next/server';
import { withRateLimit } from '@/lib/auth-middleware';
import { securityMiddleware } from '@/lib/security/security-middleware';

const TAVILY_API_URL = 'https://api.tavily.com/search';

// Get API key from server-side environment only
function getApiKey(): string | undefined {
  return process.env.TAVILY_API_KEY || 
         process.env.NEXT_SERVER_TAVILY_API_KEY;
}

const TAVILY_API_KEY = getApiKey();

// Verify API key is available at startup
if (!TAVILY_API_KEY && process.env.NODE_ENV !== 'test') {
  console.error('CRITICAL: TAVILY_API_KEY not configured in server environment');
  console.error('Please ensure .env.local.server is loaded or environment variables are set');
}

export async function POST(request: NextRequest) {
  // Apply rate limiting (30 requests per minute for search)
  return withRateLimit(request, handleRequest, { 
    maxRequests: 30, 
    windowMs: 60000,
    requireAuth: false // Allow anonymous for now
  });
}

async function handleRequest(request: NextRequest) {
  try {
    // Verify API key is available (re-check in case of hot reload)
    const apiKey = getApiKey();
    if (!apiKey) {
      console.error('Tavily API key not found in server environment');
      return NextResponse.json(
        { error: 'Tavily API not configured on server' },
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
    const { query, search_depth, max_results, include_raw_content } = body;

    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'Invalid request: query string required' },
        { status: 400 }
      );
    }

    // Prepare request to Tavily
    const tavilyRequest = {
          api_key: apiKey,
          query,
          search_depth: search_depth || 'advanced',
          max_results: max_results || 10,
          include_raw_content: include_raw_content || true,
          include_answer: true,
          include_images: false,
        };

    // Make request to Tavily
    const response = await fetch(TAVILY_API_URL, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(tavilyRequest),
        });

    if (!response.ok) {
      const error = await response.text();
      console.error('Tavily API error:', error);
      return NextResponse.json(
        { error: 'Failed to process search request' },
        { status: response.status }
      );
    }

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