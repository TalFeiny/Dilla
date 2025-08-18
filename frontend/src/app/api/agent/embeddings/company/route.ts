import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// POST: Search companies using semantic/hybrid search
export async function POST(request: NextRequest) {
  try {
    const { query, mode = 'hybrid', limit = 10 } = await request.json();
    
    if (!query) {
      return NextResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      );
    }
    
    let results;
    
    if (mode === 'semantic') {
      // Pure semantic search
      const { data, error } = await supabase.rpc('search_similar_companies', {
        query,
        limit_count: limit,
        min_similarity: 0.3
      });
      
      if (error) throw error;
      results = data;
      
    } else if (mode === 'hybrid') {
      // Hybrid search (text + semantic)
      const { data, error } = await supabase.rpc('hybrid_company_search', {
        query,
        limit_count: limit
      });
      
      if (error) throw error;
      results = data;
      
    } else {
      // Traditional text search fallback
      const { data, error } = await supabase
        .from('companies')
        .select('id, name, sector, description')
        .or(`name.ilike.%${query}%,description.ilike.%${query}%,sector.ilike.%${query}%`)
        .limit(limit);
      
      if (error) throw error;
      results = data;
    }
    
    return NextResponse.json({
      success: true,
      mode,
      query,
      results,
      count: results?.length || 0
    });
    
  } catch (error) {
    console.error('Company search error:', error);
    return NextResponse.json(
      { error: 'Failed to search companies' },
      { status: 500 }
    );
  }
}

// GET: Update company embeddings (admin endpoint)
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const updateAll = searchParams.get('updateAll') === 'true';
    
    if (updateAll) {
      // Update all company embeddings
      const { error } = await supabase.rpc('update_company_embeddings');
      
      if (error) throw error;
      
      return NextResponse.json({
        success: true,
        message: 'Company embeddings updated'
      });
    }
    
    // Get companies with missing embeddings
    const { data, error } = await supabase
      .from('companies')
      .select('id, name')
      .is('embedding', null)
      .limit(100);
    
    if (error) throw error;
    
    return NextResponse.json({
      success: true,
      companiesWithoutEmbeddings: data?.length || 0,
      companies: data
    });
    
  } catch (error) {
    console.error('Error updating company embeddings:', error);
    return NextResponse.json(
      { error: 'Failed to update embeddings' },
      { status: 500 }
    );
  }
}