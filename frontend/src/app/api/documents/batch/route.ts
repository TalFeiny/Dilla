import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { getBackendUrl } from '@/lib/backend-url';

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB per file

function inferDocumentType(fileName: string, formType: string | null): string {
  if (formType) return formType;
  const name = fileName.toLowerCase();
  if (name.includes('memo')) return 'investment_memo';
  if (name.includes('pitch')) return 'pitch_deck';
  if (name.includes('board')) return 'board_deck';
  if (name.includes('update')) return 'monthly_update';
  return 'other';
}

/**
 * POST /api/documents/batch
 * Upload multiple files at once; insert each into processed_documents with company_id/fund_id.
 * Returns immediately with document ids; processing runs in background via /api/documents/process-batch-async.
 */
export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json(
        {
          error: 'Database connection not available',
          details: { message: 'Missing Supabase env vars' },
        },
        { status: 503 }
      );
    }

    const formData = await request.formData();
    const companyId = (formData.get('company_id') as string) || null;
    const fundId = (formData.get('fund_id') as string) || null;
    const formDocumentType = (formData.get('document_type') as string) || null;

    // Collect all files: multiple "file" or "files" parts
    const files: File[] = [];
    for (const key of ['file', 'files']) {
      const parts = formData.getAll(key);
      for (const p of parts) {
        if (p instanceof File) files.push(p);
      }
    }
    if (files.length === 0) {
      return NextResponse.json({ error: 'No files uploaded' }, { status: 400 });
    }

    const results: { id: string; filename: string; storage_path: string; document_type: string }[] = [];
    const backendUrl = getBackendUrl();

    for (const file of files) {
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { error: `File too large: ${file.name}. Max 100MB per file.` },
          { status: 400 }
        );
      }

      const timestamp = Date.now();
      const filePath = `${timestamp}/${file.name}`;

      const { error: uploadError } = await supabaseService.storage
        .from('documents')
        .upload(filePath, file);

      if (uploadError) {
        console.error('Batch upload error:', uploadError);
        return NextResponse.json(
          { error: 'Failed to upload file to storage', details: uploadError.message },
          { status: 500 }
        );
      }

      const documentType = inferDocumentType(file.name, formDocumentType);
      const insertPayload: Record<string, unknown> = {
        storage_path: filePath,
        status: 'pending',
        document_type: documentType,
        processing_summary: {
          file_name: file.name,
          file_size: file.size,
          file_type: file.type,
          uploaded_at: new Date().toISOString(),
        },
      };
      if (companyId) insertPayload.company_id = companyId;
      if (fundId) insertPayload.fund_id = fundId;

      const { data: row, error: insertError } = await supabaseService
        .from('processed_documents')
        .insert(insertPayload)
        .select('id, storage_path, document_type')
        .single();

      if (insertError || !row) {
        console.error('Batch insert error:', insertError);
        try {
          await supabaseService.storage.from('documents').remove([filePath]);
        } catch (_) {}
        return NextResponse.json(
          { error: 'Failed to save document metadata', details: insertError?.message },
          { status: 500 }
        );
      }

      results.push({
        id: String(row.id),
        filename: file.name,
        storage_path: row.storage_path,
        document_type: row.document_type,
      });
    }

    // Process in background: single parallel batch call (deck agent pattern)
    const docsPayload = results.map((r) => ({
      document_id: String(r.id),
      file_path: r.storage_path,
      document_type: r.document_type,
      company_id: companyId,
      fund_id: fundId,
    }));

    (async () => {
      try {
        await fetch(`${backendUrl}/api/documents/process-batch-async`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ documents: docsPayload }),
        });
      } catch (e) {
        console.error('Batch process error', e);
      }
    })();

    return NextResponse.json({
      success: true,
      documentIds: results.map((r) => r.id),
      documents: results,
      message: `Uploaded ${results.length} document(s); processing queued in background.`,
    });
  } catch (error: unknown) {
    console.error('Batch upload error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
