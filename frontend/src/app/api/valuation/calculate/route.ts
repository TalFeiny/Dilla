import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '@/lib/backend-url';
import { supabaseService } from '@/lib/supabase';

/**
 * Thin Valuation API
 * Human-triggered valuation calculations (not agentic)
 * Proxies to FastAPI valuation engine
 */
export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 503 }
      );
    }

    const body = await request.json();
    const { companyId, method, context } = body;

    if (!companyId) {
      return NextResponse.json(
        { error: 'companyId is required' },
        { status: 400 }
      );
    }

    // Fetch company data from Supabase
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    if (companyError || !company) {
      return NextResponse.json(
        { error: 'Company not found' },
        { status: 404 }
      );
    }

    // Map company data to backend ValuationRequest format
    // Backend expects company_data as a dict, method, comparables, and assumptions
    const valuationRequest = {
      company_data: {
        name: company.name || 'Unknown',
        company_id: company.id,
        stage: company.stage || company.investment_stage || 'seed',
        revenue: company.current_arr_usd || 0,
        arr: company.current_arr_usd || 0,
        growth_rate: company.growth_rate || company.revenue_growth_pct || 0,
        burn_rate: company.burn_rate_monthly_usd || 0,
        cash_balance: company.cash_in_bank_usd || 0,
        runway_months: company.runway_months || 0,
        gross_margin: company.gross_margin || 0,
        sector: company.sector || '',
        business_model: company.business_model || '',
        industry: company.sector || '',
        category: company.category || '',
        last_round_valuation: company.current_valuation_usd || company.last_valuation_usd || null,
        last_round_date: company.last_valuation_date || company.first_investment_date || null,
        total_raised: company.total_invested_usd || 0,
        ...context, // Allow additional context to override
      },
      method: method || 'auto',
      comparables: [],
      assumptions: {},
    };

    // Call backend valuation engine
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/valuation/value-company`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(valuationRequest),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Valuation failed' }));
      return NextResponse.json(
        { error: error.error || 'Valuation calculation failed' },
        { status: response.status }
      );
    }

    const result = await response.json();
    // Backend returns { success, method, valuation, company, timestamp }; numeric result is in valuation
    const rawValuation = result.valuation;
    const valuation =
      typeof rawValuation === 'number'
        ? rawValuation
        : (rawValuation?.fair_value ?? rawValuation?.value ?? result.fair_value ?? result.value ?? 0);
    const methodUsed =
      (typeof rawValuation === 'object' && rawValuation?.method_used) || result.method_used || method || 'auto';
    const explanation =
      (typeof rawValuation === 'object' && rawValuation?.explanation) || result.explanation || '';
    const confidence =
      (typeof rawValuation === 'object' && rawValuation?.confidence) ?? result.confidence ?? 0.5;

    // Audit: log to matrix_edits for service logs / auditing
    try {
      await supabaseService.from('matrix_edits').insert({
        company_id: companyId,
        column_id: 'valuation',
        old_value: company.current_valuation_usd ?? company.last_valuation_usd ?? null,
        new_value: valuation,
        edited_by: 'service',
        edited_at: new Date().toISOString(),
        data_source: 'service',
        fund_id: company.fund_id || null,
        metadata: {
          service: 'valuation_engine',
          method: methodUsed,
          explanation,
          confidence,
          details: result,
        },
      });
    } catch (auditErr) {
      console.warn('Valuation audit log failed (non-fatal):', auditErr);
    }

    // Return standardized format
    return NextResponse.json({
      success: true,
      valuation,
      method: methodUsed,
      confidence,
      explanation,
      details: result,
      companyId,
    });
  } catch (error) {
    console.error('Valuation API error:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
