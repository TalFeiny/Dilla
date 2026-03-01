import { NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';

/**
 * GET /api/debug-gate
 * Temporary endpoint to diagnose the 403 secret mismatch. DELETE after fixing.
 * Calls the backend's /api/debug-gate (which bypasses the gate) and returns
 * what both sides think the secret is.
 */
export async function GET() {
  const secret = process.env.BACKEND_API_SECRET || '';
  const backendUrl = getBackendUrl();

  try {
    const res = await fetch(`${backendUrl}/api/debug-gate`, {
      headers: getBackendHeaders(),
    });
    const data = await res.json();

    return NextResponse.json({
      frontend: {
        secret_prefix: secret.slice(0, 12),
        secret_len: secret.length,
        secret_repr_tail: secret ? JSON.stringify(secret.slice(-5)) : 'empty',
        backend_url: backendUrl,
      },
      backend: data,
    });
  } catch (error) {
    return NextResponse.json({
      frontend: {
        secret_prefix: secret.slice(0, 12),
        secret_len: secret.length,
        secret_repr_tail: secret ? JSON.stringify(secret.slice(-5)) : 'empty',
        backend_url: backendUrl,
      },
      backend_error: error instanceof Error ? error.message : String(error),
    }, { status: 502 });
  }
}
