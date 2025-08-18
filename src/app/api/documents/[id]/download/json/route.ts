import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseKey);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    const { data, error } = await supabase
      .from('processed_documents')
      .select('*')
      .eq('id', id)
      .single();

    if (error || !data) {
      return NextResponse.json({ error: 'Document not found' }, { status: 404 });
    }

    if (data.status !== 'completed') {
      return NextResponse.json({ error: 'Analysis not completed' }, { status: 202 });
    }

    // Create JSON response
    const jsonData = {
      document_id: data.id,
      filename: data.storage_path?.split('/').pop() || 'Unknown',
      status: data.status,
      processed_at: data.processed_at,
      document_type: data.document_type,
      document_metadata: data.classification_details,
      extracted_data: data.extracted_data,
      issue_analysis: data.issue_analysis,
      comparables_analysis: data.comparables_analysis,
      processing_summary: data.processing_summary,
      raw_text_preview: data.raw_text_preview
    };

    const jsonString = JSON.stringify(jsonData, null, 2);
    const filename = `${data.storage_path?.split('/').pop()?.replace('.pdf', '') || 'analysis'}_results.json`;

    return new NextResponse(jsonString, {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': `attachment; filename="${filename}"`
      }
    });

  } catch (error) {
    console.error('Error downloading JSON:', error);
    return NextResponse.json({ error: 'Failed to download JSON' }, { status: 500 });
  }
} 