import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/lib/proxy-to-backend';

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ branchId: string }> }) {
  const { branchId } = await params;
  return proxyToBackend(request, `/api/fpa/scenarios/branch/${branchId}`);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ branchId: string }> }) {
  const { branchId } = await params;
  return proxyToBackend(request, `/api/fpa/scenarios/branch/${branchId}`);
}
