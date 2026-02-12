import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * @swagger
 * /api/documents/{id}:
 *   get:
 *     summary: Get document by ID
 *     description: Retrieve detailed information about a specific document
 *     tags: [Documents]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Document ID
 *     responses:
 *       200:
 *         description: Document details retrieved successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 document:
 *                   $ref: '#/components/schemas/Document'
 *                 content:
 *                   type: object
 *                   properties:
 *                     text_available:
 *                       type: boolean
 *                     text_length:
 *                       type: integer
 *                     has_metrics:
 *                       type: boolean
 *                 links:
 *                   type: object
 *                   properties:
 *                     results:
 *                       type: string
 *                     status:
 *                       type: string
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
 *   delete:
 *     summary: Delete document
 *     description: Delete a specific document from the system
 *     tags: [Documents]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *         description: Document ID to delete
 *     responses:
 *       200:
 *         description: Document deleted successfully
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                 message:
 *                   type: string
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

    // Return user-friendly document info
    const response = {
      document: {
        id: data.id.toString(),
        filename: data.storage_path.split('/').pop() || 'Unknown',
        file_type: 'application/pdf',
        file_size: 'Unknown',
        document_type: data.document_type || 'other',
        upload_date: data.processed_at,
        processed: data.status === 'completed'
      },
      content: {
        text_available: !!data.raw_text_preview,
        text_length: data.raw_text_preview ? data.raw_text_preview.length : 0,
        has_metrics: !!data.extracted_data
      },
      links: {
        results: `/api/documents/${id}/results`,
        status: `/api/documents/${id}/status`
      }
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Failed to fetch document' }, { status: 500 });
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }

    const body = await request.json();
    const { company_id, fund_id } = body as { company_id?: string; fund_id?: string };

    const updates: Record<string, unknown> = {};
    if (company_id != null) updates.company_id = company_id;
    if (fund_id != null) updates.fund_id = fund_id;

    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ error: 'Provide company_id and/or fund_id to link document' }, { status: 400 });
    }

    const { data, error } = await supabaseService
      .from('processed_documents')
      .update(updates)
      .eq('id', parseInt(id))
      .select()
      .single();

    if (error) {
      console.error('PATCH document error:', error);
      return NextResponse.json({ error: 'Failed to update document' }, { status: 500 });
    }

    return NextResponse.json({ success: true, document: data });
  } catch (error) {
    console.error('PATCH document error:', error);
    return NextResponse.json({ error: 'Failed to update document' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }

    const { error } = await supabaseService
      .from('processed_documents')
      .delete()
      .eq('id', parseInt(id));

    if (error) {
      console.error('Database error:', error);
      return NextResponse.json({ error: 'Failed to delete document' }, { status: 500 });
    }

    return NextResponse.json({ success: true, message: 'Document deleted successfully' });
  } catch (error) {
    console.error('Delete error:', error);
    return NextResponse.json({ error: 'Failed to delete document' }, { status: 500 });
  }
} 