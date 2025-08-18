import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

if (!supabaseService) {
  throw new Error('Supabase service not configured');
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const { documentId, filePath, documentType } = await request.json();

    if (!documentId || !filePath) {
      return NextResponse.json({ error: 'Missing required parameters' }, { status: 400 });
    }

    // Update status to processing
    await supabaseService
      .from('processed_documents')
      .update({ 
        status: 'processing',
        processing_summary: { started: true, timestamp: new Date().toISOString() }
      })
      .eq('id', documentId);

    // Download file from Supabase storage
    console.log('Attempting to download file:', filePath);
    let { data: fileData, error: downloadError } = await supabaseService.storage
      .from('documents')
      .download(filePath);

    if (downloadError || !fileData) {
      console.error('Failed to download file:', downloadError);
      
      // Try alternative path if the file is in a subdirectory
      const fileName = filePath.split('/').pop();
      if (fileName && filePath !== fileName) {
        console.log('Trying alternative download path:', fileName);
        const { data: altFileData, error: altDownloadError } = await supabaseService.storage
          .from('documents')
          .download(fileName);
        
        if (altDownloadError || !altFileData) {
          console.error('Alternative download also failed:', altDownloadError);
          await supabaseService
            .from('processed_documents')
            .update({ 
              status: 'failed',
              processing_summary: { error: 'Failed to download file from storage', details: downloadError }
            })
            .eq('id', documentId);
          return NextResponse.json({ error: 'Failed to download file' }, { status: 500 });
        }
        
        // Use the alternative file data
        fileData = altFileData;
      } else {
        await supabaseService
          .from('processed_documents')
          .update({ 
            status: 'failed',
            processing_summary: { error: 'Failed to download file from storage', details: downloadError }
          })
          .eq('id', documentId);
        return NextResponse.json({ error: 'Failed to download file' }, { status: 500 });
      }
    }

    // Save file locally for processing
    const uploadsDir = path.join(process.cwd(), 'uploads');
    if (!fs.existsSync(uploadsDir)) {
      fs.mkdirSync(uploadsDir, { recursive: true });
    }

    const localFilePath = path.join(uploadsDir, path.basename(filePath));
    
    // Fix: Convert Blob to Buffer before writing
    console.log('Saving file locally:', localFilePath);
    const arrayBuffer = await fileData.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    fs.writeFileSync(localFilePath, buffer);
    console.log('File saved successfully');

    // Call Python script for processing - use full_flow_no_comp.py for proper processing
    const pythonScriptPath = path.join(process.cwd(), 'scripts', 'full_flow_no_comp.py');
    
    if (!fs.existsSync(pythonScriptPath)) {
      console.error('Python script not found:', pythonScriptPath);
      await supabaseService
        .from('processed_documents')
        .update({ 
          status: 'failed',
          processing_summary: { error: 'Python script not found' }
        })
        .eq('id', documentId);
      return NextResponse.json({ error: 'Processing script not found' }, { status: 500 });
    }

    // Run Python script with proper environment variables
    console.log('Starting Python script:', pythonScriptPath);
    console.log('With file:', localFilePath);
    
    const env = {
      ...process.env,
      PYTHONPATH: path.join(process.cwd(), 'scripts'),
      DOCUMENT_ID: documentId.toString(),
      DOCUMENT_TYPE: documentType || 'other',
      // Pass environment variables that the Python script expects
      NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
      SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
      SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL, // Alternative name
      SUPABASE_SERVICE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY, // Alternative name
      // Add API keys
      OPENAI_API_KEY: process.env.OPENAI_API_KEY,
      TAVILY_API_KEY: process.env.TAVILY_API_KEY,
      CLAUDE_API_KEY: process.env.CLAUDE_API_KEY,
      ANTHROPIC_API_KEY: process.env.CLAUDE_API_KEY, // Alias for compatibility
      // Set working directory for .env.local file
      PWD: process.cwd()
    };

    const pythonProcess = spawn('python3', [
      pythonScriptPath,
      '--process-file', localFilePath,
      documentId,
      documentType || 'other'
    ], {
      cwd: path.join(process.cwd(), 'scripts'),
      env: env
    });

    let output = '';
    let errorOutput = '';

    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
      // Only log first 200 chars to avoid cluttering logs with full JSON
      const preview = data.toString().substring(0, 200);
      console.log('Python stdout:', preview + (data.toString().length > 200 ? '...' : ''));
    });

    pythonProcess.stderr.on('data', (data) => {
      // Stderr is for logging, not errors necessarily
      const stderrMsg = data.toString();
      errorOutput += stderrMsg;
      console.log('Python logs:', stderrMsg);
    });

    console.log('Python process started with PID:', pythonProcess.pid);
    console.log('Python script path:', pythonScriptPath);
    console.log('Local file path:', localFilePath);
    console.log('Environment variables:', {
      SUPABASE_URL: env.SUPABASE_URL ? 'SET' : 'NOT SET',
      SUPABASE_SERVICE_KEY: env.SUPABASE_SERVICE_KEY ? 'SET' : 'NOT SET',
      OPENAI_API_KEY: env.OPENAI_API_KEY ? 'SET' : 'NOT SET',
      TAVILY_API_KEY: env.TAVILY_API_KEY ? 'SET' : 'NOT SET'
    });

    return new Promise((resolve) => {
      pythonProcess.on('close', async (code) => {
        console.log(`Python process exited with code ${code}`);
        
        if (code === 0) {
          // Success - update database with results
          console.log('Python process completed successfully');
          console.log('Raw output length:', output.length);
          console.log('Raw output preview:', output.substring(0, 500));
          
          try {
            // Clean output - remove any non-JSON content
            const cleanedOutput = output.trim();
            
            // Try to extract JSON from the output
            let result;
            const jsonMatch = cleanedOutput.match(/\{[\s\S]*\}$/);
            if (jsonMatch) {
              result = JSON.parse(jsonMatch[0]);
            } else {
              result = JSON.parse(cleanedOutput);
            }
            
            console.log('JSON parsed successfully');
            await supabaseService
              .from('processed_documents')
              .update({ 
                status: 'completed',
                processed_at: new Date().toISOString(),
                classification_details: result.document_metadata || {},
                extracted_data: result.extracted_data || {},
                issue_analysis: result.issue_analysis || {},
                comparables_analysis: result.comparables_analysis || {},
                raw_text_preview: result.raw_text_preview || '',
                processing_summary: {
                  success: true,
                  processing_time: result.processing_time || 'unknown',
                  extracted_metrics: Object.keys(result.extracted_data || {}).length,
                  document_type: result.document_metadata?.document_type || 'unknown'
                }
              })
              .eq('id', documentId);

            resolve(NextResponse.json({ 
              success: true, 
              message: 'Document processed successfully',
              result 
            }));
          } catch (parseError) {
            console.error('Error parsing Python output:', parseError);
            console.error('Raw output (first 500 chars):', output.substring(0, 500));
            console.error('Raw output (last 500 chars):', output.substring(Math.max(0, output.length - 500)));
            
            await supabaseService
              .from('processed_documents')
              .update({ 
                status: 'failed',
                processing_summary: { 
                  error: 'Failed to parse processing results',
                  parseError: parseError.message,
                  outputPreview: output.substring(0, 1000)
                }
              })
              .eq('id', documentId);
            resolve(NextResponse.json({ 
              error: 'Failed to parse processing results',
              details: parseError.message,
              outputPreview: output.substring(0, 500)
            }, { status: 500 }));
          }
        } else {
          // Error - update database
          await supabaseService
            .from('processed_documents')
            .update({ 
              status: 'failed',
              processing_summary: { error: errorOutput || 'Processing failed', exit_code: code }
            })
            .eq('id', documentId);
          
          resolve(NextResponse.json({ 
            error: 'Document processing failed',
            details: errorOutput 
          }, { status: 500 }));
        }

        // Clean up local file
        try {
          if (fs.existsSync(localFilePath)) {
            fs.unlinkSync(localFilePath);
          }
        } catch (cleanupError) {
          console.error('Error cleaning up local file:', cleanupError);
        }
      });
    });

  } catch (error) {
    console.error('Processing error:', error);
    return NextResponse.json({ error: 'Processing failed' }, { status: 500 });
  }
} 