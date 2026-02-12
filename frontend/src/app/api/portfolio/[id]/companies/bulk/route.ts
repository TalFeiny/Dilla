import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

/**
 * Bulk update endpoint for portfolio companies
 * Accepts array of company updates and processes them in batch
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: fundId } = await params;
    const body = await request.json();
    const { updates, creates } = body;

    if (!supabaseService) {
      return NextResponse.json(
        { error: 'Supabase service not configured' },
        { status: 500 }
      );
    }

    if ((!Array.isArray(updates) || updates.length === 0) && (!Array.isArray(creates) || creates.length === 0)) {
      return NextResponse.json(
        { error: 'Updates or creates array is required and must not be empty' },
        { status: 400 }
      );
    }

    // Field mapping from matrix column IDs to database fields
    const fieldMap: Record<string, string> = {
      arr: 'current_arr_usd',
      burnRate: 'burn_rate_monthly_usd',
      runway: 'runway_months',
      grossMargin: 'gross_margin',
      cashInBank: 'cash_in_bank_usd',
      valuation: 'current_valuation_usd',
      ownership: 'ownership_percentage',
      invested: 'total_invested_usd',
      sector: 'sector',
      name: 'name',
    };

    const results: Array<{
      companyId: string;
      success: boolean;
      error?: string;
    }> = [];

    // Process each update
    for (const update of updates) {
      const { companyId, fields } = update;

      if (!companyId) {
        results.push({
          companyId: 'unknown',
          success: false,
          error: 'Missing companyId',
        });
        continue;
      }

      try {
        // Build update object
        const updateData: any = {};
        const now = new Date().toISOString();

        // Map fields and set appropriate timestamps
        for (const [columnId, value] of Object.entries(fields || {})) {
          const dbField = fieldMap[columnId];
          if (!dbField) {
            console.warn(`Unknown column: ${columnId}`);
            continue;
          }

          // Handle special cases
          if (columnId === 'grossMargin' && typeof value === 'number') {
            // Store as decimal (0-1), but accept percentage (0-100)
            updateData[dbField] = value > 1 ? value / 100 : value;
          } else if (columnId === 'ownership' && typeof value === 'number') {
            // Ownership is stored as percentage (0-100)
            updateData[dbField] = value;
          } else {
            updateData[dbField] = value;
          }

          // Set appropriate timestamp
          if (columnId === 'arr') {
            updateData.revenue_updated_at = now;
          } else if (columnId === 'burnRate') {
            updateData.burn_rate_updated_at = now;
          } else if (columnId === 'runway') {
            updateData.runway_updated_at = now;
          } else if (columnId === 'grossMargin') {
            updateData.gross_margin_updated_at = now;
          } else if (columnId === 'cashInBank') {
            updateData.cash_updated_at = now;
          }
        }

        if (Object.keys(updateData).length === 0) {
          results.push({
            companyId,
            success: false,
            error: 'No valid fields to update',
          });
          continue;
        }

        updateData.updated_at = now;

        // Verify company belongs to this fund
        const { data: company, error: checkError } = await supabaseService
          .from('companies')
          .select('id, fund_id')
          .eq('id', companyId)
          .single();

        if (checkError || !company) {
          results.push({
            companyId,
            success: false,
            error: 'Company not found',
          });
          continue;
        }

        if (company.fund_id !== fundId) {
          results.push({
            companyId,
            success: false,
            error: 'Company does not belong to this fund',
          });
          continue;
        }

        // Update company
        const { error: updateError } = await supabaseService
          .from('companies')
          .update(updateData)
          .eq('id', companyId)
          .eq('fund_id', fundId); // Extra safety check

        if (updateError) {
          console.error(`Error updating company ${companyId}:`, updateError);
          results.push({
            companyId,
            success: false,
            error: updateError.message,
          });
        } else {
          // Create audit trail entry (if matrix_edits table exists)
          try {
            await supabaseService.from('matrix_edits').insert({
              company_id: companyId,
              column_id: Object.keys(fields || {}).join(','),
              old_value: null, // We don't track old values in bulk updates
              new_value: JSON.stringify(updateData),
              edited_by: 'bulk_import',
              edited_at: now,
              data_source: 'bulk_import',
              fund_id: fundId,
            });
          } catch (auditError) {
            // Table might not exist yet, log but don't fail
            console.warn('Could not create audit trail entry:', auditError);
          }

          results.push({
            companyId,
            success: true,
          });
        }
      } catch (err) {
        console.error(`Error processing update for ${companyId}:`, err);
        results.push({
          companyId,
          success: false,
          error: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    }

    const successCount = results.filter((r) => r.success).length;
    const failureCount = results.length - successCount;

    return NextResponse.json({
      success: true,
      total: results.length,
      successful: successCount,
      failed: failureCount,
      results,
    });
  } catch (error) {
    console.error('Error in bulk update:', error);
    return NextResponse.json(
      { error: 'Internal server error', message: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
