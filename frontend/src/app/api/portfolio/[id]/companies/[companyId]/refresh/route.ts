import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  try {
    const { id: fundId, companyId } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Verify company belongs to this fund
    const { data: company, error: fetchError } = await supabaseService
      .from('companies')
      .select('id, fund_id, name')
      .eq('id', companyId)
      .single();

    if (fetchError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    if (company.fund_id !== fundId) {
      return NextResponse.json({ error: 'Company does not belong to this fund' }, { status: 403 });
    }

    // Get all processed documents for this company
    const { data: documents, error: docsError } = await supabaseService
      .from('processed_documents')
      .select('id, extracted_data, processed_at')
      .eq('company_id', companyId)
      .eq('status', 'completed')
      .order('processed_at', { ascending: false })
      .limit(50); // Get recent documents

    if (docsError) {
      console.error('Error fetching documents:', docsError);
      return NextResponse.json({ error: 'Failed to fetch documents' }, { status: 500 });
    }

    if (!documents || documents.length === 0) {
      return NextResponse.json({ 
        message: 'No documents found for this company',
        updated: false 
      });
    }

    // Get current company data
    const { data: currentCompany, error: companyError } = await supabaseService
      .from('companies')
      .select('current_arr_usd, cash_in_bank_usd, burn_rate_monthly_usd, runway_months, gross_margin, total_invested_usd, ownership_percentage, first_investment_date')
      .eq('id', companyId)
      .single();

    if (companyError || !currentCompany) {
      return NextResponse.json({ error: 'Failed to fetch company data' }, { status: 500 });
    }

    // Aggregate financial metrics from all documents
    const now = new Date().toISOString();
    const updateData: any = {};
    let hasUpdates = false;

    // Process each document's extracted_data
    for (const doc of documents) {
      const extractedData = doc.extracted_data || {};
      const financialMetrics = extractedData.financial_metrics || {};

      // Revenue/ARR - use highest value
      const revenue = financialMetrics.revenue || financialMetrics.arr || financialMetrics.annual_recurring_revenue;
      if (revenue && typeof revenue === 'number' && revenue > 0) {
        const currentArr = updateData.current_arr_usd || currentCompany.current_arr_usd || 0;
        if (revenue > currentArr) {
          updateData.current_arr_usd = revenue;
          updateData.revenue_updated_at = now;
          hasUpdates = true;
        }
      }

      // Cash in Bank - use most recent non-null value
      const cashInBank = financialMetrics.cash || financialMetrics.cash_in_bank || financialMetrics.cash_balance;
      if (cashInBank && typeof cashInBank === 'number' && cashInBank > 0) {
        if (!updateData.cash_in_bank_usd) {
          updateData.cash_in_bank_usd = cashInBank;
          updateData.cash_updated_at = now;
          hasUpdates = true;
        }
      }

      // Burn Rate - use most recent value
      const burnRate = financialMetrics.burn_rate || financialMetrics.monthly_burn || financialMetrics.net_burn;
      if (burnRate !== undefined && typeof burnRate === 'number') {
        if (!updateData.burn_rate_monthly_usd) {
          updateData.burn_rate_monthly_usd = Math.abs(burnRate);
          updateData.burn_rate_updated_at = now;
          hasUpdates = true;
        }
      }

      // Runway - use most recent value
      const runway = financialMetrics.runway || financialMetrics.runway_months || financialMetrics.months_of_runway;
      if (runway && typeof runway === 'number' && runway > 0) {
        if (!updateData.runway_months) {
          updateData.runway_months = runway;
          updateData.runway_updated_at = now;
          hasUpdates = true;
        }
      }

      // Gross Margin - use most recent value
      const grossMargin = financialMetrics.gross_margin || financialMetrics.gross_margin_pct;
      if (grossMargin !== undefined && typeof grossMargin === 'number') {
        if (!updateData.gross_margin) {
          const marginDecimal = grossMargin > 1 ? grossMargin / 100 : grossMargin;
          updateData.gross_margin = marginDecimal;
          updateData.gross_margin_updated_at = now;
          hasUpdates = true;
        }
      }
    }

    // Update company if we have changes (protect manual fields)
    if (hasUpdates) {
      updateData.updated_at = now;
      const { data: updatedCompany, error: updateError } = await supabaseService
        .from('companies')
        .update(updateData)
        .eq('id', companyId)
        .select()
        .single();

      if (updateError) {
        console.error('Error updating company:', updateError);
        return NextResponse.json({ error: 'Failed to update company' }, { status: 500 });
      }

      return NextResponse.json({
        success: true,
        message: 'Company data refreshed successfully',
        updated_fields: Object.keys(updateData).filter(k => k !== 'updated_at'),
        company: updatedCompany
      });
    } else {
      return NextResponse.json({
        success: true,
        message: 'No updates needed - data is already current',
        updated: false
      });
    }
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies/[companyId]/refresh:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
