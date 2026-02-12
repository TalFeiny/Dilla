import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

// Import the same job storage (in a real app, this would be in a shared module or Redis)
// For now, we'll recreate the map structure - in production use Redis or a database
const searchJobs = new Map<string, {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  companyNames: string[];
  results: Record<string, any>;
  error?: string;
  createdAt: number;
}>();

export async function GET(
  request: NextRequest,
  { params }: { params: { jobId: string } }
) {
  try {
    const { jobId } = params;

    // In a real implementation, fetch from shared storage (Redis/DB)
    // For MVP, we'll need to access the same Map - this is a limitation
    // that should be fixed with proper storage
    
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/mcp/batch-search-status/${jobId}`, {
      method: 'GET',
    });

    if (response.ok) {
      const status = await response.json();
      return NextResponse.json(status);
    }

    // Fallback: return not found
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
