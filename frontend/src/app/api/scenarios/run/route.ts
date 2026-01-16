import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      scenarioId = 'portfolio-scenario',
      portfolioId,
      selectedScenarios = [],
      numScenarios = 12,
      includeDownside = true,
      includeUpside = true,
      timeHorizon = 5,
    } = body;

    if (!portfolioId) {
      return NextResponse.json(
        { error: 'Portfolio ID is required' },
        { status: 400 }
      );
    }

    // Fetch portfolio metadata (best effort)
    let portfolioRecord: any = null;
    const { data: portfolioData } = await supabase
      .from('funds')
      .select('*')
      .eq('id', portfolioId)
      .maybeSingle();
    if (portfolioData) {
      portfolioRecord = portfolioData;
    }

    // Fetch portfolio companies with company details
    const { data: portfolioCompanies, error: pcError } = await supabase
      .from('portfolio_companies')
      .select(
        `
          *,
          company:companies(*)
        `
      )
      .eq('fund_id', portfolioId);

    if (pcError) {
      console.error('Error fetching portfolio companies:', pcError);
      return NextResponse.json(
        { error: 'Failed to fetch portfolio companies' },
        { status: 500 }
      );
    }

    const companiesPayload = (portfolioCompanies || []).map((pc: any) => {
      const companyName = pc.company?.name || 'Unknown Company';
      const valuation =
        pc.current_valuation_usd ??
        pc.company?.last_valuation_usd ??
        pc.company?.current_valuation_usd ??
        null;
      const totalFunding =
        pc.company?.total_funding_usd ??
        pc.company?.total_raised_usd ??
        pc.total_invested_usd ??
        null;

      return {
        company: companyName,
        company_id:
          pc.company?.id?.toString() || pc.company?.uuid?.toString() || companyName,
        stage:
          pc.investment_stage ||
          pc.company?.funding_stage ||
          pc.company?.stage ||
          null,
        revenue: pc.company?.current_arr_usd ?? null,
        inferred_revenue: pc.company?.inferred_revenue ?? null,
        valuation,
        inferred_valuation: pc.company?.inferred_valuation ?? valuation,
        total_funding: totalFunding,
        total_raised: totalFunding,
        inferred_total_funding: pc.company?.inferred_total_funding ?? null,
        growth_rate:
          pc.company?.growth_rate ??
          pc.company?.revenue_growth_pct ??
          pc.company?.inferred_growth_rate ??
          null,
        sector: pc.company?.sector ?? null,
        category: pc.company?.category ?? null,
        business_model: pc.company?.business_model ?? null,
        ai_component_percentage: pc.company?.ai_component_percentage ?? null,
        ownership_percentage: pc.ownership_percentage ?? null,
        investment_amount: pc.total_invested_usd ?? null,
        current_arr: pc.company?.current_arr_usd ?? null,
        current_valuation: valuation,
        investment_date: pc.investment_date ?? null,
      };
    });

    const portfolioName = portfolioRecord?.name || portfolioRecord?.title || portfolioId;

    const prompt = `Run a comprehensive PWERM scenario analysis for portfolio ${portfolioName}.
Return probability-weighted exit scenarios for every company, including exit valuation, present value, MOIC, probability, and percentile summaries.`;

    const unifiedBrainPayload = {
      prompt,
      output_format: 'analysis',
      stream: false,
      context: {
        scenario_request: {
          scenario_id: scenarioId,
          portfolio_id: portfolioId,
          selected_scenarios: selectedScenarios,
          num_scenarios: numScenarios,
          include_downside: includeDownside,
          include_upside: includeUpside,
          time_horizon: timeHorizon,
        },
        portfolio: portfolioRecord || { id: portfolioId },
        companies: companiesPayload,
      },
      options: {
        scenarioAnalysis: true,
      },
    };

    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(unifiedBrainPayload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Unified brain scenario analysis failed:', errorText);
      return NextResponse.json(
        { error: 'Scenario analysis failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({ success: true, result: data });
  } catch (error) {
    console.error('Error in POST /api/scenarios/run:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
