import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: path.join(process.cwd(), '.env.local') });

export async function POST(request: NextRequest) {
  const body = await request.json();
  
  // Minimal test data
  const testInput = {
    company_data: {
      name: body.company_name || 'TestCo',
      current_arr_usd: (body.current_arr || 5) * 1000000, // Convert to dollars
      revenue_growth_annual_pct: (body.growth_rate || 0.30) * 100,
      sector: body.sector || 'SaaS'
    },
    assumptions: {}
  };

  console.log('Test PWERM input:', JSON.stringify(testInput, null, 2));

  return new Promise((resolve) => {
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
    let outputChunks: string[] = [];

    // Send input
    pythonProcess.stdin.write(JSON.stringify(testInput));
    pythonProcess.stdin.end();

    pythonProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      outputChunks.push(chunk);
      outputData += chunk;
      console.log('Python stdout chunk:', chunk.substring(0, 200));
    });

    pythonProcess.stderr.on('data', (data) => {
      const chunk = data.toString();
      errorData += chunk;
      console.log('Python stderr:', chunk);
    });

    // Add a timeout
    const timeout = setTimeout(() => {
      pythonProcess.kill();
      resolve(NextResponse.json({
        error: 'Timeout',
        details: 'PWERM analysis took too long',
        partialOutput: outputData.substring(0, 1000),
        errorOutput: errorData.substring(0, 1000)
      }, { status: 504 }));
    }, 60000); // 1 minute timeout for testing

    pythonProcess.on('close', (code) => {
      clearTimeout(timeout);
      
      console.log(`Process exited with code: ${code}`);
      console.log(`Total output length: ${outputData.length}`);
      console.log(`Total error length: ${errorData.length}`);
      
      if (code !== 0) {
        resolve(NextResponse.json({
          error: 'Python script failed',
          code,
          errorOutput: errorData,
          partialOutput: outputData.substring(0, 1000),
          chunks: outputChunks.length
        }, { status: 500 }));
        return;
      }

      // Try to find JSON in output
      try {
        const jsonMatch = outputData.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const result = JSON.parse(jsonMatch[0]);
          console.log('Successfully parsed PWERM result');
          resolve(NextResponse.json(result));
        } else {
          // If no JSON found, try parsing the whole output
          const result = JSON.parse(outputData.trim());
          resolve(NextResponse.json(result));
        }
      } catch (e) {
        resolve(NextResponse.json({
          error: 'Failed to parse output',
          parseError: e instanceof Error ? e.message : 'Unknown',
          outputLength: outputData.length,
          firstChars: outputData.substring(0, 500),
          lastChars: outputData.substring(Math.max(0, outputData.length - 500))
        }, { status: 500 }));
      }
    });
  });
}