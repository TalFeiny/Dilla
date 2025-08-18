import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

// Configure runtime for longer execution
export const maxDuration = 60; // 1 minute for agent operations

interface CrewAnalysisRequest {
  company_name: string;
  current_arr: number;  // in millions
  growth_rate: number;  // as decimal (0.8 = 80%)
  sector: string;
  analysis_type?: 'full' | 'quick';
}

export async function POST(request: NextRequest) {
  try {
    const body: CrewAnalysisRequest = await request.json();
    
    // Validate inputs
    if (!body.company_name || !body.sector) {
      return NextResponse.json(
        { error: 'Company name and sector are required' },
        { status: 400 }
      );
    }

    const analysisType = body.analysis_type || 'quick';
    
    // Prepare environment variables
    const env = {
      ...process.env,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY || '',
      TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
      PYTHONUNBUFFERED: '1'
    };

    // Execute CrewAI Python script
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    const scriptPath = path.join(process.cwd(), 'scripts', 'crewai_agents.py');
    
    return new Promise((resolve) => {
      const pythonProcess = spawn(
        pythonPath,
        [
          scriptPath,
          body.company_name,
          String(body.current_arr || 10),
          String(body.growth_rate || 0.5),
          body.sector
        ],
        {
          env,
          cwd: process.cwd()
        }
      );

      let outputData = '';
      let errorData = '';
      let isResolved = false;

      // Collect output
      pythonProcess.stdout.on('data', (data) => {
        outputData += data.toString();
        
        // Stream progress updates if verbose output detected
        const lines = data.toString().split('\n');
        for (const line of lines) {
          if (line.includes('Working Agent:') || line.includes('Starting Task:')) {
            console.log('[CrewAI Progress]', line);
          }
        }
      });

      pythonProcess.stderr.on('data', (data) => {
        errorData += data.toString();
        console.error('[CrewAI Error]', data.toString());
      });
      
      // Add timeout handler
      const timeout = setTimeout(() => {
        if (!isResolved) {
          pythonProcess.kill();
          isResolved = true;
          resolve(NextResponse.json(
            { 
              error: 'Analysis timeout', 
              details: 'CrewAI analysis took too long to complete',
              partialOutput: outputData.substring(0, 1000)
            },
            { status: 504 }
          ));
        }
      }, 55000); // 55 seconds (slightly less than maxDuration)

      pythonProcess.on('close', (code) => {
        if (isResolved) return;
        
        clearTimeout(timeout);
        isResolved = true;
        
        if (code !== 0) {
          console.error('CrewAI process exited with code:', code);
          resolve(NextResponse.json(
            { 
              error: 'Analysis failed', 
              details: errorData || 'CrewAI script exited with error',
              code,
              partialOutput: outputData.substring(0, 500)
            },
            { status: 500 }
          ));
          return;
        }

        try {
          // Parse JSON output
          const jsonMatch = outputData.match(/\{[\s\S]*\}/);
          const result = JSON.parse(jsonMatch ? jsonMatch[0] : outputData);
          
          resolve(NextResponse.json({
            success: true,
            ...result
          }));
        } catch (parseError) {
          console.error('Failed to parse CrewAI output:', parseError);
          resolve(NextResponse.json(
            { 
              error: 'Failed to parse analysis results',
              details: outputData.substring(0, 1000)
            },
            { status: 500 }
          ));
        }
      });

      pythonProcess.on('error', (error) => {
        if (isResolved) return;
        
        clearTimeout(timeout);
        isResolved = true;
        
        console.error('Failed to start CrewAI process:', error);
        resolve(NextResponse.json(
          { 
            error: 'Failed to start analysis',
            details: error.message
          },
          { status: 500 }
        ));
      });
    });

  } catch (error) {
    console.error('CrewAI API error:', error);
    return NextResponse.json(
      { 
        error: 'Internal server error',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}