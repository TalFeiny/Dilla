import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * Proxy to FastAPI backend-agnostic document processing.
 * POST body: { documentId, filePath, documentType?, company_id?, fund_id? }
 * Backend: POST /api/documents/process with storage download, extraction, metadata_repo update.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  console.log('[documents/process] POST /api/documents/process received');
  const backendUrl = getBackendUrl();

  try {
    const body = await request.json();
    const {
      documentId,
      filePath,
      documentType,
      company_id,
      fund_id,
    } = body;

    if (!documentId || !filePath) {
      return NextResponse.json(
        { error: 'Missing required parameters: documentId, filePath' },
        { status: 400 }
      );
    }

    console.log('[documents/process] Calling backend', backendUrl, '/api/documents/process');
    const response = await fetch(`${backendUrl}/api/documents/process`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(request.headers.get('Authorization') && {
          Authorization: request.headers.get('Authorization')!,
        }),
      },
      body: JSON.stringify({
        document_id: String(documentId ?? ''),
        file_path: filePath,
        document_type: documentType ?? 'other',
        company_id: company_id ?? null,
        fund_id: fund_id ?? null,
      }),
    });

    let data: Record<string, unknown>;
    try {
      data = await response.json();
    } catch {
      const text = await response.text().catch(() => '');
      console.error('[documents/process] Backend returned non-JSON. Status:', response.status, 'Body:', text?.slice(0, 200));
      return NextResponse.json(
        { error: 'Backend returned invalid response. Is the backend running at ' + backendUrl + '?' },
        { status: 502 }
      );
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: (data as { detail?: string; error?: string }).detail ?? (data as { error?: string }).error ?? 'Document processing failed' },
        { status: response.status }
      );
    }

    return NextResponse.json({
      success: data.success ?? true,
      message: data.message ?? 'Document processed successfully',
      document_id: data.document_id ?? documentId,
      company_id: data.company_id ?? company_id ?? null,
      company_linked: !!(data.company_id ?? company_id),
      result: data.result ?? undefined,
      error: data.error ?? undefined,
    });
  } catch (error) {
    console.error('Documents process proxy error:', error);
    return NextResponse.json(
      { error: 'Processing failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
