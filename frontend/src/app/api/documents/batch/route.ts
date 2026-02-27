import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB per file

function inferDocumentType(fileName: string, formType: string | null): string {
  if (formType) return formType;
  const name = fileName.toLowerCase();
  if (name.includes('memo')) return 'investment_memo';
  return 'company_update';
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

    const backendUrl = getBackendUrl();

    // Validate file sizes up-front before any uploads
    for (const file of files) {
      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { error: `File too large: ${file.name}. Max 100MB per file.` },
          { status: 400 }
        );
      }
    }

    // Upload all files in parallel — each file: storage upload + DB insert
    const uploadResults = await Promise.allSettled(
      files.map(async (file) => {
        const timestamp = Date.now();
        const filePath = `${timestamp}/${file.name}`;

        const { error: uploadError } = await supabaseService.storage
          .from('documents')
          .upload(filePath, file);

        if (uploadError) {
          throw new Error(`Upload failed for ${file.name}: ${uploadError.message}`);
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
          // Clean up uploaded file on DB insert failure
          try {
            await supabaseService.storage.from('documents').remove([filePath]);
          } catch (_) {}
          throw new Error(`DB insert failed for ${file.name}: ${insertError?.message}`);
        }

        return {
          id: String(row.id),
          filename: file.name,
          storage_path: row.storage_path,
          document_type: row.document_type,
        };
      })
    );

    // Collect successes, log failures
    const results: { id: string; filename: string; storage_path: string; document_type: string }[] = [];
    const errors: string[] = [];
    for (const r of uploadResults) {
      if (r.status === 'fulfilled') {
        results.push(r.value);
      } else {
        console.error('Batch upload item failed:', r.reason);
        errors.push(String(r.reason));
      }
    }

    if (results.length === 0) {
      return NextResponse.json(
        { error: 'All uploads failed', details: errors },
        { status: 500 }
      );
    }

    // Kick off processing via streaming batch endpoint — returns per-doc progress.
    // Falls back to sync batch, then async Celery if both fail.
    const docsPayload = results.map((r) => ({
      document_id: String(r.id),
      file_path: r.storage_path,
      document_type: r.document_type,
      company_id: companyId,
      fund_id: fundId,
    }));

    let processingDone = false;
    let processedCount = 0;
    // Track which document IDs were successfully processed so fallbacks
    // only send unprocessed ones — prevents duplicate processing.
    const processedDocIds = new Set<string>();

    // Try streaming endpoint first (best UX — per-doc progress)
    try {
      const streamRes = await fetch(`${backendUrl}/api/documents/process-batch-stream`, {
        method: 'POST',
        headers: getBackendHeaders(),
        body: JSON.stringify({ documents: docsPayload }),
        signal: AbortSignal.timeout(600_000), // 10 min for streaming
      });
      if (streamRes.ok && streamRes.body) {
        const reader = streamRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);
              if (event.type === 'result' && event.success && event.document_id) {
                processedCount++;
                processedDocIds.add(String(event.document_id));
              }
              if (event.type === 'done') processingDone = true;
              console.log('[batch-stream]', event.type, event.document_id || '', event.success ?? '');
            } catch (_) {}
          }
        }
      }
    } catch (streamErr) {
      console.warn('[batch] Streaming processing failed, trying sync:', streamErr);
    }

    // Fallback: sync batch — only send documents NOT already processed
    if (!processingDone) {
      const remainingDocs = docsPayload.filter(d => !processedDocIds.has(d.document_id));
      if (remainingDocs.length > 0) {
        try {
          const processRes = await fetch(`${backendUrl}/api/documents/process-batch`, {
            method: 'POST',
            headers: getBackendHeaders(),
            body: JSON.stringify({ documents: remainingDocs }),
            signal: AbortSignal.timeout(300_000),
          });
          if (processRes.ok) {
            processingDone = true;
            console.log('[batch] Sync batch fallback completed for', remainingDocs.length, 'remaining doc(s)');
          }
        } catch (syncErr) {
          console.warn('[batch] Sync batch also failed, falling back to Celery:', syncErr);
        }
      } else {
        // All docs were processed during streaming even though 'done' event wasn't received
        processingDone = true;
        console.log('[batch] All docs processed during streaming (no done event), skipping fallbacks');
      }
    }

    // Last resort: Celery async — only send still-unprocessed documents
    if (!processingDone) {
      const stillRemaining = docsPayload.filter(d => !processedDocIds.has(d.document_id));
      if (stillRemaining.length > 0) {
        (async () => {
          try {
            await fetch(`${backendUrl}/api/documents/process-batch-async`, {
              method: 'POST',
              headers: getBackendHeaders(),
              body: JSON.stringify({ documents: stillRemaining }),
            });
          } catch (e) {
            console.error('[batch] Async fallback also failed:', e);
          }
        })();
      }
    }

    return NextResponse.json({
      success: true,
      documentIds: results.map((r) => r.id),
      documents: results,
      processed: processingDone,
      processedCount,
      uploadErrors: errors.length > 0 ? errors : undefined,
      message: processingDone
        ? `Uploaded and processed ${results.length} document(s).`
        : `Uploaded ${results.length} document(s); processing queued in background.`,
    });
  } catch (error: unknown) {
    console.error('Batch upload error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
