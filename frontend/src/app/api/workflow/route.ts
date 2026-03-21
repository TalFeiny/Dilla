import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/** POST — save a workflow (create or update) */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, name, description, nodes, edges, is_template, user_id, fund_id } = body;

    if (!nodes || !Array.isArray(nodes)) {
      return NextResponse.json({ error: 'nodes is required' }, { status: 400 });
    }

    if (id) {
      // Update existing
      const { data, error } = await supabaseService
        .from('workflows')
        .update({
          name: name || 'Untitled Workflow',
          description,
          nodes,
          edges: edges || [],
          is_template: is_template || false,
          updated_at: new Date().toISOString(),
        })
        .eq('id', id)
        .select()
        .single();

      if (error) {
        console.error('[workflow/save] Update error:', error);
        return NextResponse.json({ error: error.message }, { status: 500 });
      }
      return NextResponse.json(data);
    }

    // Create new
    const { data, error } = await supabaseService
      .from('workflows')
      .insert({
        name: name || 'Untitled Workflow',
        description,
        nodes,
        edges: edges || [],
        is_template: is_template || false,
        user_id: user_id || null,
        fund_id: fund_id || null,
      })
      .select()
      .single();

    if (error) {
      console.error('[workflow/save] Insert error:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json(data, { status: 201 });
  } catch (err) {
    console.error('[workflow/save] Exception:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

/** GET — list all workflows */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get('user_id');
    const fundId = searchParams.get('fund_id');

    let query = supabaseService
      .from('workflows')
      .select('id, name, description, is_template, created_at, updated_at')
      .order('updated_at', { ascending: false })
      .limit(50);

    if (userId) query = query.eq('user_id', userId);
    if (fundId) query = query.eq('fund_id', fundId);

    const { data, error } = await query;

    if (error) {
      console.error('[workflow/list] Error:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({ workflows: data || [] });
  } catch (err) {
    console.error('[workflow/list] Exception:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
