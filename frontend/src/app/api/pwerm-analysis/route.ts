import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';

// Configure runtime to allow longer execution
export const maxDuration = 300; // 5 minutes in seconds

function loadEnvironmentVariables(): { tavilyKey: string; claudeKey: string } {
  // Always read directly from .env.local file since process.env doesn't work reliably in API routes
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
        .replace(/^["']|["']$/g, ''); // Remove quotes
      
      envVars[key] = value;
    });
    
    tavilyKey = envVars.TAVILY_API_KEY || '';
    claudeKey = envVars.CLAUDE_API_KEY || envVars.ANTHROPIC_API_KEY || '';
  }
  
  // Fallback to process.env if file reading failed
  if (!tavilyKey) tavilyKey = process.env.TAVILY_API_KEY || '';
  if (!claudeKey) claudeKey = process.env.CLAUDE_API_KEY || process.env.ANTHROPIC_API_KEY || '';
  
  return { tavilyKey, claudeKey };
}

export async function POST(request: NextRequest) {
  console.log('\n=== PWERM Analysis Request Started ===');
  console.log('Time:', new Date().toISOString());
  
  try {
    // Load environment variables
    const { tavilyKey, claudeKey } = loadEnvironmentVariables();
    
    console.log('API Keys Status:', {
      TAVILY: tavilyKey ? `Found (${tavilyKey.substring(0, 8)}...)` : 'NOT FOUND',
      CLAUDE: claudeKey ? `Found (${claudeKey.substring(0, 8)}...)` : 'NOT FOUND'
    });
    
    const body = await request.json();
    
    
    // Validate inputs
    if (!body.company_name) {
      console.error('Company name missing in request:', body);
      return NextResponse.json(
        { error: 'Company name is required' },
        { status: 400 }
      );
    }

    // Fetch existing comparable companies and M&A data from the database
    let existingComparables: any[] = [];
    let maTransactions: any[] = [];
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
          .select('name, sector, current_arr_usd, current_valuation_usd, amount_raised, quarter_raised, latest_investment_date, total_invested_usd')
          .not('current_arr_usd', 'is', null)
          .not('current_valuation_usd', 'is', null);
          
        if (companies && !error) {
          // Calculate ARR multiples for existing companies
          existingComparables = companies
            .filter((c: any) => c.current_arr_usd > 0)
            .map((c: any) => ({
              name: c.name,
              sector: c.sector,
              arr: c.current_arr_usd / 1000000, // Convert to millions
              valuation: c.current_valuation_usd / 1000000, // Convert to millions
              arr_multiple: c.current_valuation_usd / c.current_arr_usd
            }));
          
          console.log(`Found ${existingComparables.length} companies with ARR multiples from database`);
        }
        
        // Fetch M&A transactions from processed documents
        const { data: processedDocs, error: docsError } = await supabase
          .from('processed_documents')
          .select('comparables_analysis')
          .not('comparables_analysis', 'is', null)
          .limit(100); // Get recent docs with comparables
          
        if (processedDocs && !docsError) {
          // Extract M&A transactions and valuation multiples
          processedDocs.forEach((doc: any) => {
            const comparables = doc.comparables_analysis || {};
            
            // Extract M&A transactions
            if (comparables.ma_transactions && Array.isArray(comparables.ma_transactions)) {
              maTransactions.push(...comparables.ma_transactions.map((deal: any) => ({
                company_name: deal.company_name || deal.target_company,
                acquirer: deal.acquirer,
                deal_value: deal.deal_value,
                deal_date: deal.deal_date,
                sector: body.sector // Use the target company's sector
              })));
            }
            
            // Extract valuation multiples if present
            if (comparables.valuation_multiples) {
              const { revenue_multiple, arr_multiple } = comparables.valuation_multiples;
              if (revenue_multiple || arr_multiple) {
                existingComparables.push({
                  name: "Market Average from Documents",
                  sector: body.sector,
                  arr: 0,
                  valuation: 0,
                  arr_multiple: arr_multiple || revenue_multiple || 0
                });
              }
            }
          });
          
          console.log(`Found ${maTransactions.length} M&A transactions from processed documents`);
        }
      } catch (dbError) {
        console.error('Error fetching database comparables:', dbError);
      }
    }

    // Try to find the company in our database first
    let companyData = null;
    if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
      try {
        const { createClient } = require('@supabase/supabase-js');
        const supabase = createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          process.env.SUPABASE_SERVICE_ROLE_KEY!
        );
        
        const { data: company, error } = await supabase
          .from('companies')
          .select('*')
          .eq('name', body.company_name)
          .single();
          
        if (company && !error) {
          companyData = company;
          console.log(`Found company ${body.company_name} in database with funding data`);
        }
      } catch (e) {
        console.log('Company not found in database');
      }
    }
    
    // Prepare input data for Python script - matches expected structure
    const inputData = {
      company_data: {
        name: body.company_name,
        current_arr_usd: (body.current_arr || 5.0) * 1000000, // Convert millions to dollars for Python script
        revenue_growth_annual_pct: (body.growth_rate || 0.30) * 100, // Convert decimal to percentage
        sector: body.sector || 'SaaS',
        // Include funding data if found
        total_invested_usd: companyData?.total_invested_usd || companyData?.amount_raised?.total || null,
        latest_investment_date: companyData?.latest_investment_date || null,
        quarter_raised: companyData?.quarter_raised || null,
        amount_raised: companyData?.amount_raised || null
      },
      assumptions: body.assumptions || {},
      fund_config: {
        fund_size_m: body.fund_config?.fund_size_m || 100, // Default $100M fund
        first_close_date: body.fund_config?.first_close_date || '2024-01-01',
        final_close_date: body.fund_config?.final_close_date || '2024-12-31',
        vintage_year: body.fund_config?.vintage_year || 2024,
        investment_period_years: body.fund_config?.investment_period_years || 3,
        fund_life_years: body.fund_config?.fund_life_years || 10,
        management_fee_pct: body.fund_config?.management_fee_pct || 2.0,
        carried_interest_pct: body.fund_config?.carried_interest_pct || 20,
        preferred_return_pct: body.fund_config?.preferred_return_pct || 8,
        
        // Investment strategy
        target_investments: body.fund_config?.target_investments || 25,
        avg_check_size_m: body.fund_config?.avg_check_size_m || 3,
        min_check_size_m: body.fund_config?.min_check_size_m || 1,
        max_check_size_m: body.fund_config?.max_check_size_m || 10,
        follow_on_reserve_pct: body.fund_config?.follow_on_reserve_pct || 50,
        
        // Target stages
        investment_stages: body.fund_config?.investment_stages || ['seed', 'series_a'],
        target_ownership_pct: body.fund_config?.target_ownership_pct || 10,
        
        // Geographic focus
        geographic_focus: body.fund_config?.geographic_focus || 'North America'
      },
      existing_comparables: existingComparables,
      ma_transactions: maTransactions
    };
    
    console.log('Sending to Python script:', JSON.stringify(inputData, null, 2));

    // Execute Python script
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    const scriptPath = path.join(process.cwd(), 'scripts', 'pwerm_analysis.py');
    
    return new Promise((resolve) => {
      // Prepare environment for Python subprocess
      const pythonEnv = {
        ...process.env,
        TAVILY_API_KEY: tavilyKey,
        CLAUDE_API_KEY: claudeKey,
        ANTHROPIC_API_KEY: claudeKey, // Compatibility alias
        PYTHONUNBUFFERED: '1'
      };
      
      console.log('Passing to Python:', {
        TAVILY: pythonEnv.TAVILY_API_KEY ? 'SET' : 'NOT SET',
        CLAUDE: pythonEnv.CLAUDE_API_KEY ? 'SET' : 'NOT SET'
      });

      const pythonProcess = spawn(pythonPath, [scriptPath], {
        env: pythonEnv,
        cwd: process.cwd()
      });

      let outputData = '';
      let errorData = '';

      // Send input data to Python script
      pythonProcess.stdin.write(JSON.stringify(inputData));
      pythonProcess.stdin.end();

      // Collect output
      pythonProcess.stdout.on('data', (data) => {
        const chunk = data.toString();
        outputData += chunk;
        console.log('Python stdout chunk length:', chunk.length);
        console.log('Python stdout preview:', chunk.substring(0, 200));
      });

      pythonProcess.stderr.on('data', (data) => {
        const chunk = data.toString();
        errorData += chunk;
        console.log('Python stderr:', chunk);
      });
      
      // Add timeout handler
      const timeout = setTimeout(() => {
        pythonProcess.kill();
        resolve(NextResponse.json(
          { 
            error: 'Analysis timeout', 
            details: 'PWERM analysis took too long to complete',
            partialOutput: outputData.substring(0, 1000)
          },
          { status: 504 }
        ));
      }, 280000); // 4 minutes 40 seconds (slightly less than maxDuration)

      pythonProcess.on('close', (code) => {
        clearTimeout(timeout); // Clear the timeout
        
        console.log(`Python process exited with code ${code}`);
        console.log(`Total output length: ${outputData.length} characters`);
        console.log(`Total error length: ${errorData.length} characters`);
        
        if (code !== 0) {
          console.error('Python error:', errorData);
          resolve(NextResponse.json(
            { 
              error: 'Analysis failed', 
              details: errorData || 'Python script exited with error',
              code,
              partialOutput: outputData.substring(0, 500)
            },
            { status: 500 }
          ));
          return;
        }

        try {
          // Parse JSON output
          const cleanedOutput = outputData.trim();
          
          // If output is empty, return a detailed error
          if (!cleanedOutput) {
            console.error('Empty output from Python script');
            resolve(NextResponse.json(
              { 
                error: 'Analysis produced no output', 
                details: 'The PWERM script completed but returned no data',
                stderr: errorData.substring(0, 1000)
              },
              { status: 500 }
            ));
            return;
          }
          
          // Try to find the last complete JSON object in the output
          // This handles cases where there might be multiple JSON objects or debug output
          let result: any;
          
          // Simple approach: just try to parse the whole output first
          try {
            result = JSON.parse(cleanedOutput);
            console.log('Successfully parsed entire output as JSON');
          } catch (e) {
            // If that fails, try to extract the last complete JSON object
            const lastBraceIndex = cleanedOutput.lastIndexOf('}');
            if (lastBraceIndex !== -1) {
              // Find the matching opening brace
              let depth = 1;
              let startIndex = lastBraceIndex - 1;
              while (startIndex >= 0 && depth > 0) {
                if (cleanedOutput[startIndex] === '}') depth++;
                if (cleanedOutput[startIndex] === '{') depth--;
                startIndex--;
              }
              
              if (depth === 0) {
                try {
                  const jsonString = cleanedOutput.substring(startIndex + 1, lastBraceIndex + 1);
                  result = JSON.parse(jsonString);
                  console.log('Successfully parsed JSON from extracted substring');
                } catch (e2) {
                  console.error('Failed to parse extracted JSON:', e2);
                }
              }
            }
          }
          
          // Fallback: Try to parse the entire output
          if (!result) {
            try {
              result = JSON.parse(cleanedOutput);
              console.log('Successfully parsed entire output as JSON');
            } catch (e) {
              console.error('Failed to parse entire output as JSON:', e);
              console.error('Output length:', cleanedOutput.length);
              console.error('First 500 chars:', cleanedOutput.substring(0, 500));
              console.error('Last 500 chars:', cleanedOutput.substring(cleanedOutput.length - 500));
              // Last resort: try to extract with regex
              const jsonMatch = cleanedOutput.match(/\{(?:[^{}]|(?:\{[^{}]*\}))*\}/g);
              if (jsonMatch && jsonMatch.length > 0) {
                // Try the last match (likely the final result)
                try {
                  result = JSON.parse(jsonMatch[jsonMatch.length - 1]);
                } catch (e2) {
                  console.error('Failed to parse regex-extracted JSON');
                  resolve(NextResponse.json(
                    { 
                      error: 'Failed to parse analysis results', 
                      details: 'The output was not valid JSON',
                      sample: cleanedOutput.substring(0, 500)
                    },
                    { status: 500 }
                  ));
                  return;
                }
              }
            }
          }
          
          if (!result) {
            resolve(NextResponse.json(
              { 
                error: 'Failed to parse analysis results', 
                details: 'Could not extract valid JSON from output',
                outputLength: cleanedOutput.length
              },
              { status: 500 }
            ));
            return;
          }
          
          // Log successful parse
          console.log('PWERM Results parsed successfully');
          console.log('Summary:', result.summary);
          console.log('Scenarios count:', result.scenarios?.length);
          console.log('Market research keys:', Object.keys(result.market_research || {}));
          
          // Optimize response size
          if (result.scenarios && result.scenarios.length > 20) {
            result.scenarios = result.scenarios
              .sort((a: any, b: any) => (b.exit_value || 0) - (a.exit_value || 0))
              .slice(0, 20);
          }
          
          if (result.exit_distribution_chart?.length > 100000) {
            delete result.exit_distribution_chart;
          }
          
          // Keep important data but limit size
          if (result.market_research) {
            // Don't delete comparables - they're important!
            if (result.market_research.exit_comparables?.length > 10) {
              result.market_research.exit_comparables = result.market_research.exit_comparables.slice(0, 10);
            }
            // Remove only truly redundant data
            delete result.market_research.raw_company_results;
            delete result.market_research.raw_exit_results;
          }
          
          // Save to database if we have Supabase configured
          if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY) {
            (async () => {
              try {
                const { createClient } = require('@supabase/supabase-js');
                const supabase = createClient(
                  process.env.NEXT_PUBLIC_SUPABASE_URL!,
                  process.env.SUPABASE_SERVICE_ROLE_KEY!
                );
                
                // First, check if company exists or create it
                let companyId = null;
                const { data: existingCompany } = await supabase
                  .from('companies')
                  .select('id')
                  .eq('name', body.company_name)
                  .single();
                
                if (existingCompany) {
                  companyId = existingCompany.id;
                } else {
                  // Create company if it doesn't exist
                  const { data: newCompany } = await supabase
                    .from('companies')
                    .insert({
                      name: body.company_name,
                      sector: body.sector || 'SaaS',
                      current_arr_usd: (body.current_arr || 0) * 1000000,
                    })
                    .select('id')
                    .single();
                  
                  if (newCompany) {
                    companyId = newCompany.id;
                  }
                }
                
                // Save PWERM results
                if (companyId) {
                  const { data: savedResult, error: saveError } = await supabase
                    .from('pwerm_results')
                    .insert({
                      company_id: companyId,
                      company_name: body.company_name,
                      current_arr_usd: (body.current_arr || 0) * 1000000,
                      growth_rate: (body.growth_rate || 0) * 100,
                      sector: body.sector || 'SaaS',
                      expected_exit_value: result.summary?.expected_exit_value || 0,
                      median_exit_value: result.summary?.median_exit_value || 0,
                      success_probability: result.summary?.success_probability || 0,
                      mega_exit_probability: result.summary?.mega_exit_probability || 0,
                      total_scenarios: result.summary?.total_scenarios || 499,
                      market_research: result.market_research || {},
                      scenarios: result.scenarios || [],
                      charts: result.exit_distribution_chart ? { exit_distribution: result.exit_distribution_chart } : {},
                      expected_round_returns: result.expected_round_returns || {},
                      full_results: result
                    })
                    .select()
                    .single();
                
                  if (savedResult && !saveError) {
                    console.log('PWERM results saved to database with ID:', savedResult.id);
                    result.analysis_id = savedResult.id;
                  } else if (saveError) {
                    console.error('Error saving PWERM results:', saveError);
                  }
                }
              } catch (dbError) {
                console.error('Database save error:', dbError);
                // Don't fail the request if save fails
              }
            })(); // End of async IIFE
          }
          
          resolve(NextResponse.json(result));
        } catch (parseError) {
          console.error('Failed to parse Python output:', parseError);
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
    console.error('PWERM Analysis API error:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
} 