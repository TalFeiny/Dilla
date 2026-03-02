import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * Get NAV time series data for portfolio companies
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const { searchParams } = new URL(request.url);
    const companyIdsParam = searchParams.get('companyIds');

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    if (!companyIdsParam) {
      return NextResponse.json({ error: 'companyIds parameter is required' }, { status: 400 });
    }

    const companyIds = companyIdsParam.split(',').filter((id) => id.trim());

    if (companyIds.length === 0) {
      return NextResponse.json({});
    }

    // Get current ownership percentages for companies
    const { data: companies, error: companiesError } = await supabaseService
      .from('companies')
      .select('id, ownership_percentage')
      .in('id', companyIds)
      .eq('fund_id', fundId);

    if (companiesError) {
      console.error('Error fetching companies:', companiesError);
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }

    const ownershipMap = new Map<string, number>();
    companies?.forEach((c: any) => {
      ownershipMap.set(c.id, c.ownership_percentage || 0);
    });

    // Get historical metrics (Phase 5.2: limit to last 24 months for performance)
    const twentyFourMonthsAgo = new Date();
    twentyFourMonthsAgo.setMonth(twentyFourMonthsAgo.getMonth() - 24);
    const { data: historyData, error: historyError } = await supabaseService
      .from('company_metrics_history')
      .select('company_id, current_arr_usd, recorded_at')
      .in('company_id', companyIds)
      .eq('fund_id', fundId)
      .gte('recorded_at', twentyFourMonthsAgo.toISOString())
      .order('recorded_at', { ascending: true })
      .limit(1000);

    if (historyError) {
      console.error('Error fetching history:', historyError);
      // Return empty data instead of error - time series is optional
      return NextResponse.json({});
    }

    // Group by company and calculate NAV over time
    const companyHistory = new Map<string, Array<{ arr: number; date: string }>>();

    historyData?.forEach((record: any) => {
      if (!companyHistory.has(record.company_id)) {
        companyHistory.set(record.company_id, []);
      }
      companyHistory.get(record.company_id)!.push({
        arr: record.current_arr_usd || 0,
        date: record.recorded_at,
      });
    });

    // Calculate NAV time series for each company
    // Return as number[] for sparklines (values only, no dates)
    // UnifiedMatrix can store dates separately if needed
    const result: Record<string, number[]> = {};
    const allDates: string[] = [];
    const dateToCompanyNav = new Map<string, Map<string, number>>();

    companyHistory.forEach((history, companyId) => {
      const ownership = ownershipMap.get(companyId) || 0;
      const ownershipDecimal = ownership / 100;

      const navSeries = history.map((h) => {
        const valuation = h.arr * 10; // Simple multiple
        return valuation * ownershipDecimal;
      });

      result[companyId] = navSeries;

      // Build date-indexed data for aggregate
      history.forEach((h, i) => {
        if (!allDates.includes(h.date)) allDates.push(h.date);
        if (!dateToCompanyNav.has(h.date)) {
          dateToCompanyNav.set(h.date, new Map());
        }
        dateToCompanyNav.get(h.date)!.set(companyId, navSeries[i]);
      });
    });

    // If aggregate requested, return portfolio-level NAV over time with dates
    const aggregateParam = searchParams.get('aggregate');
    if (aggregateParam === '1' || aggregateParam === 'true') {
      const sortedDates = [...new Set(allDates)].sort();
      const aggregateNav = sortedDates.map((d) => {
        const byCompany = dateToCompanyNav.get(d);
        if (!byCompany) return 0;
        return [...byCompany.values()].reduce((a, b) => a + b, 0);
      });
      return NextResponse.json({
        byCompany: result,
        aggregate: {
          labels: sortedDates,
          data: aggregateNav,
        },
      });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Error in NAV time series API:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
