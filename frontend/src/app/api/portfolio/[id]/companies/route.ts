import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * GET /api/portfolio/[id]/companies
 * Fetch all companies for a fund with portfolio fields
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;

    if (!fundId || fundId.trim() === '') {
      return NextResponse.json({
        error: 'Fund ID is required'
      }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ 
        error: 'Supabase service not configured' 
      }, { status: 500 });
    }

    // Tier 1: Full | Tier 2: Core (key display fields) | Tier 3: Minimal (fallback for schema drift)
    const fullColumns = [
      'id', 'name', 'sector', 'funnel_status', 'total_invested_usd', 'ownership_percentage',
      'current_arr_usd', 'current_valuation_usd', 'first_investment_date', 'exit_date', 'exit_value_usd',
      'exit_multiple', 'fund_id', 'extra_data', 'cash_in_bank_usd', 'investment_lead',
      'last_contacted_date', 'burn_rate_monthly_usd', 'runway_months', 'gross_margin',
      'revenue_growth_monthly_pct', 'revenue_growth_annual_pct',
      'cash_updated_at', 'burn_rate_updated_at', 'runway_updated_at', 'revenue_updated_at', 'gross_margin_updated_at'
    ];
    const coreColumns = [
      'id', 'name', 'sector', 'funnel_status', 'fund_id', 'total_invested_usd', 'ownership_percentage',
      'current_arr_usd', 'current_valuation_usd', 'first_investment_date',
      'burn_rate_monthly_usd', 'runway_months', 'gross_margin', 'cash_in_bank_usd', 'extra_data'
    ];
    const minimalColumns = [
      'id', 'name', 'sector', 'fund_id', 'total_invested_usd', 'ownership_percentage',
      'current_arr_usd', 'first_investment_date'
    ];

    let companies: any[] | null = null;
    let error: any = null;

    for (const columns of [fullColumns, coreColumns, minimalColumns]) {
      const selectColumns = columns.join(', ');
      const result = await supabaseService
        .from('companies')
        .select(selectColumns)
        .eq('fund_id', fundId)
        .order('name', { ascending: true });
      companies = result.data;
      error = result.error;
      if (!error) break;
      if (error.code === '42703') {
        console.warn(`[companies] Retrying with fewer columns (${columns.length} cols), error:`, error.message);
      } else {
        break; // Non-column error, don't retry
      }
    }

    if (error) {
      console.error('Error fetching companies:', error);
      return NextResponse.json({ 
        error: 'Failed to fetch companies',
        details: error.message,
        code: error.code 
      }, { status: 500 });
    }

    // Transform to portfolio company format with calculated metrics
    const portfolioCompanies = (companies || []).map((company: any) => {
      const investmentAmount = company.total_invested_usd ?? null;
      const ownershipPercentage = company.ownership_percentage ?? null;
      const currentArr = company.current_arr_usd ?? null;
      // Use persisted current_valuation_usd when present; else derive from investment/ownership only. No invented multiples.
      const valuation =
        company.current_valuation_usd != null && company.current_valuation_usd > 0
          ? Number(company.current_valuation_usd)
          : company.total_invested_usd && ownershipPercentage > 0
            ? investmentAmount / (ownershipPercentage / 100)
            : undefined;

      const base = {
        id: company.id,
        name: company.name,
        sector: company.sector || '',
        stage: company.funnel_status || '',
        investmentAmount,
        ownershipPercentage,
        currentArr,
        valuation,
        investmentDate: company.first_investment_date || '',
        exitDate: company.exit_date || undefined,
        exitValue: company.exit_value_usd ?? company.exit_value ?? undefined,
        exitMultiple: company.exit_multiple || undefined,
        fundId: company.fund_id,
        cashInBank: company.cash_in_bank_usd || undefined,
        investmentLead: company.investment_lead || undefined,
        lastContacted: company.last_contacted_date || undefined,
        burnRate: company.burn_rate_monthly_usd || undefined,
        runwayMonths: company.runway_months || undefined,
        grossMargin: company.gross_margin || undefined,
        revenueGrowthMonthly: company.revenue_growth_monthly_pct ?? undefined,
        revenueGrowthAnnual: company.revenue_growth_annual_pct ?? undefined,
        cashUpdatedAt: company.cash_updated_at || undefined,
        burnRateUpdatedAt: company.burn_rate_updated_at || undefined,
        runwayUpdatedAt: company.runway_updated_at || undefined,
        revenueUpdatedAt: company.revenue_updated_at || undefined,
        grossMarginUpdatedAt: company.gross_margin_updated_at || undefined,
        revenueDocumentId: company.revenue_document_id || undefined,
        burnRateDocumentId: company.burn_rate_document_id || undefined,
        runwayDocumentId: company.runway_document_id || undefined,
        grossMarginDocumentId: company.gross_margin_document_id || undefined,
        cashDocumentId: company.cash_document_id || undefined,
      };
      // Spread extra_data so CSV/import columns (round, lead, description, etc.) appear on the object for the grid
      const extra = company.extra_data && typeof company.extra_data === 'object' ? company.extra_data : {};
      return { ...base, ...extra };
    });

    return NextResponse.json(portfolioCompanies);
  } catch (error) {
    console.error('Error in GET /api/portfolio/[id]/companies:', error);
    return NextResponse.json({ 
      error: 'Internal server error' 
    }, { status: 500 });
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    
    if (!fundId || fundId.trim() === '') {
      return NextResponse.json({ 
        error: 'Fund ID is required' 
      }, { status: 400 });
    }
    
    if (!supabaseService) {
      console.error('Supabase service not initialized');
      const hasUrl = !!process.env.NEXT_PUBLIC_SUPABASE_URL;
      const hasKey = !!process.env.SUPABASE_SERVICE_ROLE_KEY;
      return NextResponse.json({ 
        error: 'Database connection not available',
        details: {
          hasUrl,
          hasKey,
          message: 'Missing required environment variables: NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY'
        }
      }, { status: 503 });
    }
    
    const body = await request.json();
    const { 
      name, 
      sector, 
      stage, 
      investmentAmount, 
      ownershipPercentage, 
      investmentDate,
      currentArr = 0,
      valuation = 0
    } = body;

    if (!name || name.trim() === '') {
      return NextResponse.json({ 
        error: 'Company name is required' 
      }, { status: 400 });
    }

    /**
     * Parse currency input from various formats (M/K/B notation, formatted strings)
     */
    const parseCurrencyInput = (value: any): number => {
      if (typeof value === 'number') return value;
      if (!value) return 0;
      
      // Remove currency symbols and whitespace
      let cleaned = value.toString().trim().replace(/[$€£¥,\s]/g, '');
      
      // Handle suffixes
      const upper = cleaned.toUpperCase();
      let multiplier = 1;
      
      if (upper.endsWith('B')) {
        multiplier = 1_000_000_000;
        cleaned = cleaned.slice(0, -1);
      } else if (upper.endsWith('M')) {
        multiplier = 1_000_000;
        cleaned = cleaned.slice(0, -1);
      } else if (upper.endsWith('K')) {
        multiplier = 1_000;
        cleaned = cleaned.slice(0, -1);
      }
      
      const num = parseFloat(cleaned);
      if (isNaN(num)) return 0;
      
      return num * multiplier;
    };

    // Validate and parse numeric values
    const parsedInvestmentAmount = parseCurrencyInput(investmentAmount);
    
    if (!parsedInvestmentAmount || isNaN(parsedInvestmentAmount) || parsedInvestmentAmount <= 0) {
      return NextResponse.json({ 
        error: 'Investment amount must be a positive number' 
      }, { status: 400 });
    }

    // Parse ARR - allow 0 but not negative
    const parsedArr = typeof currentArr === 'string' 
      ? (currentArr === '' ? null : parseFloat(currentArr))
      : currentArr;
    
    if (parsedArr !== null && (isNaN(parsedArr) || parsedArr < 0)) {
      return NextResponse.json({ 
        error: 'Current ARR must be a non-negative number or empty' 
      }, { status: 400 });
    }

    // Create new company in the companies table
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .insert({
        name: name.trim(),
        sector: sector?.trim() || null,
        funnel_status: stage || 'portfolio', // Use provided stage or default to portfolio
        total_invested_usd: parsedInvestmentAmount,
        ownership_percentage: ownershipPercentage ? parseFloat(ownershipPercentage) : null,
        first_investment_date: investmentDate || null,
        current_arr_usd: parsedArr !== null && parsedArr >= 0 ? parsedArr : null,
        fund_id: fundId,
        status: 'active'
      })
      .select()
      .single();

    if (companyError) {
      console.error('Error creating company:', companyError);
      console.error('Supabase error details:', JSON.stringify(companyError, null, 2));
      console.error('Request body:', JSON.stringify(body, null, 2));
      console.error('Fund ID:', fundId);
      
      // Check for common issues
      let errorMessage = companyError.message || String(companyError);
      let statusCode = 500;
      
      if (companyError.code === '42P01') {
        errorMessage = 'Companies table does not exist. Please run database migrations.';
        statusCode = 500;
      } else if (companyError.code === '42501') {
        errorMessage = 'Permission denied. Check RLS policies or service role key.';
        statusCode = 403;
      } else if (companyError.code === '23505') {
        errorMessage = `A company with the name "${name}" already exists in this fund.`;
        statusCode = 409; // Conflict
      } else if (companyError.code === '23503') {
        errorMessage = `Foreign key constraint violation. Fund ID ${fundId} may not exist or you don't have access to it.`;
        statusCode = 400;
      } else if (companyError.code === '23502') {
        // Try to identify which field is missing
        const missingField = companyError.message?.match(/column "(\w+)" violates not-null constraint/)?.[1];
        errorMessage = missingField 
          ? `Required field "${missingField}" is missing.`
          : 'Required field is missing. Check all required fields are provided.';
        statusCode = 400;
      }
      
      return NextResponse.json({ 
        error: 'Failed to create company',
        message: errorMessage,
        details: errorMessage,
        code: companyError.code,
        hint: companyError.hint,
        fullError: process.env.NODE_ENV === 'development' ? JSON.stringify(companyError, null, 2) : undefined
      }, { status: statusCode });
    }

    return NextResponse.json(company);
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const { searchParams } = new URL(request.url);
    const companyId = searchParams.get('companyId');

    if (!companyId) {
      return NextResponse.json({ error: 'Company ID is required' }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Delete portfolio company record
    const { error } = await supabaseService
      .from('companies')
      .delete()
      .eq('id', companyId)
      .eq('fund_id', fundId);

    if (error) {
      console.error('Error deleting portfolio company:', error);
      console.error('Supabase error details:', JSON.stringify(error, null, 2));
      return NextResponse.json({ 
        error: 'Failed to delete portfolio company',
        details: error.message || String(error),
        code: error.code
      }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error in DELETE /api/portfolio/[id]/companies:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 