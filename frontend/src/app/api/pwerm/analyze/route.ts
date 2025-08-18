import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    if (!body || Object.keys(body).length === 0) {
      return NextResponse.json(
        { error: 'No data provided' },
        { status: 400 }
      );
    }

    // Get the absolute path to the script
    const scriptsDir = path.join(process.cwd(), 'scripts');
    const scriptPath = path.join(scriptsDir, 'pwerm_analysis.py');

    // Create temporary input file
    const tempInputFile = path.join(scriptsDir, `temp_pwerm_input_${Date.now()}.json`);
    
    try {
      fs.writeFileSync(tempInputFile, JSON.stringify(body));

      // Run the Python script
      const result = await runPythonScript(scriptPath, [
        '--input-file', tempInputFile
      ], scriptsDir);

      if (result.success) {
        return NextResponse.json(result.data);
      } else {
        return NextResponse.json(
          { error: result.error },
          { status: 500 }
        );
      }
    } finally {
      // Clean up temp file
      if (fs.existsSync(tempInputFile)) {
        fs.unlinkSync(tempInputFile);
      }
    }

  } catch (error) {
    console.error('PWERM analysis error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

function runPythonScript(
  scriptPath: string, 
  args: string[], 
  cwd: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  return new Promise((resolve) => {
    const pythonProcess = spawn('python', [scriptPath, ...args], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve({ success: true, data: result });
        } catch (parseError) {
          resolve({ 
            success: false, 
            error: `Failed to parse script output: ${parseError}` 
          });
        }
      } else {
        resolve({ 
          success: false, 
          error: `Script failed with code ${code}: ${stderr}` 
        });
      }
    });

    pythonProcess.on('error', (error) => {
      resolve({ 
        success: false, 
        error: `Failed to start script: ${error.message}` 
      });
    });
  });
} 