import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  try {
    const { id: fundId, companyId } = await params;
    const body = await request.json();

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Verify company belongs to this fund
    const { data: company, error: fetchError } = await supabaseService
      .from('companies')
      .select('id, fund_id')
      .eq('id', companyId)
      .single();

    if (fetchError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    if (company.fund_id !== fundId) {
      return NextResponse.json({ error: 'Company does not belong to this fund' }, { status: 403 });
    }

    // Coerce objects to primitives so we never store [object Object]
    const toString = (v: unknown): string | null => {
      if (v == null) return null;
      if (typeof v === 'string') return v.trim() || null;
      if (typeof v === 'object' && !Array.isArray(v) && v !== null) {
        const o = v as Record<string, unknown>;
        const x = o.value ?? o.displayValue ?? o.display_value ?? '';
        return typeof x === 'string' ? (x.trim() || null) : x != null ? String(x) : null;
      }
      return String(v);
    };
    const toNum = (v: unknown): number | null => {
      if (v == null) return null;
      if (typeof v === 'number' && !Number.isNaN(v)) return v;
      const n = typeof v === 'object' && v !== null && !Array.isArray(v)
        ? Number((v as Record<string, unknown>).value ?? (v as Record<string, unknown>).displayValue ?? NaN)
        : Number(v);
      return Number.isNaN(n) ? null : n;
    };

    // Build update object - only allow editing manual fields
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString()
    };

    // Manual fields that can be edited — always coerce to correct type
    // Never store id-like value as company name (fixes "companyb16366363" bug)
    const looksLikeId = (v: string | null): boolean => {
      if (v == null || v.trim() === '') return false;
      const s = v.trim();
      return /^company[a-z0-9]+$/i.test(s) || /^[a-f0-9-]{36}$/i.test(s) || /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(s);
    };
    if (body.name !== undefined) {
      const s = toString(body.name);
      if (s !== null) {
        if (looksLikeId(s)) {
          return NextResponse.json({ error: 'Company name cannot be an ID' }, { status: 400 });
        }
        updateData.name = s;
      }
    }
    if (body.total_invested_usd !== undefined) {
      const n = toNum(body.total_invested_usd);
      updateData.total_invested_usd = n;
    }
    if (body.ownership_percentage !== undefined) {
      const n = toNum(body.ownership_percentage);
      updateData.ownership_percentage = n;
    }
    if (body.first_investment_date !== undefined) {
      const s = toString(body.first_investment_date);
      updateData.first_investment_date = s;
    }
    if (body.sector !== undefined) {
      const s = toString(body.sector);
      updateData.sector = s;
    }
    if (body.investment_lead !== undefined) {
      const s = toString(body.investment_lead);
      updateData.investment_lead = s;
    }
    if (body.last_contacted_date !== undefined) {
      const s = toString(body.last_contacted_date);
      updateData.last_contacted_date = s;
    }
    // Financial/metric fields editable from matrix — coerce via toNum
    if (body.current_arr_usd !== undefined) {
      updateData.current_arr_usd = toNum(body.current_arr_usd);
      updateData.revenue_updated_at = new Date().toISOString();
    }
    if (body.burn_rate_monthly_usd !== undefined) {
      updateData.burn_rate_monthly_usd = toNum(body.burn_rate_monthly_usd);
      updateData.burn_rate_updated_at = new Date().toISOString();
    }
    if (body.runway_months !== undefined) {
      const v = toNum(body.runway_months);
      updateData.runway_months = v != null ? Math.floor(v) : null;
      updateData.runway_updated_at = new Date().toISOString();
    }
    if (body.gross_margin !== undefined) {
      let v = toNum(body.gross_margin);
      if (v != null && v > 1) v = v / 100;
      updateData.gross_margin = v;
      updateData.gross_margin_updated_at = new Date().toISOString();
    }
    if (body.cash_in_bank_usd !== undefined) {
      updateData.cash_in_bank_usd = toNum(body.cash_in_bank_usd);
      updateData.cash_updated_at = new Date().toISOString();
    }
    if (body.current_valuation_usd !== undefined) {
      updateData.current_valuation_usd = toNum(body.current_valuation_usd);
    }
    // Allow assigning / changing fund (persist fund_id)
    if (body.fund_id !== undefined) {
      const s = toString(body.fund_id);
      const uuidLike = s != null && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
      updateData.fund_id = uuidLike ? s : null;
    }

    // Update company
    const { data: updatedCompany, error: updateError } = await supabaseService
      .from('companies')
      .update(updateData)
      .eq('id', companyId)
      .select()
      .single();

    if (updateError) {
      console.error('Error updating company:', updateError);
      return NextResponse.json({ error: 'Failed to update company' }, { status: 500 });
    }

    return NextResponse.json(updatedCompany);
  } catch (error) {
    console.error('Error in PUT /api/portfolio/[id]/companies/[companyId]:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

/**
 * DELETE /api/portfolio/[id]/companies/[companyId]
 * Delete a company from a portfolio
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  try {
    const { id: fundId, companyId } = await params;

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Verify company belongs to this fund
    const { data: company, error: fetchError } = await supabaseService
      .from('companies')
      .select('id, fund_id, name')
      .eq('id', companyId)
      .single();

    if (fetchError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    if (company.fund_id !== fundId) {
      return NextResponse.json({ error: 'Company does not belong to this fund' }, { status: 403 });
    }

    // Delete company (this will cascade to related records if foreign keys are set up)
    const { error: deleteError } = await supabaseService
      .from('companies')
      .delete()
      .eq('id', companyId)
      .eq('fund_id', fundId);

    if (deleteError) {
      console.error('Error deleting company:', deleteError);
      return NextResponse.json(
        { 
          error: 'Failed to delete company',
          details: deleteError.message || String(deleteError),
          code: deleteError.code
        },
        { status: 500 }
      );
    }

    return NextResponse.json({ 
      success: true,
      message: `Company "${company.name}" deleted successfully`
    });
  } catch (error) {
    console.error('Error in DELETE /api/portfolio/[id]/companies/[companyId]:', error);
    return NextResponse.json(
      { error: 'Internal server error', message: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
