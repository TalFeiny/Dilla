import { NextRequest } from 'next/server';
import { proxyToBackend, withQuery } from '@/lib/proxy-to-backend';

export async function GET(request: NextRequest) {
  return proxyToBackend(request, withQuery(request, '/api/fpa/drivers/registry'));
}
