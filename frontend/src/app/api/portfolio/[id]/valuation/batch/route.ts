import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { getBackendUrl } from '@/lib/backend-url';

const MAX_CONCURRENT_VALUATIONS = 5; // Process 5 companies at a time
const VALUATION_TIMEOUT_MS = 60000; // 60 seconds per valuation

interface BatchValuationRequest {
  companyIds: string[];
  method: 'dcf' | 'comparables' | 'pwerm' | 'auto';
  filters?: {
    growthRateMin?: number;
    sector?: string;
    stage?: string;
  };
}

/**
 * POST /api/portfolio/[id]/valuation/batch
 * Start a batch valuation job
 * Returns immediately with jobId, processing happens in background
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const body: BatchValuationRequest = await request.json();
    const { companyIds, method = 'auto', filters } = body;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    if (!companyIds || companyIds.length === 0) {
      return NextResponse.json(
        { error: 'companyIds array is required' },
        { status: 400 }
      );
    }

    // Create job record
    const { data: job, error: jobError } = await supabaseService
      .from('batch_valuation_jobs')
      .insert({
        fund_id: fundId,
        valuation_method: method,
        company_ids: companyIds,
        total_companies: companyIds.length,
        status: 'queued',
        completed_count: 0,
        failed_count: 0,
        processing_count: 0,
        results: {},
        errors: [],
        metadata: { filters },
      })
      .select()
      .single();

    if (jobError || !job) {
      console.error('Failed to create batch job:', jobError);
      return NextResponse.json(
        { error: 'Failed to create batch job' },
        { status: 500 }
      );
    }

    // Start background processing (don't await)
    processBatchValuation(job.id, fundId, companyIds, method).catch((error) => {
      console.error('Batch valuation processing error:', error);
      // Update job status to failed
      void supabaseService
        .from('batch_valuation_jobs')
        .update({
          status: 'failed',
          errors: [{ error: error.message, timestamp: new Date().toISOString() }],
        })
        .eq('id', job.id)
        .then(() => {}, console.error);
    });

    return NextResponse.json({
      jobId: job.id,
      status: 'queued',
      totalCompanies: companyIds.length,
      method,
    });
  } catch (error) {
    console.error('Batch valuation API error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}

/**
 * Process batch valuation in background
 * Uses concurrency limits and incremental result storage
 */
async function processBatchValuation(
  jobId: string,
  fundId: string,
  companyIds: string[],
  method: string
) {
  if (!supabaseService) return;

  // Update status to processing
  await supabaseService
    .from('batch_valuation_jobs')
    .update({
      status: 'processing',
      started_at: new Date().toISOString(),
    })
    .eq('id', jobId);

  const results: Record<string, any> = {};
  const errors: any[] = [];
  let completedCount = 0;
  let failedCount = 0;

  // Process companies in batches with concurrency limit
  for (let i = 0; i < companyIds.length; i += MAX_CONCURRENT_VALUATIONS) {
    const batch = companyIds.slice(i, i + MAX_CONCURRENT_VALUATIONS);

    // Process batch in parallel
    const batchPromises = batch.map(async (companyId) => {
      try {
        // Update processing count
        await supabaseService
          .from('batch_valuation_jobs')
          .update({
            processing_count: i + batch.length,
          })
          .eq('id', jobId);

        // Call valuation API with timeout
        const valuationResult = await Promise.race([
          fetch(`${getBackendUrl()}/api/valuation/value-company`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              company_data: { company_id: companyId },
              method,
            }),
          }),
          new Promise<Response>((_, reject) =>
            setTimeout(() => reject(new Error('Valuation timeout')), VALUATION_TIMEOUT_MS)
          ),
        ]);

        if (!valuationResult.ok) {
          throw new Error(`Valuation failed: ${valuationResult.status}`);
        }

        const data = await valuationResult.json();
        const valuation = data.fair_value ?? data.value ?? 0;

        // Get company ownership for NAV calculation
        const { data: company } = await supabaseService
          .from('companies')
          .select('ownership_percentage')
          .eq('id', companyId)
          .eq('fund_id', fundId)
          .single();

        const ownership = (company?.ownership_percentage || 0) / 100;
        const nav = valuation * ownership;

        // Store result incrementally
        const result = {
          valuation,
          nav,
          method: data.method_used || method,
          explanation: data.explanation || '',
          confidence: data.confidence || 0.5,
          completed_at: new Date().toISOString(),
        };

        results[companyId] = result;
        completedCount++;

        // Update job with incremental result
        await supabaseService
          .from('batch_valuation_jobs')
          .update({
            results,
            completed_count: completedCount,
            processing_count: Math.max(0, i + batch.length - completedCount - failedCount),
          })
          .eq('id', jobId);

        return result;
      } catch (error: any) {
        failedCount++;
        const errorEntry = {
          companyId,
          error: error.message || String(error),
          retry_count: 0,
          timestamp: new Date().toISOString(),
        };
        errors.push(errorEntry);

        // Update job with error
        await supabaseService
          .from('batch_valuation_jobs')
          .update({
            errors: [...errors],
            failed_count: failedCount,
            processing_count: Math.max(0, i + batch.length - completedCount - failedCount),
          })
          .eq('id', jobId);

        return null;
      }
    });

    await Promise.all(batchPromises);
  }

  // Final update
  const finalStatus = failedCount === companyIds.length ? 'failed' : 'completed';
  await supabaseService
    .from('batch_valuation_jobs')
    .update({
      status: finalStatus,
      completed_count: completedCount,
      failed_count: failedCount,
      completed_at: new Date().toISOString(),
    })
    .eq('id', jobId);
}

/**
 * GET /api/portfolio/[id]/valuation/batch
 * Get all batch valuation jobs for a fund
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    let query = supabaseService
      .from('batch_valuation_jobs')
      .select('*')
      .eq('fund_id', fundId)
      .order('created_at', { ascending: false });

    if (status) {
      query = query.eq('status', status);
    }

    const { data: jobs, error } = await query;

    if (error) {
      console.error('Error fetching batch jobs:', error);
      return NextResponse.json(
        { error: 'Failed to fetch batch jobs' },
        { status: 500 }
      );
    }

    return NextResponse.json({ jobs: jobs || [] });
  } catch (error) {
    console.error('Batch valuation GET error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
