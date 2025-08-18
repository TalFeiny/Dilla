import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const jobId = searchParams.get('job_id');
    
    if (jobId) {
      // Get specific job status
      const pythonProcess = spawn('python3', [
        'scripts/document_queue_processor.py',
        '--status',
        jobId
      ]);

      let output = '';
      pythonProcess.stdout.on('data', (data: Buffer) => {
        output += data.toString();
      });

      await new Promise((resolve, reject) => {
        pythonProcess.on('close', (code: number) => {
          if (code === 0) {
            resolve(null);
          } else {
            reject(new Error(`Python process exited with code ${code}`));
          }
        });
      });

      try {
        const jobData = JSON.parse(output);
        return NextResponse.json({
          success: true,
          job: jobData
        });
      } catch (parseError) {
        return NextResponse.json({
          success: false,
          error: 'Job not found or invalid response',
          raw_output: output
        });
      }
    } else {
      // Get queue statistics
      const pythonProcess = spawn('python3', [
        'scripts/document_queue_processor.py',
        '--stats'
      ]);

      let output = '';
      pythonProcess.stdout.on('data', (data: Buffer) => {
        output += data.toString();
      });

      await new Promise((resolve, reject) => {
        pythonProcess.on('close', (code: number) => {
          if (code === 0) {
            resolve(null);
          } else {
            reject(new Error(`Python process exited with code ${code}`));
          }
        });
      });

      try {
        const stats = JSON.parse(output);
        return NextResponse.json({
          success: true,
          queue_stats: stats,
          timestamp: new Date().toISOString()
        });
      } catch (parseError) {
        return NextResponse.json({
          success: false,
          error: 'Failed to parse queue statistics',
          raw_output: output
        });
      }
    }
  } catch (error) {
    console.error('Queue status error:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to get queue status' 
    }, { status: 500 });
  }
} 