import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

if (!supabaseService) {
  throw new Error('Supabase service not configured');
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const fundId = searchParams.get('fund_id');
    const companyId = searchParams.get('company_id');
    const dateFrom = searchParams.get('date_from');
    const dateTo = searchParams.get('date_to');

    // Build query for processed_documents
    let query = supabaseService
      .from('processed_documents')
      .select(`
        id,
        company_id,
        fund_id,
        processed_at,
        extracted_data,
        document_type,
        companies!inner(id, name, fund_id)
      `)
      .eq('status', 'completed')
      .not('company_id', 'is', null)
      .order('processed_at', { ascending: true });

    // Filter by fund_id if provided
    if (fundId) {
      query = query.eq('fund_id', fundId);
    }

    // Filter by company_id if provided
    if (companyId) {
      query = query.eq('company_id', companyId);
    }

    // Filter by date range if provided
    if (dateFrom) {
      query = query.gte('processed_at', dateFrom);
    }
    if (dateTo) {
      query = query.lte('processed_at', dateTo);
    }

    const { data: documents, error } = await query;

    if (error) {
      console.error('Error querying ledger data:', error);
      return NextResponse.json({ error: 'Failed to fetch ledger data' }, { status: 500 });
    }

    // Transform documents into comprehensive time-series ledger data
    const timeSeriesData = (documents || [])
      .map((doc: any) => {
        const extractedData = doc.extracted_data || {};
        const financialMetrics = extractedData.financial_metrics || {};
        const capTable = extractedData.cap_table || {};
        const fundingAnalysis = extractedData.funding_analysis || {};
        const companyInfo = extractedData.company_info || {};
        const valuationData = extractedData.valuation || {};
        
        // Extract revenue/ARR values
        const revenue = financialMetrics.revenue || 
                       financialMetrics.annual_revenue ||
                       financialMetrics.total_revenue;
        const arr = financialMetrics.arr || 
                   financialMetrics.annual_recurring_revenue ||
                   financialMetrics.recurring_revenue ||
                   financialMetrics.current_arr;
        
        // Extract cap table data
        const sharesOutstanding = capTable.shares_outstanding || 
                                 capTable.total_shares ||
                                 capTable.outstanding_shares ||
                                 financialMetrics.shares_outstanding;
        const investors = capTable.investors || 
                         fundingAnalysis.investors ||
                         extractedData.investors || [];
        
        // Extract valuation data
        const valuation = valuationData.value ||
                         valuationData.valuation ||
                         fundingAnalysis.valuation ||
                         (fundingAnalysis.rounds && fundingAnalysis.rounds.length > 0 
                           ? fundingAnalysis.rounds[fundingAnalysis.rounds.length - 1].valuation 
                           : null);
        const valuationMethod = valuationData.method ||
                               valuationData.valuation_method ||
                               extractedData.valuation_method ||
                               null;
        const preMoneyValuation = fundingAnalysis.pre_money_valuation ||
                                 capTable.pre_money_valuation ||
                                 null;
        const postMoneyValuation = fundingAnalysis.post_money_valuation ||
                                  capTable.post_money_valuation ||
                                  null;
        
        // Calculate share price if we have valuation and shares
        let sharePrice = null;
        if (valuation && sharesOutstanding && sharesOutstanding > 0) {
          sharePrice = valuation / sharesOutstanding;
        } else if (postMoneyValuation && sharesOutstanding && sharesOutstanding > 0) {
          sharePrice = postMoneyValuation / sharesOutstanding;
        } else if (preMoneyValuation && sharesOutstanding && sharesOutstanding > 0) {
          sharePrice = preMoneyValuation / sharesOutstanding;
        }
        
        // Extract currency (default to USD)
        const currency = extractedData.currency ||
                        financialMetrics.currency ||
                        fundingAnalysis.currency ||
                        'USD';
        
        // Get company info
        const company = doc.companies || {};
        const companyName = companyInfo.company_name || 
                           extractedData.company || 
                           extractedData.company_name ||
                           company.name || 'Unknown';
        
        // Get fund info from company or document
        const fundId = doc.fund_id || company.fund_id || null;
        
        // Get date from processed_at or from extracted_data
        let date = doc.processed_at;
        if (extractedData.date) {
          date = extractedData.date;
        } else if (extractedData.period_date) {
          date = extractedData.period_date;
        } else if (extractedData.report_date) {
          date = extractedData.report_date;
        } else if (companyInfo.meeting_date) {
          date = companyInfo.meeting_date;
        }

        // Include all entries (not just those with revenue)
        return {
          date,
          company_id: doc.company_id,
          company_name: companyName,
          fund_id: fundId,
          // Financial metrics
          revenue: revenue || null,
          arr: arr || null,
          burn_rate: financialMetrics.burn_rate || null,
          runway_months: financialMetrics.runway_months || null,
          gross_margin: financialMetrics.gross_margin || null,
          cash_balance: financialMetrics.cash_balance || 
                       financialMetrics.cash_in_bank ||
                       null,
          // Cap table data
          shares_outstanding: sharesOutstanding || null,
          investors: Array.isArray(investors) ? investors : [],
          // Valuation data
          valuation: valuation || postMoneyValuation || preMoneyValuation || null,
          valuation_method: valuationMethod || null,
          pre_money_valuation: preMoneyValuation || null,
          post_money_valuation: postMoneyValuation || null,
          share_price: sharePrice || null,
          currency: currency,
          // Other extracted data
          document_id: doc.id,
          document_type: doc.document_type,
          processed_at: doc.processed_at,
          // Include full extracted_data for flexibility
          extracted_data: extractedData
        };
      })
      .filter((entry: any) => entry !== null)
      .sort((a: any, b: any) => {
        // Sort by date
        const dateA = new Date(a.date).getTime();
        const dateB = new Date(b.date).getTime();
        return dateA - dateB;
      });

    // Group by company for summary
    const byCompany = timeSeriesData.reduce((acc: any, entry: any) => {
      if (!acc[entry.company_id]) {
        acc[entry.company_id] = {
          company_id: entry.company_id,
          company_name: entry.company_name,
          fund_id: entry.fund_id,
          entries: [],
          latest_revenue: null,
          latest_arr: null,
          latest_valuation: null,
          latest_valuation_method: null,
          latest_share_price: null,
          latest_shares_outstanding: null,
          latest_investors: [],
          latest_currency: 'USD',
          latest_date: null
        };
      }
      acc[entry.company_id].entries.push(entry);
      
      // Track latest values for each metric
      if (entry.revenue && (!acc[entry.company_id].latest_revenue || entry.revenue > acc[entry.company_id].latest_revenue)) {
        acc[entry.company_id].latest_revenue = entry.revenue;
      }
      if (entry.arr && (!acc[entry.company_id].latest_arr || entry.arr > acc[entry.company_id].latest_arr)) {
        acc[entry.company_id].latest_arr = entry.arr;
      }
      if (entry.valuation) {
        acc[entry.company_id].latest_valuation = entry.valuation;
        acc[entry.company_id].latest_valuation_method = entry.valuation_method;
      }
      if (entry.share_price) {
        acc[entry.company_id].latest_share_price = entry.share_price;
      }
      if (entry.shares_outstanding) {
        acc[entry.company_id].latest_shares_outstanding = entry.shares_outstanding;
      }
      if (entry.investors && entry.investors.length > 0) {
        acc[entry.company_id].latest_investors = entry.investors;
      }
      if (entry.currency) {
        acc[entry.company_id].latest_currency = entry.currency;
      }
      if (!acc[entry.company_id].latest_date || new Date(entry.date) > new Date(acc[entry.company_id].latest_date)) {
        acc[entry.company_id].latest_date = entry.date;
      }
      return acc;
    }, {});

    const summary = Object.values(byCompany);

    return NextResponse.json({
      time_series: timeSeriesData,
      by_company: summary,
      total_entries: timeSeriesData.length,
      companies_count: summary.length
    });

  } catch (error) {
    console.error('Ledger API error:', error);
    return NextResponse.json({ 
      error: 'Failed to process ledger request',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}
