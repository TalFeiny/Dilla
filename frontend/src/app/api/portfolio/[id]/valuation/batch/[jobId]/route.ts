import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * GET /api/portfolio/[id]/valuation/batch/[jobId]
 * Get status and progress of a batch valuation job
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; jobId: string }> }
) {
  try {
    const { id: fundId, jobId } = await params;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    const { data: job, error } = await supabaseService
      .from('batch_valuation_jobs')
      .select('*')
      .eq('id', jobId)
      .eq('fund_id', fundId)
      .single();

    if (error || !job) {
      return NextResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    // Calculate progress percentage
    const progress =
      job.total_companies > 0
        ? ((job.completed_count + job.failed_count) / job.total_companies) * 100
        : 0;

    // Calculate estimated time remaining (if processing)
    let estimatedCompletionAt = null;
    if (job.status === 'processing' && job.started_at && job.completed_count > 0) {
      const elapsed = Date.now() - new Date(job.started_at).getTime();
      const avgTimePerCompany = elapsed / job.completed_count;
      const remaining = job.total_companies - job.completed_count - job.failed_count;
      const estimatedMs = avgTimePerCompany * remaining;
      estimatedCompletionAt = new Date(Date.now() + estimatedMs).toISOString();
    }

    return NextResponse.json({
      jobId: job.id,
      status: job.status,
      progress: Math.round(progress),
      totalCompanies: job.total_companies,
      completedCount: job.completed_count,
      failedCount: job.failed_count,
      processingCount: job.processing_count,
      method: job.valuation_method,
      results: job.results || {},
      errors: job.errors || [],
      createdAt: job.created_at,
      startedAt: job.started_at,
      completedAt: job.completed_at,
      estimatedCompletionAt,
      metadata: job.metadata || {},
    });
  } catch (error) {
    console.error('Batch job status error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/portfolio/[id]/valuation/batch/[jobId]
 * Cancel a batch valuation job (if still processing)
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; jobId: string }> }
) {
  try {
    const { id: fundId, jobId } = await params;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    // Check if job exists and is cancellable
    const { data: job } = await supabaseService
      .from('batch_valuation_jobs')
      .select('status')
      .eq('id', jobId)
      .eq('fund_id', fundId)
      .single();

    if (!job) {
      return NextResponse.json(
        { error: 'Job not found' },
        { status: 404 }
      );
    }

    if (job.status === 'completed' || job.status === 'failed') {
      return NextResponse.json(
        { error: 'Cannot cancel completed or failed job' },
        { status: 400 }
      );
    }

    // Update status to cancelled
    const { error } = await supabaseService
      .from('batch_valuation_jobs')
      .update({
        status: 'cancelled',
        completed_at: new Date().toISOString(),
      })
      .eq('id', jobId);

    if (error) {
      console.error('Error cancelling job:', error);
      return NextResponse.json(
        { error: 'Failed to cancel job' },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, jobId });
  } catch (error) {
    console.error('Cancel batch job error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
