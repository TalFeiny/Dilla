import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Return a minimal valid response for testing
    const testResponse = {
      company_data: {
        name: body.company_name || 'TestCo',
        revenue: body.current_arr || 5.0,
        growth_rate: body.growth_rate || 0.30,
        sector: body.sector || 'SaaS'
      },
      summary: {
        expected_exit_value: 1500.5,
        median_exit_value: 1200.0,
        total_scenarios: 499,
        success_probability: 0.75,
        mega_exit_probability: 0.15,
        ipo_probability: 0.25,
        outlier_score: 85
      },
      market_research: {
        exit_comparables: [
          {
            company: 'Example Corp',
            sector: 'SaaS',
            ev_revenue_multiple: 8.5,
            deal_value: 500,
            date: '2024'
          }
        ],
        direct_competitors: ['Competitor A', 'Competitor B'],
        potential_acquirers: ['Microsoft', 'Google', 'Salesforce']
      },
      scenarios: [
        {
          id: 1,
          type: 'strategic_acquisition',
          probability: 0.30,
          exit_value: 1000,
          revenue_multiple: 10,
          description: 'Strategic acquisition scenario'
        },
        {
          id: 2,
          type: 'ipo',
          probability: 0.25,
          exit_value: 2000,
          revenue_multiple: 15,
          description: 'IPO scenario'
        }
      ],
      exit_distribution_chart: '',
      analysis_timestamp: new Date().toISOString()
    };
    
    console.log('Returning debug response:', testResponse);
    return NextResponse.json(testResponse);
    
  } catch (error) {
    console.error('Debug API error:', error);
    return NextResponse.json({ 
      error: 'Debug API error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}