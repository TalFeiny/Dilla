import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: path.join(process.cwd(), '.env.local') });

export const maxDuration = 300;

export async function POST(request: NextRequest) {
  const body = await request.json();
  
  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();
      
      // Send initial status
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'status', message: 'Starting analysis...' })}\n\n`));
      
      // Prepare input data
      const inputData = {
        company_data: {
          name: body.company_name,
          current_arr_usd: body.current_arr || 5.0,
          revenue_growth_annual_pct: (body.growth_rate || 0.30) * 100,
          sector: body.sector || 'SaaS'
        },
        assumptions: body.assumptions || {}
      };
      
      const pythonPath = process.env.PYTHON_PATH || 'python3';
      const scriptPath = path.join(process.cwd(), 'scripts', 'pwerm_analysis.py');
      
      const pythonProcess = spawn(pythonPath, [scriptPath], {
        env: {
          ...process.env,
          TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
          CLAUDE_API_KEY: process.env.CLAUDE_API_KEY || '',
          PYTHONUNBUFFERED: '1'
        }
      });
      
      let outputData = '';
      let errorData = '';
      
      // Send input
      pythonProcess.stdin.write(JSON.stringify(inputData));
      pythonProcess.stdin.end();
      
      // Stream progress updates
      pythonProcess.stderr.on('data', (data) => {
        const message = data.toString();
        errorData += message;
        
        // Send progress updates for specific messages
        if (message.includes('Starting market research') || 
            message.includes('Analyzing') ||
            message.includes('Generating scenarios')) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
            type: 'progress', 
            message: message.trim() 
          })}\n\n`));
        }
      });
      
      pythonProcess.stdout.on('data', (data) => {
        outputData += data.toString();
      });
      
      pythonProcess.on('close', (code) => {
        if (code !== 0) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
            type: 'error', 
            message: 'Analysis failed',
            details: errorData 
          })}\n\n`));
        } else {
          try {
            const jsonMatch = outputData.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
              const result = JSON.parse(jsonMatch[0]);
              
              // Send results in chunks
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                type: 'summary', 
                data: result.summary 
              })}\n\n`));
              
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                type: 'company_data', 
                data: result.company_data 
              })}\n\n`));
              
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                type: 'market_research', 
                data: result.market_research 
              })}\n\n`));
              
              // Send scenarios in batches
              const scenarios = result.scenarios || [];
              for (let i = 0; i < scenarios.length; i += 10) {
                controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                  type: 'scenarios_batch', 
                  data: scenarios.slice(i, i + 10),
                  batch: Math.floor(i / 10) + 1,
                  total_batches: Math.ceil(scenarios.length / 10)
                })}\n\n`));
              }
              
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
                type: 'complete', 
                message: 'Analysis complete' 
              })}\n\n`));
            }
          } catch (e) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ 
              type: 'error', 
              message: 'Failed to parse results',
              details: e instanceof Error ? e.message : 'Unknown error'
            })}\n\n`));
          }
        }
        
        controller.close();
      });
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