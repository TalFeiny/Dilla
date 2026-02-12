import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { spawn } from 'child_process';
import path from 'path';
import { resolveScriptPath } from '@/lib/scripts-path';

/**
 * POST: Run PWERM analysis.
 * - Accepts optional body.inputs / body.rowInputs (matrix row values). These override DB company.
 * - Merges company from DB with inputs, sends JSON to Python script via stdin.
 * - Script path: SCRIPTS_DIR env, or cwd/scripts, or cwd/../scripts.
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; companyId: string }> }
) {
  try {
    const { id: fundId, companyId } = await params;

    let company: Record<string, unknown> | null = null;
    if (supabaseService) {
      const { data, error } = await supabaseService
        .from('companies')
        .select('*')
        .eq('id', companyId)
        .eq('fund_id', fundId)
        .single();
      if (!error && data) company = data as Record<string, unknown>;
    }

    const body = await request.json().catch(() => ({}));
    const rowInputs = body.inputs ?? body.rowInputs ?? {};

    const company_data = buildCompanyDataForPwerm(company, rowInputs);
    const hasName = Boolean(company_data.name || company_data.company_name);
    const hasRevenue = [company_data.current_arr_usd, company_data.revenue, company_data.arr].some(
      (v) => v != null && Number(v) !== 0
    );
    if (!hasName && !hasRevenue) {
      return NextResponse.json(
        { error: 'Provide row inputs (name, ARR/revenue, sector) or a valid company in this fund' },
        { status: 400 }
      );
    }

    const { path: scriptPath, tried } = resolveScriptPath('pwerm_analysis.py');
    if (!scriptPath) {
      return NextResponse.json(
        {
          error: `PWERM script not found at any of: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.`,
        },
        { status: 500 }
      );
    }

    const inputPayload = JSON.stringify({
      company_data: company_data,
      assumptions: body.assumptions ?? {},
      fund_config: body.fund_config ?? {},
    });
    const result = await runPythonScriptStdin(scriptPath, inputPayload);

    if (!result.success) {
      return NextResponse.json(
        { error: result.error ?? 'PWERM analysis failed' },
        { status: 500 }
      );
    }

    const pwermResults = result.data;
    if (supabaseService && company) {
      await supabaseService
        .from('companies')
        .update({ updated_at: new Date().toISOString() })
        .eq('id', companyId)
        .eq('fund_id', fundId);
    }

    const pwerm = pwermResults as Record<string, unknown> | undefined;
    const fair_value =
      pwerm?.fair_value ??
      (pwerm?.results as Record<string, unknown> | undefined)?.pwerm_value ??
      (pwerm?.results as Record<string, unknown> | undefined)?.expected_value ??
      pwerm?.weighted_value ??
      pwerm?.expected_value;

    return NextResponse.json({
      success: true,
      pwermResults,
      fair_value: fair_value != null ? Number(fair_value) : undefined,
      message: 'PWERM analysis completed successfully',
    });
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies/[companyId]/pwerm:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    );
  }
}

function buildCompanyDataForPwerm(
  company: Record<string, unknown> | null,
  inputs: Record<string, unknown>
): Record<string, unknown> {
  const fromDb = company
    ? {
        name: company.name,
        company_name: company.name,
        current_arr_usd: company.current_arr_usd ?? company.current_arr,
        revenue: company.current_arr_usd ?? company.revenue,
        sector: company.sector ?? '',
        revenue_growth_annual_pct: company.revenue_growth_annual_pct ?? company.growth_rate != null ? Number(company.growth_rate) * 100 : undefined,
        current_valuation_usd: company.current_valuation_usd,
        total_invested_usd: company.total_invested_usd,
      }
    : {};
  const fromInputs: Record<string, unknown> = {
    name: inputs.name ?? inputs.company_name,
    company_name: inputs.company_name ?? inputs.name,
    current_arr_usd: inputs.current_arr_usd ?? inputs.revenue ?? inputs.arr,
    revenue: inputs.revenue ?? inputs.arr ?? inputs.current_arr_usd,
    arr: inputs.arr ?? inputs.revenue ?? inputs.current_arr_usd,
    sector: inputs.sector,
    revenue_growth_annual_pct: inputs.revenue_growth_annual_pct ?? (inputs.growth_rate != null ? Number(inputs.growth_rate) * 100 : undefined),
    current_valuation_usd: inputs.current_valuation_usd ?? inputs.last_round_valuation,
    total_invested_usd: inputs.total_invested_usd ?? inputs.total_raised,
  };
  const merged: Record<string, unknown> = { ...fromDb };
  for (const [k, v] of Object.entries(fromInputs)) {
    if (v !== undefined && v !== null && v !== '') merged[k] = v;
  }
  return merged;
}

function runPythonScriptStdin(
  scriptPath: string,
  stdinPayload: string
): Promise<{ success: boolean; data?: unknown; error?: string }> {
  const scriptDir = path.dirname(scriptPath);
  return new Promise((resolve) => {
    const pythonProcess = spawn('python', [scriptPath], {
      cwd: scriptDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONPATH: scriptDir },
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve({ success: true, data: result });
        } catch {
          resolve({ success: false, error: `Invalid JSON output: ${stdout.slice(0, 200)}` });
        }
      } else {
        resolve({ success: false, error: stderr || `Exit code ${code}` });
      }
    });

    pythonProcess.on('error', (err) => {
      resolve({ success: false, error: err.message });
    });

    pythonProcess.stdin.write(stdinPayload, (err) => {
      if (err) {
        resolve({ success: false, error: err.message });
        return;
      }
      pythonProcess.stdin.end();
    });
  });
}
