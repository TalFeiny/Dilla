import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { spawn } from 'child_process';
import path from 'path';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string; companyId: string } }
) {
  try {
    // Get company data
    const { data: company, error: companyError } = await supabase
      .from('companies')
      .select('*')
      .eq('id', params.companyId)
      .single();

    if (companyError || !company) {
      console.error('Error fetching company:', companyError);
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    // Get portfolio company data
    const { data: portfolioCompany, error: pcError } = await supabase
      .from('portfolio_companies')
      .select('*')
      .eq('id', params.companyId)
      .eq('fund_id', params.id)
      .single();

    if (pcError || !portfolioCompany) {
      console.error('Error fetching portfolio company:', pcError);
      return NextResponse.json({ error: 'Portfolio company not found' }, { status: 404 });
    }

    // Prepare data for PWERM analysis with waterfall
    const pwermData = {
      company_name: company.name,
      sector: company.sector || '',
      current_arr: company.current_arr_usd || 0,
      current_valuation: company.current_valuation_usd || 0,
      investment_amount: portfolioCompany.total_invested_usd || 0,
      ownership_percentage: portfolioCompany.ownership_percentage || 0,
      investment_date: portfolioCompany.investment_date,
      investment_stage: portfolioCompany.investment_stage || '',
      // Waterfall parameters for company-level analysis
      waterfall_assumptions: {
        preferred_return_rate: 0.08,  // 8% preferred return
        catch_up_percentage: 0.80,    // 80% catch-up
        carried_interest_rate: 0.20,  // 20% carried interest
        management_fee_rate: 0.02,    // 2% management fee
        hurdle_rate: 0.08,            // 8% hurdle rate
        gp_commitment_percentage: 0.01  // 1% GP commitment
      }
    };

    // Run PWERM analysis using the Python script
    const scriptsDir = path.join(process.cwd(), 'scripts');
    const scriptPath = path.join(scriptsDir, 'pwerm_analysis.py');

    const result = await runPythonScript(scriptPath, [
      '--company-analysis', JSON.stringify(pwermData)
    ], scriptsDir);

    if (!result.success) {
      console.error('PWERM analysis failed:', result.error);
      return NextResponse.json(
        { error: `PWERM analysis failed: ${result.error}` },
        { status: 500 }
      );
    }

    const pwermResults = result.data;

    // Update the portfolio company with PWERM results
    const { error: updateError } = await supabase
      .from('portfolio_companies')
      .update({
        pwerm_status: 'completed',
        pwerm_results: pwermResults,
        updated_at: new Date().toISOString()
      })
      .eq('id', params.companyId);

    if (updateError) {
      console.error('Error updating portfolio company with PWERM results:', updateError);
    }

    return NextResponse.json({ 
      success: true, 
      pwermResults,
      message: 'Company PWERM analysis with waterfall completed successfully'
    });
  } catch (error) {
    console.error('Error in POST /api/portfolio/[id]/companies/[companyId]/pwerm:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

function runPythonScript(
  scriptPath: string, 
  args: string[], 
  cwd: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  return new Promise((resolve) => {
    const pythonProcess = spawn('python', [scriptPath, ...args], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONPATH: cwd
      }
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
        } catch (parseError) {
          resolve({ 
            success: false, 
            error: `Failed to parse script output: ${parseError}. Output: ${stdout}` 
          });
        }
      } else {
        resolve({ 
          success: false, 
          error: `Script failed with code ${code}: ${stderr}` 
        });
      }
    });

    pythonProcess.on('error', (error) => {
      resolve({ 
        success: false, 
        error: `Failed to start script: ${error.message}` 
      });
    });
  });
} 