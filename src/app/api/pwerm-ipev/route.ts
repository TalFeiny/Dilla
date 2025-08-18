import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

// Configure runtime to allow longer execution
export const maxDuration = 300; // 5 minutes

function loadEnvironmentVariables(): { tavilyKey: string; claudeKey: string } {
  const envPath = path.join(process.cwd(), '.env.local');
  let tavilyKey = '';
  let claudeKey = '';
  
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const envVars: Record<string, string> = {};
    
    envContent.split('\n').forEach(line => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) return;
      
      const equalIndex = trimmed.indexOf('=');
      if (equalIndex === -1) return;
      
      const key = trimmed.substring(0, equalIndex).trim();
      const value = trimmed.substring(equalIndex + 1).trim()
        .replace(/^["']|["']$/g, '');
      
      envVars[key] = value;
    });
    
    tavilyKey = envVars.TAVILY_API_KEY || '';
    claudeKey = envVars.CLAUDE_API_KEY || envVars.ANTHROPIC_API_KEY || '';
  }
  
  // Fallback to process.env
  if (!tavilyKey) tavilyKey = process.env.TAVILY_API_KEY || '';
  if (!claudeKey) claudeKey = process.env.CLAUDE_API_KEY || process.env.ANTHROPIC_API_KEY || '';
  
  return { tavilyKey, claudeKey };
}

export async function POST(request: NextRequest) {
  console.log('\n=== IPEV PWERM Analysis Request Started ===');
  console.log('Time:', new Date().toISOString());
  
  try {
    const { tavilyKey, claudeKey } = loadEnvironmentVariables();
    
    console.log('API Keys Status:', {
      TAVILY: tavilyKey ? `Found (${tavilyKey.substring(0, 8)}...)` : 'NOT FOUND',
      CLAUDE: claudeKey ? `Found (${claudeKey.substring(0, 8)}...)` : 'NOT FOUND'
    });
    
    const body = await request.json();
    
    // Validate inputs
    if (!body.company_name) {
      return NextResponse.json(
        { error: 'Company name is required' },
        { status: 400 }
      );
    }

    // Determine which PWERM implementation to use
    const useIPEV = body.use_ipev !== false; // Default to IPEV
    const scriptName = useIPEV ? 'pwerm_ipev.py' : 'pwerm_analysis.py';
    
    console.log(`Using ${useIPEV ? 'IPEV-compliant' : 'original'} PWERM implementation`);

    // Fetch comparable companies from database
    let existingComparables: any[] = [];
    let companyData = null;
    
    if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
      try {
        const { createClient } = require('@supabase/supabase-js');
        const supabase = createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          process.env.SUPABASE_SERVICE_ROLE_KEY!
        );
        
        // Fetch companies with valuation data
        const { data: companies, error } = await supabase
          .from('companies')
          .select('name, sector, current_arr_usd, current_valuation_usd, amount_raised')
          .not('current_arr_usd', 'is', null)
          .not('current_valuation_usd', 'is', null)
          .limit(50);
          
        if (companies && !error) {
          existingComparables = companies
            .filter((c: any) => c.current_arr_usd > 0)
            .map((c: any) => ({
              name: c.name,
              sector: c.sector,
              revenue: c.current_arr_usd,
              ev: c.current_valuation_usd,
              arr_multiple: c.current_valuation_usd / c.current_arr_usd
            }));
          
          console.log(`Found ${existingComparables.length} comparables from database`);
        }
        
        // Try to find the specific company
        const { data: company, error: companyError } = await supabase
          .from('companies')
          .select('*')
          .eq('name', body.company_name)
          .single();
          
        if (company && !companyError) {
          companyData = company;
          console.log(`Found company ${body.company_name} in database`);
        }
      } catch (dbError) {
        console.error('Database error:', dbError);
      }
    }
    
    // Prepare input data
    const inputData = {
      company_data: {
        name: body.company_name,
        current_arr_usd: (body.current_arr || companyData?.current_arr_usd || 5000000),
        revenue_growth_annual_pct: (body.growth_rate || 30),
        sector: body.sector || companyData?.sector || 'SaaS',
        last_round_valuation: body.last_valuation || companyData?.current_valuation_usd || 0,
        months_since_last_round: body.months_since_last_round || 6,
        ebitda_margin: body.ebitda_margin || 0.2
      },
      assumptions: {
        stage: body.stage || 'growth',
        investment_amount: body.investment_amount || 10000000,
        ownership_percent: body.ownership_percent || 0.15,
        liquidation_preference: body.liquidation_preference || 50000000,
        participation_cap: body.participation_cap || 2.0,
        conversion_price: body.conversion_price || 10.0,
        debt: body.debt || 0
      },
      fund_config: body.fund_config || {
        fund_size_m: 100,
        vintage_year: 2024,
        target_ownership_pct: 15
      },
      existing_comparables: existingComparables
    };
    
    console.log('Sending to Python script:', JSON.stringify(inputData, null, 2).substring(0, 500));

    // Execute Python script
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    const scriptPath = path.join(process.cwd(), 'scripts', scriptName);
    
    return new Promise((resolve) => {
      const pythonEnv = {
        ...process.env,
        TAVILY_API_KEY: tavilyKey,
        CLAUDE_API_KEY: claudeKey,
        ANTHROPIC_API_KEY: claudeKey,
        PYTHONUNBUFFERED: '1'
      };

      const pythonProcess = spawn(pythonPath, [scriptPath], {
        env: pythonEnv,
        cwd: process.cwd()
      });

      let outputData = '';
      let errorData = '';

      // Send input data
      pythonProcess.stdin.write(JSON.stringify(inputData));
      pythonProcess.stdin.end();

      pythonProcess.stdout.on('data', (data) => {
        const chunk = data.toString();
        outputData += chunk;
        console.log('Python stdout chunk:', chunk.substring(0, 100));
      });

      pythonProcess.stderr.on('data', (data) => {
        const chunk = data.toString();
        errorData += chunk;
        console.log('Python stderr:', chunk);
      });
      
      // Timeout handler
      const timeout = setTimeout(() => {
        pythonProcess.kill();
        resolve(NextResponse.json(
          { 
            error: 'Analysis timeout', 
            details: 'PWERM analysis took too long to complete'
          },
          { status: 504 }
        ));
      }, 280000);

      pythonProcess.on('close', (code) => {
        clearTimeout(timeout);
        
        console.log(`Python process exited with code ${code}`);
        
        if (code !== 0) {
          console.error('Python error:', errorData);
          resolve(NextResponse.json(
            { 
              error: 'Analysis failed', 
              details: errorData || 'Python script exited with error',
              code
            },
            { status: 500 }
          ));
          return;
        }

        try {
          const cleanedOutput = outputData.trim();
          
          if (!cleanedOutput) {
            resolve(NextResponse.json(
              { 
                error: 'Analysis produced no output', 
                details: 'The PWERM script completed but returned no data'
              },
              { status: 500 }
            ));
            return;
          }
          
          // Parse JSON output
          const result = JSON.parse(cleanedOutput);
          
          console.log('IPEV PWERM Results parsed successfully');
          console.log('Methodology:', result.methodology);
          console.log('Fair Value:', result.fair_value_analysis?.fair_value);
          console.log('Expected MOIC:', result.summary?.expected_moic);
          
          // Save to database if configured
          if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
            (async () => {
              try {
                const { createClient } = require('@supabase/supabase-js');
                const supabase = createClient(
                  process.env.NEXT_PUBLIC_SUPABASE_URL!,
                  process.env.SUPABASE_SERVICE_ROLE_KEY!
                );
                
                // Get or create company
                let companyId = null;
                const { data: existingCompany } = await supabase
                  .from('companies')
                  .select('id')
                  .eq('name', body.company_name)
                  .single();
                
                if (existingCompany) {
                  companyId = existingCompany.id;
                } else {
                  const { data: newCompany } = await supabase
                    .from('companies')
                    .insert({
                      name: body.company_name,
                      sector: body.sector || 'SaaS',
                      current_arr_usd: inputData.company_data.current_arr_usd,
                    })
                    .select('id')
                    .single();
                  
                  if (newCompany) {
                    companyId = newCompany.id;
                  }
                }
                
                // Save PWERM results with IPEV flag
                if (companyId) {
                  const { data: savedResult, error: saveError } = await supabase
                    .from('pwerm_results')
                    .insert({
                      company_id: companyId,
                      company_name: body.company_name,
                      current_arr_usd: inputData.company_data.current_arr_usd,
                      growth_rate: inputData.company_data.revenue_growth_annual_pct,
                      sector: inputData.company_data.sector,
                      expected_exit_value: result.summary?.fair_value || 0,
                      median_exit_value: result.fair_value_analysis?.value_distribution?.median || 0,
                      success_probability: result.summary?.success_probability || 0,
                      mega_exit_probability: result.fair_value_analysis?.probabilities?.mega_exit_probability || 0,
                      total_scenarios: result.fair_value_analysis?.scenario_count || 499,
                      methodology: result.methodology || 'IPEV PWERM',
                      market_research: result.enterprise_value_analysis || {},
                      scenarios: result.scenarios || [],
                      sensitivity_analysis: result.sensitivity_analysis || {},
                      full_results: result
                    })
                    .select()
                    .single();
                
                  if (savedResult && !saveError) {
                    console.log('IPEV PWERM results saved with ID:', savedResult.id);
                    result.analysis_id = savedResult.id;
                  } else if (saveError) {
                    console.error('Error saving results:', saveError);
                  }
                }
              } catch (dbError) {
                console.error('Database save error:', dbError);
              }
            })();
          }
          
          resolve(NextResponse.json(result));
        } catch (parseError) {
          console.error('Failed to parse output:', parseError);
          resolve(NextResponse.json(
            { 
              error: 'Failed to parse analysis results',
              details: outputData.substring(0, 1000)
            },
            { status: 500 }
          ));
        }
      });
    });

  } catch (error) {
    console.error('IPEV PWERM API error:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}