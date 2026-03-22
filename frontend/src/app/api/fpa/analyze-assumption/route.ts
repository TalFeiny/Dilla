import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/proxy-to-backend';

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/api/fpa/analyze-assumption');
}
