import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { spawn } from 'child_process';
import path from 'path';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { scenarioId, portfolioId, selectedScenarios } = body;

    if (!portfolioId) {
      return NextResponse.json(
        { error: 'Portfolio ID is required' },
        { status: 400 }
      );
    }

    // Get portfolio companies
    const { data: portfolioCompanies, error: pcError } = await supabase
      .from('portfolio_companies')
      .select(`
        *,
        company:companies(*)
      `)
      .eq('fund_id', portfolioId);

    if (pcError) {
      console.error('Error fetching portfolio companies:', pcError);
      return NextResponse.json({ error: 'Failed to fetch portfolio companies' }, { status: 500 });
    }

    // Prepare scenario data
    const scenarioData = {
      scenario_id: scenarioId,
      portfolio_id: portfolioId,
      selected_scenarios: selectedScenarios || [],
      companies: portfolioCompanies?.map((pc: any) => ({
        name: pc.company?.name || 'Unknown Company',
        sector: pc.company?.sector || '',
        investment_amount: pc.total_invested_usd || 0,
        ownership_percentage: pc.ownership_percentage || 0,
        current_arr: pc.company?.current_arr_usd || 0,
        current_valuation: pc.current_valuation_usd || 0,
        investment_date: pc.investment_date,
        stage: pc.investment_stage || ''
      })) || []
    };

    // Run scenario analysis using the Python script
    const scriptsDir = path.join(process.cwd(), 'scripts');
    const scriptPath = path.join(scriptsDir, 'pwerm_analysis.py');

    const result = await runPythonScript(scriptPath, [
      '--scenario-analysis', JSON.stringify(scenarioData)
    ], scriptsDir);

    if (!result.success) {
      console.error('Scenario analysis failed:', result.error);
      return NextResponse.json(
        { error: `Scenario analysis failed: ${result.error}` },
        { status: 500 }
      );
    }

    return NextResponse.json({ 
      success: true, 
      scenarioResults: result.data,
      message: 'Scenario analysis completed successfully'
    });
  } catch (error) {
    console.error('Error in POST /api/scenarios/run:', error);
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