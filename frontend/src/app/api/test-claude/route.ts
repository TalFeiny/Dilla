import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const claudeKey = process.env.CLAUDE_API_KEY || process.env.ANTHROPIC_API_KEY || '';
  
  if (!claudeKey) {
    return NextResponse.json({ error: 'Claude API key not found' }, { status: 500 });
  }

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': claudeKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-haiku-20240307',
        max_tokens: 100,
        messages: [
          {
            role: 'user',
            content: 'Say hello in 5 words or less'
          }
        ]
      })
    });

    const data = await response.json();
    
    if (!response.ok) {
      return NextResponse.json({ 
        error: 'Claude API error',
        status: response.status,
        details: data
      }, { status: response.status });
    }

    return NextResponse.json({ 
      success: true,
      response: data,
      message: 'Claude API is working'
    });

  } catch (error) {
    return NextResponse.json({ 
      error: 'Failed to call Claude API',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}