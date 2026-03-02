import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const { searchParams } = new URL(request.url);
    const limitParam = searchParams.get('limit');
    const offset = parseInt(searchParams.get('offset') || '0', 10);
    const fieldsParam = searchParams.get('fields');
    
    // Determine which fields to select
    let selectString = '*';
    if (fieldsParam === 'minimal') {
      // Minimal fields for dropdowns and lists
      selectString = 'id,name,current_arr_usd,sector,current_valuation_usd,year_founded';
    } else if (fieldsParam) {
      // Custom fields if specified
      selectString = fieldsParam;
    }

    // Build query with appropriate fields
    let query = supabaseService
      .from('companies')
      .select(selectString)
      .order('name', { ascending: true });

    // Apply limit and offset
    if (limitParam) {
      const limit = Math.min(parseInt(limitParam, 10), 1000); // Cap at 1000 for performance
      query = query.range(offset, offset + limit - 1);
    } else {
      // Default to 500 records if no limit specified
      query = query.range(offset, offset + 499);
    }

    const { data, error } = await query;

    if (error) {
      console.error('Supabase error:', error);
      return NextResponse.json({ error: 'Failed to fetch companies' }, { status: 500 });
    }

    // Add cache headers for better performance
    return NextResponse.json(data || [], {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const body = await request.json();
    const { name, sector, stage, funnel_status, ...otherFields } = body;

    if (!name || name.trim() === '') {
      return NextResponse.json({ 
        error: 'Company name is required' 
      }, { status: 400 });
    }

    // Prepare company data for insertion
    // For sourcing companies (no fundId), don't require investmentAmount
    const companyData: any = {
      name: name.trim(),
      sector: sector?.trim() || null,
      funnel_status: funnel_status || stage || 'prospect', // Default to prospect for sourcing
      status: 'active',
    };

    // Only include investment-related fields if provided (for portfolio companies)
    if (otherFields.total_invested_usd !== undefined) {
      companyData.total_invested_usd = otherFields.total_invested_usd;
    }
    if (otherFields.ownership_percentage !== undefined) {
      companyData.ownership_percentage = otherFields.ownership_percentage;
    }
    if (otherFields.first_investment_date) {
      companyData.first_investment_date = otherFields.first_investment_date;
    }
    if (otherFields.current_arr_usd !== undefined) {
      companyData.current_arr_usd = otherFields.current_arr_usd;
    }
    if (otherFields.fund_id) {
      companyData.fund_id = otherFields.fund_id;
    }

    const { data, error } = await supabaseService
      .from('companies')
      .insert([companyData])
      .select();

    if (error) {
      console.error('Supabase error:', error);
      return NextResponse.json({ 
        error: 'Failed to create company',
        details: error.message 
      }, { status: 500 });
    }

    return NextResponse.json(data?.[0] || {});
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}