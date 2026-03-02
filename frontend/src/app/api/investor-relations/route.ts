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

    let allocations = [];
    let sentimentRecords = [];

    // Fetch LP allocations if lp_allocations table exists
    try {
      const { data: allocationsData, error: allocationsError } = await supabaseService
        .from('lp_allocations')
        .select('*')
        .order('allocation_date', { ascending: false })
        .limit(limit);

      if (!allocationsError) {
        allocations = allocationsData || [];
      }
    } catch (error) {
      console.log('lp_allocations table not found or error occurred');
    }

    // Fetch sentiment records if lp_sentiment table exists
    try {
      const { data: sentimentData, error: sentimentError } = await supabaseService
        .from('lp_sentiment')
        .select('*')
        .order('interaction_date', { ascending: false })
        .limit(limit);

      if (!sentimentError) {
        sentimentRecords = sentimentData || [];
      }
    } catch (error) {
      console.log('lp_sentiment table not found or error occurred');
    }

    return NextResponse.json({
      allocations,
      sentimentRecords,
      totalAllocations: allocations.length,
      totalSentimentRecords: sentimentRecords.length
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
    const { type, data } = body;

    let result;

    if (type === 'allocation') {
      const { data: insertedData, error } = await supabaseService
        .from('lp_allocations')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create allocation' }, { status: 500 });
      }

      result = insertedData?.[0] || {};
    } else if (type === 'sentiment') {
      const { data: insertedData, error } = await supabaseService
        .from('lp_sentiment')
        .insert([data])
        .select();

      if (error) {
        console.error('Supabase error:', error);
        return NextResponse.json({ error: 'Failed to create sentiment record' }, { status: 500 });
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