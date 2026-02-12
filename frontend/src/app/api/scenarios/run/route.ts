import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { getBackendUrl } from '@/lib/backend-url';

const BACKEND_URL = getBackendUrl();

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
    if (supabaseService) {
      const { data: portfolioData } = await supabaseService
        .from('funds')
        .select('*')
        .eq('id', portfolioId)
        .maybeSingle();
      if (portfolioData) {
        portfolioRecord = portfolioData;
      }
    }

    // Fetch portfolio companies - use companies table with fund_id filter
    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    const { data: portfolioCompanies, error: pcError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('fund_id', portfolioId)
      .not('fund_id', 'is', null);

    if (pcError) {
      console.error('Error fetching portfolio companies:', pcError);
      return NextResponse.json(
        { error: 'Failed to fetch portfolio companies' },
        { status: 500 }
      );
    }

    const companiesPayload = (portfolioCompanies || []).map((company: any) => {
      const companyName = company.name || 'Unknown Company';
      const valuation =
        company.current_valuation_usd ??
        company.last_valuation_usd ??
        null;
      const totalFunding =
        company.total_funding_usd ??
        company.total_raised_usd ??
        company.total_invested_usd ??
        null;

      return {
        company: companyName,
        company_id: company.id?.toString() || companyName,
        stage:
          company.investment_stage ||
          company.funding_stage ||
          company.stage ||
          null,
        revenue: company.current_arr_usd ?? null,
        inferred_revenue: company.inferred_revenue ?? null,
        valuation,
        inferred_valuation: company.inferred_valuation ?? valuation,
        total_funding: totalFunding,
        total_raised: totalFunding,
        inferred_total_funding: company.inferred_total_funding ?? null,
        growth_rate:
          company.growth_rate ??
          company.revenue_growth_pct ??
          company.inferred_growth_rate ??
          null,
        sector: company.sector ?? null,
        category: company.category ?? null,
        business_model: company.business_model ?? null,
        ai_component_percentage: company.ai_component_percentage ?? null,
        ownership_percentage: company.ownership_percentage ?? null,
        investment_amount: company.total_invested_usd ?? null,
        current_arr: company.current_arr_usd ?? null,
        current_valuation: valuation,
        investment_date: company.first_investment_date ?? company.created_at ?? null,
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
