import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl, getBackendHeaders } from '@/lib/backend-url';
import { searchJobs } from '../job-store';

export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  try {
    const { jobId } = params;

    // Check shared in-memory store first (same Map the POST route writes to)
    const localJob = searchJobs.get(jobId);
    if (localJob) {
      return NextResponse.json({
        status: localJob.status,
        companyNames: localJob.companyNames,
        results: localJob.results,
        error: localJob.error,
      });
    }

    // Fallback: try backend status endpoint
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/mcp/batch-search-status/${jobId}`, {
      method: 'GET',
      headers: getBackendHeaders(),
    });

    if (response.ok) {
      const status = await response.json();
      return NextResponse.json(status);
    }

    return NextResponse.json(
      { error: 'Job not found' },
      { status: 404 }
    );
  } catch (error) {
    console.error('Error checking search status:', error);
    return NextResponse.json(
      { error: 'Failed to check search status' },
      { status: 500 }
    );
  }
}
