import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * @swagger
 * /api/documents/{id}/status:
 *   get:
 *     summary: Get document processing status
 *     description: Check the current processing status of a document
 *     tags:
 *       - Documents
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *           format: uuid
 *     responses:
 *       200:
 *         description: Status retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 document_id:
 *                   type: string
 *                 filename:
 *                   type: string
 *                 status:
 *                   type: string
 *                   enum: [pending, processing, completed, failed]
 *                 uploaded_at:
 *                   type: string
 *                   format: date-time
 *                 processing_time:
 *                   type: string
 *                   description: Time taken to process (if completed)
 *                 progress:
 *                   type: object
 *                   properties:
 *                     current_step:
 *                       type: string
 *                     total_steps:
 *                       type: integer
 *                     percentage:
 *                       type: number
 *       404:
 *         description: Document not found
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Error'
 *       500:
 *         description: Internal server error
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Error'
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }

    const { data, error } = await supabaseService
      .from('processed_documents')
      .select('*')
      .eq('id', parseInt(id))
      .single();

    if (error || !data) {
      return NextResponse.json({ error: 'Document not found' }, { status: 404 });
    }

    // Calculate processing time if completed
    let processingTime = null;
    if (data.status === 'completed' && data.processed_at && data.created_at) {
      const startTime = new Date(data.created_at);
      const endTime = new Date(data.processed_at);
      const diffMs = endTime.getTime() - startTime.getTime();
      processingTime = `${Math.round(diffMs / 1000)}s`;
    }

    // Determine progress based on status
    let progress = {
      current_step: 'unknown',
      total_steps: 5,
      percentage: 0
    };

    switch (data.status) {
      case 'pending':
        progress = { current_step: 'queued', total_steps: 5, percentage: 0 };
        break;
      case 'processing':
        progress = { current_step: 'processing', total_steps: 5, percentage: 50 };
        break;
      case 'completed':
        progress = { current_step: 'completed', total_steps: 5, percentage: 100 };
        break;
      case 'failed':
        progress = { current_step: 'failed', total_steps: 5, percentage: 0 };
        break;
    }

    const response = {
      document_id: data.id.toString(),
      filename: data.storage_path.split('/').pop() || 'Unknown',
      status: data.status || 'pending',
      uploaded_at: data.created_at,
      processing_time: processingTime,
      progress,
      document_type: data.document_type || 'unknown',
      job_id: data.job_id || null
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Failed to fetch document status' }, { status: 500 });
  }
} 