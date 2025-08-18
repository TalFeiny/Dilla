import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    console.log('Test API received:', body);
    
    // Return a minimal but valid response to test
    const testResponse = {
      company_data: {
        name: body.company_name,
        revenue: body.current_arr,
        growth_rate: body.growth_rate,
        sector: body.sector
      },
      summary: {
        expected_exit_value: 250.5,
        median_exit_value: 180.3,
        total_scenarios: 499,
        success_probability: 0.78,
        mega_exit_probability: 0.15
      },
      market_research: {
        exit_comparables: [
          { target: "BambooHR", acquirer: "Private Equity", revenue_multiple: 12.5, sector: "HR Tech" }
        ],
        direct_competitors: [
          { name: "Remote", stage: "Series C" },
          { name: "Oyster", stage: "Series C" }
        ],
        potential_acquirers: [
          { name: "Microsoft", likelihood: "high", typical_multiple: 15 }
        ]
      },
      scenarios: [
        { id: 1, type: "ipo", exit_value: 5000, probability: 0.02, revenue_multiple: 10 },
        { id: 2, type: "strategic_acquisition", exit_value: 3000, probability: 0.05, revenue_multiple: 6 },
        { id: 3, type: "liquidation", exit_value: 10, probability: 0.01, revenue_multiple: 0.02 }
      ],
      outlier_analysis: {
        overall_outlier_score: 85,
        outlier_probability: 0.8
      },
      market_landscape: {
        submarket: "Global EOR Platform",
        incumbents: [{ name: "ADP", type: "public", market_cap: "$100B" }]
      },
      categorization: {
        sector: "SaaS",
        subsector: "HR Tech"
      },
      exit_distribution_chart: "",
      analysis_timestamp: new Date().toISOString()
    };
    
    return NextResponse.json(testResponse);
  } catch (error) {
    console.error('Test API error:', error);
    return NextResponse.json({ error: 'Test failed' }, { status: 500 });
  }
}