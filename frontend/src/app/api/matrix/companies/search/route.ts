import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';

// In-memory job storage (for MVP - use Redis in production)
const searchJobs = new Map<string, {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  companyNames: string[];
  results: Record<string, any>;
  error?: string;
  createdAt: number;
}>();

// Clean up old jobs (older than 1 hour)
setInterval(() => {
  const oneHourAgo = Date.now() - 3600000;
  for (const [jobId, job] of searchJobs.entries()) {
    if (job.createdAt < oneHourAgo) {
      searchJobs.delete(jobId);
    }
  }
}, 60000); // Run cleanup every minute

export async function POST(request: NextRequest) {
  try {
    const { companyNames } = await request.json();

    if (!Array.isArray(companyNames) || companyNames.length === 0) {
      return NextResponse.json(
        { error: 'companyNames must be a non-empty array' },
        { status: 400 }
      );
    }

    // Generate job ID
    const jobId = `search-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    // Initialize job
    searchJobs.set(jobId, {
      status: 'pending',
      companyNames,
      results: {},
      createdAt: Date.now(),
    });

    // Start async batch search (don't await - let it run in background)
    performBatchSearch(jobId, companyNames).catch((error) => {
      const job = searchJobs.get(jobId);
      if (job) {
        job.status = 'failed';
        job.error = error.message || 'Batch search failed';
      }
    });

    return NextResponse.json({ jobId });
  } catch (error) {
    console.error('Error starting batch search:', error);
    return NextResponse.json(
      { error: 'Failed to start batch search' },
      { status: 500 }
    );
  }
}

async function performBatchSearch(jobId: string, companyNames: string[]) {
  const job = searchJobs.get(jobId);
  if (!job) return;

  job.status = 'processing';

  try {
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/mcp/batch-search-companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ companyNames }),
    });

    if (!response.ok) {
      throw new Error(`Backend search failed: ${response.status}`);
    }

    const results = await response.json();
    
    job.results = results;
    job.status = 'completed';
  } catch (error) {
    console.error('Batch search error:', error);
    job.status = 'failed';
    job.error = error instanceof Error ? error.message : 'Unknown error';
  }
}
