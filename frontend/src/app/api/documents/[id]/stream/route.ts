import { NextRequest } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const id = params.id;

  // Create SSE stream
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      let isClosed = false;

      const sendEvent = (data: any) => {
        if (isClosed) return;
        try {
          const event = `data: ${JSON.stringify(data)}\n\n`;
          controller.enqueue(encoder.encode(event));
        } catch (error) {
          console.error('Error sending SSE event:', error);
        }
      };

      const closeStream = () => {
        if (!isClosed) {
          isClosed = true;
          try {
            controller.close();
          } catch (error) {
            console.error('Error closing controller:', error);
          }
        }
      };

      // Send initial connection event
      sendEvent({ type: 'connected', message: 'Stream connected' });

      // Poll for status updates
      const pollStatus = async () => {
        try {
          const { data, error } = await supabaseService
            .from('processed_documents')
            .select('status, processing_summary, extracted_data, issue_analysis, comparables_analysis, raw_text_preview')
            .eq('id', id)
            .single();

          if (error) {
            sendEvent({ type: 'error', message: 'Failed to fetch status' });
            closeStream();
            return;
          }

          if (data.status === 'completed') {
            sendEvent({ 
              type: 'completed', 
              message: 'Analysis completed successfully',
              data: {
                extracted_data: data.extracted_data,
                issue_analysis: data.issue_analysis,
                comparables_analysis: data.comparables_analysis,
                raw_text_preview: data.raw_text_preview
              }
            });
            closeStream();
            return;
          }

          if (data.status === 'failed') {
            sendEvent({ type: 'error', message: 'Processing failed' });
            closeStream();
            return;
          }

          // Send progress update
          sendEvent({ 
            type: 'progress', 
            message: `Processing... Status: ${data.status}`,
            status: data.status
          });

          // Continue polling if not completed
          if (!isClosed) {
            setTimeout(pollStatus, 2000); // Poll every 2 seconds
          }

        } catch (error) {
          console.error('Polling error:', error);
          sendEvent({ type: 'error', message: 'Monitoring error' });
          closeStream();
        }
      };

      // Start polling
      pollStatus();

      // Handle client disconnect
      request.signal.addEventListener('abort', () => {
        closeStream();
      });
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Cache-Control'
    }
  });
} 