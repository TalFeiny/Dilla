import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

/**
 * POST /api/fpa/upload-actuals
 * Proxy multipart form upload (CSV file + company_id + fund_id) to backend.
 * Backend parses CSV, auto-detects orientation, and upserts into fpa_actuals.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const backendUrl = getBackendUrl();

    // Forward the form data as-is to the backend
    const res = await fetch(`${backendUrl}/api/fpa/upload-actuals`, {
      method: 'POST',
      body: formData,
      headers: {
        // Let fetch set Content-Type with boundary for multipart
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
    console.error('FPA upload-actuals error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}
