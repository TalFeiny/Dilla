import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { resolveScriptPath } from '@/lib/scripts-path';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { document_path, document_id, document_type } = body;

    if (!document_path || !document_id || !document_type) {
      return NextResponse.json(
        { error: 'Missing required fields: document_path, document_id, document_type' },
        { status: 400 }
      );
    }

    const { path: scriptPath, tried } = resolveScriptPath('full_flow_no_comp.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `Document script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const scriptsDir = path.dirname(scriptPath);

    // Run the Python script
    console.log('Running Python script with args:', {
      scriptPath,
      document_path,
      document_id,
      document_type,
      cwd: scriptsDir
    });
    
    const result = await runPythonScript(scriptPath, [
      '--process-file', document_path,
      document_id,
      document_type
    ], scriptsDir);

    if (result.success) {
      return NextResponse.json(result.data);
    } else {
      return NextResponse.json(
        { error: result.error },
        { status: 500 }
      );
    }

  } catch (error) {
    console.error('Document processing error:', error);
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
    const pythonProcess = spawn('python3', [scriptPath, ...args], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
      console.log('Python stdout:', data.toString());
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
      console.error('Python stderr:', data.toString());
    });

    pythonProcess.on('close', (code) => {
      console.log('Python process closed with code:', code);
      console.log('Python stdout length:', stdout.length);
      console.log('Python stderr length:', stderr.length);
      
      if (code === 0) {
        try {
          // The Python script outputs the final JSON result on the last line
          const lines = stdout.split('\n');
          const lastLine = lines[lines.length - 1].trim();
          
          try {
            const result = JSON.parse(lastLine);
            if (result.success !== undefined) {
              console.log('Successfully parsed JSON result');
              resolve({ success: true, data: result });
            } else {
              console.log('JSON parsed but no success field found');
              resolve({ 
                success: false, 
                error: `Invalid result format from script` 
              });
            }
          } catch (parseError) {
            console.log('JSON parse error on last line:', parseError);
            console.log('Last line:', lastLine);
            resolve({ 
              success: false, 
              error: `Failed to parse script output: ${parseError}` 
            });
          }
        } catch (parseError) {
          console.log('JSON parse error:', parseError);
          console.log('Raw stdout (last 1000 chars):', stdout.slice(-1000));
          resolve({ 
            success: false, 
            error: `Failed to parse script output: ${parseError}` 
          });
        }
      } else {
        console.log('Script failed with stderr:', stderr);
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