import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';

export async function POST(request: NextRequest) {
  try {
    const { code, context = {} } = await request.json();
    
    if (!code) {
      return NextResponse.json(
        { error: 'No code provided' },
        { status: 400 }
      );
    }
    
    // Create temporary Python file
    const tempId = crypto.randomBytes(8).toString('hex');
    const tempFile = path.join('/tmp', `agent_${tempId}.py`);
    
    // Prepare the Python code with context injection
    const fullCode = `
import json
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Context variables
context = ${JSON.stringify(context)}

# User code
${code}

# Ensure output is JSON serializable
if 'result' in locals():
    import numpy as np
    import pandas as pd
    
    def make_serializable(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        else:
            return obj
    
    result = make_serializable(result)
    print(json.dumps({'success': True, 'result': result}))
else:
    print(json.dumps({'success': True, 'message': 'Code executed successfully'}))
`;
    
    // Write code to temp file
    await fs.writeFile(tempFile, fullCode);
    
    // Execute Python code
    return new Promise((resolve) => {
      const python = spawn('python3', [tempFile]);
      let stdout = '';
      let stderr = '';
      
      python.stdout.on('data', (data) => {
        stdout += data.toString();
      });
      
      python.stderr.on('data', (data) => {
        stderr += data.toString();
      });
      
      python.on('close', async (code) => {
        // Clean up temp file
        try {
          await fs.unlink(tempFile);
        } catch (e) {
          console.error('Failed to delete temp file:', e);
        }
        
        if (code !== 0) {
          resolve(NextResponse.json(
            { 
              error: 'Python execution failed',
              stderr: stderr,
              code: code
            },
            { status: 500 }
          ));
          return;
        }
        
        try {
          // Try to parse JSON output
          const lastLine = stdout.trim().split('\n').pop();
          if (lastLine && lastLine.startsWith('{')) {
            const result = JSON.parse(lastLine);
            resolve(NextResponse.json(result));
          } else {
            // Return raw output if not JSON
            resolve(NextResponse.json({
              success: true,
              output: stdout,
              type: 'text'
            }));
          }
        } catch (parseError) {
          // Return raw output if parsing fails
          resolve(NextResponse.json({
            success: true,
            output: stdout,
            type: 'text'
          }));
        }
      });
      
      // Set timeout
      setTimeout(() => {
        python.kill();
        resolve(NextResponse.json(
          { error: 'Python execution timeout (30s)' },
          { status: 500 }
        ));
      }, 30000);
    });
    
  } catch (error) {
    console.error('Python execution error:', error);
    return NextResponse.json(
      { error: 'Failed to execute Python code' },
      { status: 500 }
    );
  }
}