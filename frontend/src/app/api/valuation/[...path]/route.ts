import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/proxy-to-backend';

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, `/api/valuation/${path.join('/')}`);
}
