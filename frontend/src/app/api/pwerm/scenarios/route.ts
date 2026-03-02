import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import { spawn } from 'child_process';
import path from 'path';
import { resolveScriptPath } from '@/lib/scripts-path';
import { supabaseService } from '@/lib/supabase';

const execAsync = promisify(exec);

export async function GET() {
  try {
    const { path: pythonScriptPath, tried } = resolveScriptPath('pwerm_analysis.py');
    if (!pythonScriptPath) {
      const scenarios = generateDefaultScenarios();
      return NextResponse.json({ scenarios, warning: `Script not found at: ${tried.join(', ')}. Using defaults.` });
    }
    
    const { stdout, stderr } = await execAsync(
      `python3 "${pythonScriptPath}" --list-scenarios`,
      { 
        timeout: 60000, // 1 minute timeout
        env: {
          ...process.env
        }
      }
    );

    if (stderr) {
      console.error('Python script stderr:', stderr);
    }

    // Parse the scenarios from your PWERM script
    let scenarios;
    try {
      scenarios = JSON.parse(stdout);
    } catch (parseError) {
      console.error('Failed to parse scenarios from PWERM script:', parseError);
      
      // If the script doesn't have a --list-scenarios flag, we'll return the known structure
      // based on the pwerm_analysis.py file
      scenarios = generateDefaultScenarios();
    }

    return NextResponse.json({ scenarios });
  } catch (error) {
    console.error('Error in GET /api/pwerm/scenarios:', error);
    
    // Fallback to default scenarios if script execution fails
    const scenarios = generateDefaultScenarios();
    return NextResponse.json({ scenarios });
  }
}

function generateDefaultScenarios() {
  // Generate the 499 scenarios based on the pwerm_analysis.py structure
  const scenarios = [];
  
  // Key scenario definitions from the script
  const keyScenarios = [
    { id: 1, name: "Liquidation — written to 0", valuation_range: "0", outcome_type: "liquidation" },
    { id: 2, name: "Pre-seed only - Distressed Acquisition for parts", valuation_range: "1-5M", outcome_type: "distressed" },
    { id: 3, name: "Pre-seed and seed, Distressed acquisition for parts", valuation_range: "1-5M", outcome_type: "distressed" },
    { id: 4, name: "Pre-seed only - Acquihire small", valuation_range: "5-10M", outcome_type: "acquihire" },
    { id: 5, name: "Pre-seed and seed - Acquihire small", valuation_range: "5-10M", outcome_type: "acquihire" },
    { id: 15, name: "Pre-seed only - small strategic", valuation_range: "20-25M", outcome_type: "strategic" },
    { id: 16, name: "Pre-seed and seed - small strategic", valuation_range: "20-25M", outcome_type: "strategic" },
    { id: 50, name: "Pre-seed only - Land Grab", valuation_range: "45-50M", outcome_type: "land_grab" },
    { id: 57, name: "Pre-seed only - Small Land & Expand", valuation_range: "50-60M", outcome_type: "land_expand" },
    { id: 70, name: "Pre-seed only - Medium Land & Expand", valuation_range: "60-70M", outcome_type: "land_expand" },
    { id: 90, name: "Pre-seed only - Large Land & Expand", valuation_range: "70-80M", outcome_type: "land_expand" },
    { id: 100, name: "Pre-seed only - XLarge Land & Expand", valuation_range: "80-90M", outcome_type: "land_expand" },
    { id: 110, name: "Pre-seed only - XXLarge Land & Expand", valuation_range: "90-100M", outcome_type: "land_expand" },
    { id: 120, name: "Pre-seed and seed - Xsmall Enterprise Complimentary", valuation_range: "100-125M", outcome_type: "enterprise" },
    { id: 140, name: "Pre-seed and seed - Small Enterprise Complimentary", valuation_range: "125-150M", outcome_type: "enterprise" },
    { id: 160, name: "Pre-seed and seed - Medium Enterprise Complimentary", valuation_range: "150-175M", outcome_type: "enterprise" },
    { id: 180, name: "Pre-seed and seed - Large Enterprise Complimentary", valuation_range: "175-200M", outcome_type: "enterprise" },
    { id: 200, name: "Pre-seed and seed - XLarge Enterprise Complimentary", valuation_range: "200-225M", outcome_type: "enterprise" },
    { id: 220, name: "Pre-seed and seed - XXLarge Enterprise Complimentary", valuation_range: "225-250M", outcome_type: "enterprise" },
    { id: 240, name: "Pre-seed, seed and seed extension - Small competitive threat", valuation_range: "250-300M", outcome_type: "competitive" },
    { id: 260, name: "Pre-seed, seed and seed extension - Medium Competitive Threat", valuation_range: "300-350M", outcome_type: "competitive" },
    { id: 280, name: "Pre-seed, seed and seed extension - Large competitive threat or roll up", valuation_range: "350-400M", outcome_type: "competitive" },
    { id: 300, name: "Pre-seed, seed and seed extension - Insurgent threat or Roll up", valuation_range: "400-450M", outcome_type: "insurgent" },
    { id: 320, name: "Pre-seed, seed and seed extension - Microcap regional IPO, rollup or major threat", valuation_range: "450-500M", outcome_type: "microcap_ipo" },
    { id: 340, name: "Pre-seed, seed and seed extension - Small Cap IPO, rollup or crown jewel asset", valuation_range: "500-600M", outcome_type: "small_cap_ipo" },
    { id: 360, name: "Pre-seed, seed and seed extension - Downround IPO, rollup or crown jewel asset", valuation_range: "600-700M", outcome_type: "downround_ipo" },
    { id: 380, name: "Pre-seed, seed, A, B - Post-lockup poor performing IPO, rollup or crown jewel asset", valuation_range: "700-800M", outcome_type: "poor_ipo" },
    { id: 400, name: "Pre-seed, seed, A, B - lower midcap IPO, mini cap buyout, crown jewel asset", valuation_range: "800-900M", outcome_type: "midcap_ipo" },
    { id: 420, name: "Pre-seed, seed, A, B - Upper midcap IPO, small cap buyout, crown jewel asset", valuation_range: "900M-1B", outcome_type: "upper_midcap_ipo" },
    { id: 440, name: "Pre-seed, seed, A, B - Upper midcap IPO, small cap buyout, Buy over build", valuation_range: "1B-1.1B", outcome_type: "buy_over_build" },
    { id: 460, name: "Pre-seed, seed, A, B - Upper middle midcap IPO, small cap buyout, Buy over build", valuation_range: "1.1B-1.2B", outcome_type: "buy_over_build" },
    { id: 480, name: "Pre-seed, seed, A, B - Small largecap IPO, lower midcap buyout, Buy over build", valuation_range: "1.2-1.3B", outcome_type: "largecap_ipo" },
    { id: 450, name: "Pre-seed, seed, A, B - Market price range largecap IPO, largecap buyout, Megacap acquisition", valuation_range: "2B-2.1B", outcome_type: "megacap" },
    { id: 460, name: "Pre-seed, seed, A, B - just above market price range IPO, largecap buyout, megacap acquisition", valuation_range: "2.1-2.2B", outcome_type: "megacap" },
    { id: 470, name: "Pre-seed, seed, A, B - Solid performing IPO, largecap buyout, megacap sale", valuation_range: "2.2-2.3B", outcome_type: "megacap" },
    { id: 480, name: "Pre-seed, seed, A, B - Good performing IPO, largecap buyout, Big tech acquisition", valuation_range: "2.3-2.4B", outcome_type: "big_tech" },
    { id: 490, name: "Pre-seed, seed, A, B - Great performing IPO, largecap buyout, Big tech acquisition", valuation_range: "2.4-2.5B", outcome_type: "big_tech" },
    { id: 475, name: "Pre-seed, seed, A, B - Major Exchange Top IPO, largecap buyout, Big tech Acquisition", valuation_range: "2.5-2.6B", outcome_type: "major_exchange" },
    { id: 485, name: "Pre-seed, seed, A, B - Surging major exchange IPO, largecap buout, Mag 7 IPO", valuation_range: "2.6-2.7B", outcome_type: "mag7" },
    { id: 490, name: "Pre-seed, seed, A, B - Top Price range mega IPO, megacap buyout, Mag 7 acquisition", valuation_range: "2.7-2.8B", outcome_type: "mag7" },
    { id: 495, name: "Pre-seed, seed, A, B - Best performing mega IPO, megacap buyout, Mag 7 Acquisition", valuation_range: "3B-4B", outcome_type: "mag7_best" },
    { id: 499, name: "Pre-seed, seed, A, B, C, D, E, F - NYSE Best possible IPO, megacap buyout, Google / Apple / Meta Acquisition", valuation_range: "10B+", outcome_type: "faang" }
  ];

  // Create a map for quick lookup
  const keyScenarioMap = new Map(keyScenarios.map(s => [s.id, s]));

  // Generate all 499 scenarios
  for (let i = 1; i <= 499; i++) {
    if (keyScenarioMap.has(i)) {
      scenarios.push(keyScenarioMap.get(i)!);
    } else {
      // Generate synthetic scenarios for missing IDs
      let scenario = {
        id: i,
        name: `Scenario ${i} (Synthetic)`,
        valuation_range: "Variable",
        outcome_type: "additional"
      };

      // Apply structured synthetic valuation ranges based on ID proximity
      if (i < 57) {
        const baseVal = (i - 5) * 0.5 + 10;
        scenario.valuation_range = `${baseVal.toFixed(1)}M-${(baseVal + 5).toFixed(1)}M`;
        scenario.outcome_type = "strategic_mid";
      } else if (i < 110) {
        const baseVal = 50 + (i - 57) * 0.5;
        scenario.valuation_range = `${baseVal.toFixed(1)}M-${(baseVal + 5).toFixed(1)}M`;
        scenario.outcome_type = "land_expand";
      } else if (i < 200) {
        const baseVal = 100 + (i - 110) * 2;
        scenario.valuation_range = `${baseVal}M-${baseVal + 25}M`;
        scenario.outcome_type = "enterprise";
      } else if (i < 400) {
        const baseVal = 250 + (i - 200) * 5;
        scenario.valuation_range = `${baseVal}M-${baseVal + 50}M`;
        scenario.outcome_type = "competitive";
      } else if (i < 450) {
        const baseVal = 800 + (i - 400) * 100;
        scenario.valuation_range = `${baseVal}M-${baseVal + 100}M`;
        scenario.outcome_type = "ipo";
      } else {
        const baseVal = 2 + (i - 450) * 0.1;
        scenario.valuation_range = `${baseVal.toFixed(1)}B-${(baseVal + 0.1).toFixed(1)}B`;
        scenario.outcome_type = "megacap";
      }

      scenarios.push(scenario);
    }
  }

  return scenarios;
}

// POST endpoint to run PWERM analysis for all companies in a portfolio
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { portfolioId } = body;

    if (!portfolioId) {
      return NextResponse.json({ error: 'Portfolio ID is required' }, { status: 400 });
    }

    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Fetch portfolio companies
    const { data: companies, error: companiesError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('fund_id', portfolioId)
      .not('fund_id', 'is', null);

    if (companiesError) {
      console.error('Error fetching portfolio companies:', companiesError);
      return NextResponse.json({ error: 'Failed to fetch portfolio companies' }, { status: 500 });
    }

    if (!companies || companies.length === 0) {
      return NextResponse.json({ error: 'No companies found in portfolio' }, { status: 404 });
    }

    const { path: scriptPath, tried } = resolveScriptPath('pwerm_analysis.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `PWERM script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const scriptsDir = path.dirname(scriptPath);
    const results = [];
    const errors = [];

    // Run PWERM analysis for each company
    for (const company of companies) {
      try {
        // Prepare data for PWERM analysis
        const pwermInput = {
          company_data: {
            name: company.name,
            company_name: company.name,
            current_arr_usd: (company.current_arr_usd || 1000000) / 1000000, // Convert to millions
            growth_rate: (company.revenue_growth_annual_pct || 70) / 100, // Convert percentage to decimal
            sector: company.sector || 'Technology',
            total_invested_usd: company.total_invested_usd || 0,
            ownership_percentage: company.ownership_percentage || 0,
            burn_rate_monthly_usd: company.burn_rate_monthly_usd,
            runway_months: company.runway_months,
          },
          assumptions: {},
          fund_config: {}
        };

        const result = await runPythonScript(scriptPath, [], scriptsDir, JSON.stringify(pwermInput));

        if (result.success) {
          // Update company with PWERM results
          await supabaseService
            .from('companies')
            .update({
              has_pwerm_model: true,
              latest_pwerm_run_at: new Date().toISOString(),
              pwerm_scenarios_count: result.data?.summary?.total_scenarios || 499,
              thesis_match_score: result.data?.summary?.success_probability 
                ? result.data.summary.success_probability * 100 
                : 50,
              pwerm_results: result.data
            })
            .eq('id', company.id);

          results.push({
            company_id: company.id,
            company_name: company.name,
            success: true,
            results: result.data
          });
        } else {
          errors.push({
            company_id: company.id,
            company_name: company.name,
            error: result.error
          });
        }
      } catch (error) {
        errors.push({
          company_id: company.id,
          company_name: company.name,
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }

    return NextResponse.json({
      success: true,
      message: `PWERM analysis completed for ${results.length} companies`,
      results,
      errors: errors.length > 0 ? errors : undefined
    });
  } catch (error) {
    console.error('Error in POST /api/pwerm/scenarios:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}

function runPythonScript(
  scriptPath: string, 
  args: string[], 
  cwd: string,
  stdinData?: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  return new Promise((resolve) => {
    const env = {
      ...process.env,
      PYTHONPATH: cwd,
      TAVILY_API_KEY: process.env.TAVILY_API_KEY,
      ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY,
      PWD: process.cwd()
    };
    
    const pythonProcess = spawn('python3', [scriptPath, ...args], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: env
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    if (stdinData) {
      pythonProcess.stdin.write(stdinData);
      pythonProcess.stdin.end();
    }

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