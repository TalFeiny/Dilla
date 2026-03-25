import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * POST /api/agent/cap-table-entries/upload-csv
 * Proxy multipart form upload (CSV file + company_id + fund_id) to backend.
 * Same pattern as /api/fpa/upload-actuals.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/agent/cap-table-entries/upload-csv`, {
      method: 'POST',
      body: formData,
      headers: {
        Accept: 'application/json',
        ...(process.env.BACKEND_API_SECRET
          ? { 'X-Backend-Secret': process.env.BACKEND_API_SECRET }
          : {}),
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      return NextResponse.json(
        { error: err.detail ?? 'Upload failed' },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Cap table CSV upload error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
