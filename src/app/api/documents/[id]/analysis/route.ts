import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

// Cache for analysis data
const analysisCache = new Map<string, { data: any; timestamp: number }>();
const CACHE_TTL = 0; // Disable cache temporarily to force fresh data

if (!supabaseService) {
  throw new Error('Supabase service not configured');
}

// Transform database data to match frontend interface
function transformAnalysisData(dbData: any) {
  console.log('Raw database data:', JSON.stringify(dbData, null, 2));
  
  const extractedData = dbData.extracted_data || {};
  const processingSummary = dbData.processing_summary || {};
  const comparablesAnalysis = dbData.comparables_analysis || {};
  const issueAnalysis = dbData.issue_analysis || {};

  console.log('Extracted data:', extractedData);
  console.log('Issue analysis:', issueAnalysis);

  // Extract company name from filename or business updates
  let companyName = extractedData.company_info?.name || extractedData.name;
  if (!companyName && dbData.storage_path) {
    const filename = dbData.storage_path.split('/').pop() || '';
    // Handle common filename patterns
    if (filename.toLowerCase().includes('equitee')) {
      companyName = 'Equitee';
    } else if (filename.toLowerCase().includes('pliant')) {
      companyName = 'Pliant';
    } else if (filename.toLowerCase().includes('extract')) {
      companyName = 'Extract Company';
    } else if (filename.toLowerCase().includes('may_investor_update')) {
      companyName = 'May Investor Update Company';
    } else {
      companyName = filename.replace(/\.(pdf|docx?|txt)$/i, '').replace(/\s+update$/i, '');
    }
  }

  // Extract sector from business updates, industry terms, or sector classification
  let sector = extractedData.company_info?.sector || extractedData.sector;
  
  // Check for explicit sector classification first
  if (!sector && extractedData.sector_classification?.primary_sector) {
    sector = extractedData.sector_classification.primary_sector;
  }
  
  // Fallback to industry terms analysis
  if (!sector && extractedData.extracted_entities?.industry_terms) {
    const industryTerms = extractedData.extracted_entities.industry_terms;
    if (industryTerms.includes('IPO') || industryTerms.includes('liquidity event')) {
      sector = 'Fintech';
    } else if (industryTerms.includes('FCA regulated')) {
      sector = 'Regulated Financial Services';
    } else if (industryTerms.includes('SaaS') || industryTerms.includes('software')) {
      sector = 'SaaS';
    } else if (industryTerms.includes('AI') || industryTerms.includes('machine learning')) {
      sector = 'AI';
    } else if (industryTerms.includes('fintech') || industryTerms.includes('financial')) {
      sector = 'Fintech';
    }
  }

  // Extract stage from business updates or document type
  let stage = extractedData.company_info?.stage || extractedData.stage;
  if (!stage) {
    if (dbData.document_type === 'monthly_update') {
      stage = 'Growth Stage';
    } else if (extractedData.business_updates?.achievements?.some((a: string) => a.includes('Pre IPO'))) {
      stage = 'Pre-IPO';
    }
  }

  return {
    id: dbData.id?.toString() || 'unknown',
    raw_text_preview: dbData.raw_text_preview || '',
    raw_text: dbData.raw_text_preview || '', // Add both for compatibility
    document_metadata: {
      filename: dbData.storage_path?.split('/').pop()?.replace('.pdf', '') || 'Unknown Document',
      processed_at: dbData.processed_at || new Date().toISOString(),
      document_type: dbData.document_type || 'unknown',
      status: dbData.status || 'unknown',
    },
    extracted_data: {
      financial_metrics: {
        arr: extractedData.financial_metrics?.arr || extractedData.arr || null,
        burn_rate: extractedData.financial_metrics?.burn_rate || extractedData.burn_rate || null,
        runway_months: extractedData.financial_metrics?.runway_months || extractedData.runway_months || null,
        growth_rate: extractedData.financial_metrics?.growth_rate || extractedData.growth_rate || null,
        revenue: extractedData.financial_metrics?.revenue || null,
        mrr: extractedData.financial_metrics?.mrr || null,
        cash_balance: extractedData.financial_metrics?.cash_balance || null,
      },
      operational_metrics: {
        headcount: extractedData.operational_metrics?.headcount || null,
        new_hires: extractedData.operational_metrics?.new_hires || null,
        customer_count: extractedData.operational_metrics?.customer_count || null,
        churn_rate: extractedData.operational_metrics?.churn_rate || null,
        cac: extractedData.operational_metrics?.cac || null,
        ltv: extractedData.operational_metrics?.ltv || null,
      },
      company_info: {
        name: companyName,
        sector: sector,
        stage: stage,
        employees: extractedData.company_info?.employees || extractedData.employees || null,
        founded_year: extractedData.company_info?.founded_year || extractedData.founded_year || null,
        valuation: extractedData.company_info?.valuation || extractedData.valuation || null,
        funding_raised: extractedData.company_info?.funding_raised || extractedData.funding_raised || null,
        business_model: extractedData.business_updates?.product_updates?.join(', ') || null,
        achievements: extractedData.business_updates?.achievements || [],
        challenges: extractedData.business_updates?.challenges || [],
        competitors: extractedData.extracted_entities?.competitors_mentioned || [],
        industry_terms: extractedData.extracted_entities?.industry_terms || [],
        partners_mentioned: extractedData.extracted_entities?.partners_mentioned || [],
      },
    },
    comparables_analysis: {
      companies_found: comparablesAnalysis.comparable_companies?.length || 0,
      ma_transactions: comparablesAnalysis.ma_transactions || [],
      comparable_companies: Array.isArray(comparablesAnalysis.comparable_companies) 
        ? comparablesAnalysis.comparable_companies.map((company: any) => ({
            name: typeof company.name === 'string' ? company.name : 'Unknown',
            sector: typeof company.industry === 'string' ? company.industry : 'Unknown',
            valuation: typeof company.market_cap === 'number' ? `$${(company.market_cap / 1000000000).toFixed(1)}B` : 'Unknown',
            revenue: company.revenue_ttm ? `$${(company.revenue_ttm / 1000000000).toFixed(1)}B` : 'Unknown',
            growth_rate: company.key_metrics?.revenue_growth ? `${(company.key_metrics.revenue_growth * 100).toFixed(1)}%` : 'Unknown',
            ticker: company.ticker || 'Unknown',
            description: company.description || '',
            relevance_score: company.relevance_score || 0,
          }))
        : [],
      ma_deals: Array.isArray(comparablesAnalysis.ma_transactions) 
        ? comparablesAnalysis.ma_transactions.map((deal: any) => ({
            company_name: deal.target_company || 'Unknown',
            deal_value: deal.deal_value ? `$${(deal.deal_value / 1000000000).toFixed(1)}B` : 'Unknown',
            deal_date: deal.deal_date || 'Unknown',
            acquirer: deal.acquirer || 'Unknown',
            description: deal.description || '',
            relevance_score: deal.relevance_score || 0,
          }))
        : [],
      valuation_multiples: comparablesAnalysis.valuation_multiples || {},
      analysis_summary: comparablesAnalysis.analysis_summary || {},
    },
    issue_analysis: {
      red_flags: Array.isArray(issueAnalysis.red_flags) 
        ? issueAnalysis.red_flags.map((flag: any) => ({
            severity: 'medium' as const,
            description: typeof flag === 'string' ? flag : 'Unknown issue',
            category: 'general'
          }))
        : [],
      overall_sentiment: issueAnalysis.overall_sentiment || 'neutral',
      confidence_level: issueAnalysis.confidence_level || 'medium',
      key_risks: Array.isArray(issueAnalysis.key_concerns) ? issueAnalysis.key_concerns : [],
      positive_indicators: Array.isArray(issueAnalysis.positive_indicators) ? issueAnalysis.positive_indicators : [],
      recommendations: Array.isArray(issueAnalysis.recommendations) ? issueAnalysis.recommendations : [],
      missing_metrics: Array.isArray(issueAnalysis.missing_metrics) ? issueAnalysis.missing_metrics : [],
      business_concerns: Array.isArray(issueAnalysis.business_concerns) ? issueAnalysis.business_concerns : [],
      language_concerns: Array.isArray(issueAnalysis.language_concerns) ? issueAnalysis.language_concerns : [],
    },
    processing_summary: {
      total_pages: processingSummary.text_length ? Math.ceil(processingSummary.text_length / 500) : 1, // Estimate pages
      processing_time_seconds: processingSummary.processing_time_seconds || 0,
      confidence_score: processingSummary.confidence_score || 75,
    },
  };
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
): Promise<NextResponse> {
  try {
    const { id: documentId } = await params;
    
    if (!documentId) {
      return NextResponse.json({ error: 'Document ID is required' }, { status: 400 });
    }

    // Check cache first
    const cached = analysisCache.get(documentId);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return NextResponse.json(cached.data, {
        headers: {
          'Cache-Control': 'public, max-age=300, stale-while-revalidate=600',
          'X-Cache': 'HIT'
        }
      });
    }

    // Fetch from database with optimized query
    let data, error;
    
    try {
      const result = await supabaseService
        .from('processed_documents')
        .select('*')
        .eq('id', documentId)
        .single();
      
      data = result.data;
      error = result.error;
      
    } catch (dbError) {
      console.error('Database error:', dbError);
      return NextResponse.json({ error: 'Database request failed' }, { status: 500 });
    }

    if (error) {
      console.error('Database error:', error);
      return NextResponse.json({ error: 'Document not found' }, { status: 404 });
    }

    if (!data) {
      return NextResponse.json({ error: 'Document not found' }, { status: 404 });
    }

    // Transform the data to match frontend interface
    const analysisData = transformAnalysisData(data);

      // Check if we have meaningful analysis data - be more comprehensive
  const hasAnalysisData = analysisData.extracted_data?.financial_metrics?.arr || 
                         analysisData.extracted_data?.financial_metrics?.burn_rate ||
                         analysisData.extracted_data?.financial_metrics?.growth_rate ||
                         analysisData.extracted_data?.financial_metrics?.revenue ||
                         analysisData.extracted_data?.financial_metrics?.cash_balance ||
                         analysisData.extracted_data?.financial_metrics?.runway_months ||
                         analysisData.extracted_data?.company_info?.name ||
                         analysisData.extracted_data?.company_info?.achievements?.length > 0 ||
                         analysisData.extracted_data?.company_info?.challenges?.length > 0 ||
                         analysisData.extracted_data?.company_info?.competitors?.length > 0 ||
                         analysisData.extracted_data?.company_info?.industry_terms?.length > 0 ||
                         analysisData.extracted_data?.company_info?.partners_mentioned?.length > 0 ||
                         analysisData.issue_analysis?.red_flags?.length > 0 ||
                         analysisData.issue_analysis?.key_risks?.length > 0 ||
                         analysisData.issue_analysis?.key_concerns?.length > 0 ||
                         analysisData.issue_analysis?.business_concerns?.length > 0 ||
                         analysisData.issue_analysis?.missing_metrics?.length > 0 ||
                         analysisData.issue_analysis?.recommendations?.length > 0 ||
                         analysisData.comparables_analysis?.companies_found > 0 ||
                         analysisData.comparables_analysis?.ma_transactions?.length > 0 ||
                         analysisData.comparables_analysis?.valuation_multiples?.ev_revenue_multiples ||
                         data.status === 'completed';

    console.log('Has analysis data:', hasAnalysisData);
    console.log('Document status:', data.status);

    if (!hasAnalysisData && data.status !== 'completed') {
      // If no analysis data and not completed, try to trigger processing
      console.log('No analysis data found, document may need processing');
      return NextResponse.json({
        ...analysisData,
        processing_required: true,
        message: 'Document analysis not yet completed. Please wait for processing to finish.'
      }, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0',
          'X-Cache': 'MISS'
        }
      });
    }

    // If we have analysis data but status is failed, update the status to completed
    if (hasAnalysisData && data.status === 'failed') {
      console.log('Document has analysis data but status is failed, updating to completed');
      try {
        await supabaseService
          .from('processed_documents')
          .update({ status: 'completed' })
          .eq('id', documentId);
      } catch (updateError) {
        console.error('Failed to update document status:', updateError);
      }
    }

    // Cache the result
    analysisCache.set(documentId, {
      data: analysisData,
      timestamp: Date.now()
    });

    return NextResponse.json(analysisData, {
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
        'X-Cache': 'MISS'
      }
    });

  } catch (error: unknown) {
    console.error('GET /api/documents/[id]/analysis error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 