import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Extract core parameters
    const companyName = body.company_name || 'Test Company';
    const currentArr = body.current_arr_usd || 5000000;
    const growthRate = body.growth_rate || 0.30;
    const sector = body.sector || 'Technology';
    
    // Prepare input data for Python script
    const inputData = {
      company_data: {
        name: companyName,
        current_arr_usd: currentArr / 1000000, // Convert to millions
        revenue_growth_annual_pct: growthRate * 100, // Convert to percentage
        sector: sector
      },
      assumptions: {
        investment_amount: 1000000,
        ownership_percentage: 0.10,
        time_horizon_years: 5,
        market_conditions: 'neutral'
      }
    };
    
    console.log('Sending to Python:', JSON.stringify(inputData, null, 2));
    
    // Call Python script - use the one in root directory
    const pythonScriptPath = path.join(process.cwd(), '..', 'pwerm7_clean.py');
    
    return new Promise((resolve) => {
      const pythonProcess = spawn('python3', [pythonScriptPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env,
          OPENAI_API_KEY: process.env.OPENAI_API_KEY || ''
        }
      });
      
      let stdout = '';
      let stderr = '';
      let jsonOutput = '';
      let isCapturingJson = false;
      let braceCount = 0;

      // Handle stdout - look for JSON output
      pythonProcess.stdout.on('data', (data) => {
        const chunk = data.toString();
        stdout += chunk;
        
        // Simple JSON extraction - look for first { to last }
        for (let i = 0; i < chunk.length; i++) {
          const char = chunk[i];
          
          if (!isCapturingJson && char === '{') {
            isCapturingJson = true;
            braceCount = 1;
            jsonOutput = '{';
          } else if (isCapturingJson) {
            jsonOutput += char;
            if (char === '{') braceCount++;
            else if (char === '}') {
              braceCount--;
              if (braceCount === 0) {
                // Found complete JSON object
                isCapturingJson = false;
                break;
              }
            }
          }
        }
      });

      // Handle stderr for debugging
      pythonProcess.stderr.on('data', (data) => {
        stderr += data.toString();
        console.log('Python stderr:', data.toString());
      });

      // Send input data
      pythonProcess.stdin.write(JSON.stringify(inputData));
      pythonProcess.stdin.end();
      
      pythonProcess.on('close', (code) => {
        console.log('Python process exited with code:', code);
        console.log('Stderr length:', stderr.length);
        console.log('Stdout length:', stdout.length);
        console.log('JSON output length:', jsonOutput.length);
        
        if (code !== 0) {
          resolve(NextResponse.json({ 
            error: 'Python script failed',
            code: code,
            stderr: stderr.slice(0, 1000)
          }, { status: 500 }));
          return;
        }

        try {
          // Try to parse the extracted JSON
          if (jsonOutput) {
            const results = JSON.parse(jsonOutput);
            
            // Transform the results to match expected structure
            const response = {
              success: true,
              core_inputs: {
                company_name: companyName,
                current_arr_usd: currentArr,
                growth_rate: growthRate,
                sector: sector
              },
              market_research: {
                market_landscape: results.market_landscape || {},
                comparables: results.comparables || [],
                acquirers: results.potential_acquirers || [],
                exit_comparables: [],
                potential_acquirers: results.potential_acquirer_names || []
              },
              scenarios: (results.scenarios || []).map((s: any, idx: number) => ({
                id: idx + 1,
                name: s.scenario_name || `Scenario ${idx + 1}`,
                type: s.exit_type || 'unknown',
                probability: s.probability || 0,
                exit_value: s.exit_value_usd || 0,
                weighted_value: s.weighted_value || 0,
                total_funding_raised: s.total_funding || 0,
                years_to_exit: s.time_to_exit || 5,
                graduation_stage: s.graduation_stage || 'N/A',
                description: s.scenario_description || '',
                waterfall_analysis: {}
              })),
              summary: {
                expected_exit_value: results.expected_value_usd || 0,
                median_exit_value: results.median_exit_value || 0,
                total_scenarios: results.scenarios?.length || 0,
                success_probability: results.probability_of_success || 0,
                mega_exit_probability: results.probability_of_mega_exit || 0,
                p10_exit_value: results.p10_exit_value || 0,
                p25_exit_value: results.p25_exit_value || 0,
                p75_exit_value: results.p75_exit_value || 0,
                p90_exit_value: results.p90_exit_value || 0
              },
              analysis_timestamp: new Date().toISOString()
            };
            
            resolve(NextResponse.json(response));
          } else {
            // No JSON found, return error
            resolve(NextResponse.json({ 
              error: 'No JSON output from Python script',
              stdout: stdout.slice(0, 500),
              stderr: stderr.slice(0, 500)
            }, { status: 500 }));
          }
          
        } catch (parseError) {
          console.error('Parse error:', parseError);
          resolve(NextResponse.json({ 
            error: 'Failed to parse Python output',
            parseError: parseError instanceof Error ? parseError.message : 'Unknown',
            jsonOutput: jsonOutput.slice(0, 500)
          }, { status: 500 }));
        }
      });
    });

  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}