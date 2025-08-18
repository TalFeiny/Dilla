import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export const runtime = 'nodejs';
export const maxDuration = 300; // 5 minutes

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Validate required fields
  if (!body.company_name || !body.current_arr || !body.sector) {
    return NextResponse.json(
      { error: 'Missing required fields: company_name, current_arr, sector' },
      { status: 400 }
    );
  }

  // Create a TransformStream for streaming
  const encoder = new TextEncoder();
  const stream = new TransformStream();
  const writer = stream.writable.getWriter();

  // Load environment variables
  const tavilyKey = process.env.TAVILY_API_KEY;
  const claudeKey = process.env.CLAUDE_API_KEY;

  // First check if company data exists in database
  let cachedFundingData = null;
  if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
    try {
      const { createClient } = require('@supabase/supabase-js');
      const supabase = createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.SUPABASE_SERVICE_ROLE_KEY!
      );
      
      // Check for cached funding data
      const { data: company, error } = await supabase
        .from('companies')
        .select('total_invested_usd, amount_raised, latest_investment_date, cached_funding_data, funding_data_updated_at')
        .eq('name', body.company_name)
        .single();
        
      if (company && !error) {
        const dataAge = company.funding_data_updated_at ? 
          (Date.now() - new Date(company.funding_data_updated_at).getTime()) / (1000 * 60 * 60 * 24) : 
          Infinity;
          
        // Use cached data if less than 30 days old
        if (dataAge < 30 && company.cached_funding_data) {
          cachedFundingData = company.cached_funding_data;
          await writer.write(encoder.encode(JSON.stringify({
            type: 'progress',
            message: 'Using cached funding data',
            progress: 10
          }) + '\n'));
        }
      }
    } catch (e) {
      console.error('Database error:', e);
    }
  }

  // Prepare input data
  const inputData = {
    company_data: {
      name: body.company_name,
      current_arr_usd: (body.current_arr || 5.0) * 1000000,
      revenue_growth_annual_pct: (body.growth_rate || 0.30) * 100,
      sector: body.sector || 'SaaS',
      cached_funding_data: cachedFundingData
    },
    stream_progress: true // Tell Python to stream progress
  };

  // Start the analysis
  const pythonPath = process.env.PYTHON_PATH || 'python3';
  const scriptPath = path.join(process.cwd(), 'scripts', 'pwerm_analysis.py');
  
  const envWithKeys = {
    ...process.env,
    TAVILY_API_KEY: tavilyKey || '',
    CLAUDE_API_KEY: claudeKey || '',
    PYTHONUNBUFFERED: '1'
  };

  const pythonProcess = spawn(pythonPath, [scriptPath, '--stream'], {
    env: envWithKeys
  });

  // Send input
  pythonProcess.stdin.write(JSON.stringify(inputData));
  pythonProcess.stdin.end();

  // Handle output
  let outputBuffer = '';
  let finalResult: any = null;

  pythonProcess.stdout.on('data', async (data) => {
    const text = data.toString();
    const lines = text.split('\n').filter((line: string) => line.trim());
    
    for (const line of lines) {
      try {
        const parsed = JSON.parse(line);
        
        if (parsed.type === 'progress') {
          // Stream progress update
          await writer.write(encoder.encode(line + '\n'));
        } else if (parsed.type === 'final') {
          // Final result
          finalResult = parsed.data;
        } else if (parsed.type === 'cache_update') {
          // Update cache in database
          if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
            try {
              const { createClient } = require('@supabase/supabase-js');
              const supabase = createClient(
                process.env.NEXT_PUBLIC_SUPABASE_URL!,
                process.env.SUPABASE_SERVICE_ROLE_KEY!
              );
              
              await supabase
                .from('companies')
                .upsert({
                  name: body.company_name,
                  cached_funding_data: parsed.funding_data,
                  funding_data_updated_at: new Date().toISOString()
                }, {
                  onConflict: 'name'
                });
            } catch (e) {
              console.error('Cache update error:', e);
            }
          }
        }
      } catch (e) {
        // Not JSON, just append to buffer
        outputBuffer += line;
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error('Python stderr:', data.toString());
  });

  pythonProcess.on('close', async (code) => {
    if (code !== 0 || !finalResult) {
      await writer.write(encoder.encode(JSON.stringify({
        type: 'error',
        message: 'Analysis failed',
        details: outputBuffer
      }) + '\n'));
    } else {
      await writer.write(encoder.encode(JSON.stringify({
        type: 'complete',
        data: finalResult
      }) + '\n'));
    }
    
    await writer.close();
  });

  // Return the stream
  return new Response(stream.readable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}