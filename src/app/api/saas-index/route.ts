import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Fetch from publicsaascompanies.com
    const response = await fetch('https://www.publicsaascompanies.com/api/companies', {
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; VC-Platform/1.0)',
      },
      next: { revalidate: 3600 } // Cache for 1 hour
    });

    if (!response.ok) {
      // Fallback to hardcoded recent median values if API fails
      const fallbackMedian = 5.2; // Median EV/Revenue for SaaS as of 2024
      const dlomAdjusted = fallbackMedian * 0.7; // Apply 30% DLOM
      
      return NextResponse.json({
        median_ev_revenue: fallbackMedian,
        dlom_adjusted: dlomAdjusted,
        dlom_percentage: 30,
        source: 'fallback',
        timestamp: new Date().toISOString()
      });
    }

    const data = await response.json();
    
    // Calculate median EV/Revenue multiple
    const companies = data.companies || data;
    const validMultiples = companies
      .filter((c: any) => c.ev && c.revenue && c.revenue > 0)
      .map((c: any) => c.ev / c.revenue)
      .filter((m: number) => m > 0 && m < 100) // Filter outliers
      .sort((a: number, b: number) => a - b);
    
    const median = validMultiples.length > 0
      ? validMultiples[Math.floor(validMultiples.length / 2)]
      : 5.2; // Fallback median
    
    const dlomAdjusted = median * 0.7; // Apply 30% DLOM
    
    return NextResponse.json({
      median_ev_revenue: median,
      dlom_adjusted: dlomAdjusted,
      dlom_percentage: 30,
      total_companies: validMultiples.length,
      source: 'live',
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Error fetching SaaS index:', error);
    
    // Return fallback values on error
    const fallbackMedian = 5.2;
    const dlomAdjusted = fallbackMedian * 0.7;
    
    return NextResponse.json({
      median_ev_revenue: fallbackMedian,
      dlom_adjusted: dlomAdjusted,
      dlom_percentage: 30,
      source: 'fallback',
      timestamp: new Date().toISOString(),
      error: 'Failed to fetch live data'
    });
  }
}