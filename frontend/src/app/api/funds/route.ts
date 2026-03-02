import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function GET(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const { searchParams } = new URL(request.url);
    const type = searchParams.get('type') || 'all';
    const limit = parseInt(searchParams.get('limit') || '100', 10);

    let funds = [];
    let fundAccounts = [];
    let regulatoryFilings = [];

    // Fetch funds if funds table exists
    try {
      const { data: fundsData, error: fundsError } = await supabaseService
        .from('funds')
        .select('*')
        .order('name', { ascending: true })
        .limit(limit);

      if (!fundsError) {
        funds = fundsData || [];
      }
    } catch (error) {
      console.log('funds table not found or error occurred');
    }

    // Fetch fund accounts if fund_accounts table exists
    try {
      const { data: accountsData, error: accountsError } = await supabaseService
        .from('fund_accounts')
        .select('*')
        .order('account_name', { ascending: true })
        .limit(limit);

      if (!accountsError) {
        fundAccounts = accountsData || [];
      }
    } catch (error) {
      console.log('fund_accounts table not found or error occurred');
    }

    // Fetch regulatory filings if regulatory_filings table exists
    try {
      const { data: filingsData, error: filingsError } = await supabaseService
        .from('regulatory_filings')
        .select('*')
        .order('due_date', { ascending: true })
        .limit(limit);

      if (!filingsError) {
        regulatoryFilings = filingsData || [];
      }
    } catch (error) {
      console.log('regulatory_filings table not found or error occurred');
    }

    // Return funds array directly for backward compatibility
    // Also support legacy format with nested structure
    const format = searchParams.get('format') || 'array';
    
    if (format === 'legacy') {
      return NextResponse.json({
        funds,
        fundAccounts,
        regulatoryFilings,
        totalFunds: funds.length,
        totalFundAccounts: fundAccounts.length,
        totalRegulatoryFilings: regulatoryFilings.length
      });
    }
    
    // Default: return funds array directly
    return NextResponse.json(funds);
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
    const { type, data } = body;

    let result;

    if (type === 'fund') {
      const { data: insertedData, error } = await supabaseService
        .from('funds')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create fund' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else if (type === 'fund_account') {
      const { data: insertedData, error } = await supabaseService
        .from('fund_accounts')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create fund account' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else if (type === 'regulatory_filing') {
      const { data: insertedData, error } = await supabaseService
        .from('regulatory_filings')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create regulatory filing' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else {
      return NextResponse.json({ error: 'Invalid type specified' }, { status: 400 });
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 