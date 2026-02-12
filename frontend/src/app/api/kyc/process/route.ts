import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { resolveScriptPath } from '@/lib/scripts-path';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { document_path } = body;

    if (!document_path) {
      return NextResponse.json(
        { error: 'Missing document_path' },
        { status: 400 }
      );
    }

    // Sanitize document_path to prevent path traversal
    const sanitized = path.basename(document_path);
    if (sanitized !== document_path || document_path.includes('..') || document_path.includes('/') || document_path.includes('\\')) {
      return NextResponse.json(
        { error: 'Invalid document_path: must be a plain filename with no directory traversal' },
        { status: 400 }
      );
    }

    const { path: scriptPath, tried } = resolveScriptPath('kyc_processor.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `KYC script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const scriptsDir = path.dirname(scriptPath);

    // Run the Python script with sanitized path
    const result = await runPythonScript(scriptPath, [sanitized], scriptsDir);

    if (result.success) {
      return NextResponse.json(result.data);
    } else {
      return NextResponse.json(
        { error: result.error },
        { status: 500 }
      );
    }

  } catch (error) {
    console.error('KYC processing error:', error);
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