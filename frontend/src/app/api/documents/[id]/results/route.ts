import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * @swagger
 * /api/documents/{id}/results:
 *   get:
 *     summary: Get document analysis results
 *     description: Retrieve the processed content and extracted metrics from a document
 *     tags:
 *       - Documents
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         description: Document UUID
 *         schema:
 *           type: string
 *           format: uuid
 *     responses:
 *       200:
 *         description: Analysis results retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 document:
 *                   $ref: '#/components/schemas/DocumentMetadata'
 *                 analysis:
 *                   type: object
 *                   properties:
 *                     text_content:
 *                       type: string
 *                       description: Extracted text from the document
 *                     key_metrics:
 *                       type: object
 *                       description: Extracted financial and business metrics
 *                     processing_date:
 *                       type: string
 *                       format: date-time
 *                 summary:
 *                   type: object
 *                   description: High-level summary of extracted information
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

    // Check if document has been processed
    if (data.status !== 'completed') {
      return NextResponse.json({ 
        error: 'Document processing not completed',
        status: data.status 
      }, { status: 400 });
    }

    // Return analysis results
    const response = {
      document: {
        id: data.id.toString(),
        filename: data.storage_path.split('/').pop() || 'Unknown',
        file_type: 'application/pdf',
        file_size: data.file_size || 'Unknown',
        upload_date: data.processed_at,
        processed: data.status === 'completed',
        document_type: data.document_type || 'other'
      },
      analysis: {
        text_content: data.raw_text_preview || '',
        key_metrics: data.extracted_data || {},
        processing_date: data.processed_at,
        processing_summary: data.processing_summary || {}
      },
      summary: {
        document_type: data.document_type,
        processing_status: data.status,
        text_length: data.raw_text_preview ? data.raw_text_preview.length : 0,
        has_metrics: !!data.extracted_data,
        processing_time: data.processing_time || 'Unknown'
      }
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Failed to fetch document results' }, { status: 500 });
  }
} 