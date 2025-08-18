import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import * as dotenv from 'dotenv';

// Load environment variables
dotenv.config({ path: path.join(process.cwd(), '.env.local') });

export async function GET(request: NextRequest) {
  return new Promise((resolve) => {
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    
    // Test Python with a simple command that checks environment
    const testScript = `
import os
import json
import sys

result = {
    "python_version": sys.version,
    "has_tavily_key": bool(os.getenv('TAVILY_API_KEY')),
    "has_claude_key": bool(os.getenv('CLAUDE_API_KEY')),
    "tavily_key_length": len(os.getenv('TAVILY_API_KEY', '')),
    "claude_key_length": len(os.getenv('CLAUDE_API_KEY', '')),
    "working_directory": os.getcwd(),
    "env_vars_count": len(os.environ),
    "path_exists": os.path.exists('scripts/pwerm_analysis.py')
}

print(json.dumps(result, indent=2))
`;

    const pythonProcess = spawn(pythonPath, ['-c', testScript], {
      env: {
        ...process.env,
        TAVILY_API_KEY: process.env.TAVILY_API_KEY || '',
        CLAUDE_API_KEY: process.env.CLAUDE_API_KEY || '',
        PYTHONUNBUFFERED: '1'
      },
      cwd: process.cwd()
    });

    let output = '';
    let error = '';

    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      error += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0) {
        resolve(NextResponse.json({
          success: false,
          error: error || 'Python test failed',
          code
        }, { status: 500 }));
        return;
      }

      try {
        const result = JSON.parse(output);
        resolve(NextResponse.json({
          success: true,
          ...result
        }));
      } catch (e) {
        resolve(NextResponse.json({
          success: false,
          error: 'Failed to parse Python output',
          output,
          parseError: e instanceof Error ? e.message : 'Unknown error'
        }, { status: 500 }));
      }
    });
  });
}