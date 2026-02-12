import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

const MAX_CONCURRENT = 5;

/**
 * POST /api/portfolio/[id]/valuation
 * Sync valuation for all companies in a fund.
 * Loads portfolio companies, calls /api/valuation/calculate per company (with concurrency limit),
 * returns { companies } for valuePortfolio workflow.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    if (!fundId?.trim()) {
      return NextResponse.json({ error: 'Fund ID is required' }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    const body = await request.json().catch(() => ({}));
    const method = body.method || 'auto';

    const { data: companies, error: listError } = await supabaseService
      .from('companies')
      .select('id, name, sector, funnel_status, total_invested_usd, ownership_percentage, current_arr_usd, fund_id')
      .eq('fund_id', fundId)
      .order('name', { ascending: true });

    if (listError || !companies?.length) {
      return NextResponse.json(
        { error: listError?.message || 'No companies found for this fund', companies: [] },
        { status: companies?.length === 0 ? 200 : 500 }
      );
    }

    const origin =
      (typeof request.url === 'string' ? new URL(request.url).origin : null) ||
      process.env.NEXT_PUBLIC_APP_URL ||
      'http://localhost:3000';
    const results: Array<{
      id: string;
      name?: string;
      sector?: string;
      stage?: string;
      valuation?: number;
      method?: string;
      confidence?: number;
      error?: string;
    }> = [];

    for (let i = 0; i < companies.length; i += MAX_CONCURRENT) {
      const chunk = companies.slice(i, i + MAX_CONCURRENT);
      const chunkResults = await Promise.all(
        chunk.map(async (company: { id: string; name?: string; sector?: string; funnel_status?: string }) => {
          try {
            const res = await fetch(`${origin}/api/valuation/calculate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                companyId: company.id,
                method,
                context: { fundId },
              }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
              return {
                id: company.id,
                name: company.name,
                sector: company.sector,
                stage: company.funnel_status,
                error: data.error || `HTTP ${res.status}`,
              };
            }
            const valuation = data.valuation ?? data.data?.valuation ?? 0;
            return {
              id: company.id,
              name: company.name,
              sector: company.sector,
              stage: company.funnel_status,
              valuation,
              method: data.method ?? method,
              confidence: data.confidence,
            };
          } catch (err) {
            return {
              id: company.id,
              name: company.name,
              sector: company.sector,
              stage: company.funnel_status,
              error: err instanceof Error ? err.message : 'Valuation failed',
            };
          }
        })
      );
      results.push(...chunkResults);
    }

    return NextResponse.json({ companies: results });
  } catch (error) {
    console.error('Portfolio valuation API error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 }
    );
  }
}
