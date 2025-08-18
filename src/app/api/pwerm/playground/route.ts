import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { supabaseService } from '@/lib/supabase';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Extract core parameters
    const companyName = body.company_name;
    const currentArr = body.current_arr_usd || 5000000;
    const growthRate = body.growth_rate || 0.30;
    
    // Optional parameters with defaults
    const sector = body.sector || 'Technology';
    const timeHorizon = body.time_horizon_years || 5;
    const marketConditions = body.market_conditions || 'neutral';
    
    // Get company data from database if company_id is provided
    let companyData = {
      name: companyName,
      revenue: currentArr, // Keep as USD, don't convert to millions
      growth_rate: growthRate,
      sector: sector,
      funding: 10.0, // Default
      data_confidence: 'medium'
    };
    
    if (body.company_id) {
      const { data: company, error } = await supabaseService
        .from('companies')
        .select('*')
        .eq('id', body.company_id)
        .single();
      
      if (!error && company) {
        companyData = {
          name: company.name,
          revenue: (company.current_arr_usd || 5000000) / 1000000,
          growth_rate: company.revenue_growth_annual_pct || 0.30,
          sector: company.sector || 'Technology',
          funding: (company.total_funding_usd || 10000000) / 1000000,
          data_confidence: 'high'
        };
      }
    }
    
    // Call enhanced PWERM script directly
    const pythonScriptPath = path.join(process.cwd(), 'scripts', 'pwerm_analysis.py');
    
    return new Promise((resolve) => {
      let resolved = false;
      
      // Prepare input data for Python script - match the structure expected by pwerm_analysis.py
      const inputData = {
        company_data: {
          name: companyData.name,
          current_arr_usd: currentArr / 1000000, // Convert to millions for Python script
          revenue_growth_annual_pct: companyData.growth_rate * 100, // Convert to percentage
          sector: companyData.sector
        },
        assumptions: {
          investment_amount: body.investment_amount || 1000000,
          ownership_percentage: body.ownership_percentage || 0.10,
          time_to_exit_years: timeHorizon,
          time_horizon_years: timeHorizon,
          market_conditions: marketConditions
        }
      };
      
      // Ensure environment variables are passed to Python subprocess
      const pythonEnv = {
        PATH: process.env.PATH,
        TAVILY_API_KEY: process.env.TAVILY_API_KEY,
        CLAUDE_API_KEY: process.env.CLAUDE_API_KEY,
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY,
        OPENAI_API_KEY: process.env.OPENAI_API_KEY
      };
      
      const pythonProcess = spawn('python3', [pythonScriptPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: pythonEnv,
        maxBuffer: 50 * 1024 * 1024 // Increase buffer to 50MB for large responses
      });
      
      // Debug: Log environment variables
      console.log('Environment variables check:', {
        TAVILY_API_KEY: process.env.TAVILY_API_KEY ? `Set (${process.env.TAVILY_API_KEY.substring(0, 10)}...)` : 'Not set',
        CLAUDE_API_KEY: process.env.CLAUDE_API_KEY ? `Set (${process.env.CLAUDE_API_KEY.substring(0, 10)}...)` : 'Not set',
        OPENAI_API_KEY: process.env.OPENAI_API_KEY ? `Set (${process.env.OPENAI_API_KEY.substring(0, 10)}...)` : 'Not set'
      });

      let outputChunks: Buffer[] = [];
      let errorOutput = '';
      let progressMessages: string[] = [];

      pythonProcess.stdout.on('data', (data: Buffer) => {
        // Store as buffer to avoid encoding issues with large data
        outputChunks.push(data);
        
        // Extract progress messages for real-time updates
        const message = data.toString();
        if (message.includes('Starting') || message.includes('Processing') || message.includes('Completed')) {
          progressMessages.push(message.trim());
        }
      });

      pythonProcess.stderr.on('data', (data) => {
        const message = data.toString();
        errorOutput += message;
        // Only log first 200 chars of stderr to avoid flooding console
        if (message.length > 200) {
          console.log('Python stderr (truncated):', message.substring(0, 200) + '...');
        } else {
          console.log('Python stderr:', message);
        }
        
        // Also capture progress from stderr
        if (message.includes('Starting') || message.includes('Processing') || message.includes('Completed')) {
          progressMessages.push(message.trim());
        }
      });

      // Send input data to Python script ONCE
      console.log('Sending to Python script:', JSON.stringify(inputData));
      console.log('Company name being sent:', inputData.company_data.name);
      console.log('Sector being sent:', inputData.company_data.sector);
      pythonProcess.stdin.write(JSON.stringify(inputData));
      pythonProcess.stdin.end();
      
      // THEN set up event handlers
      pythonProcess.on('close', async (code) => {
        if (resolved) return;
        resolved = true;
        
        if (code !== 0) {
          console.error('Python script error:', errorOutput);
          resolve(NextResponse.json({ 
            error: 'PWERM analysis failed', 
            details: errorOutput,
            progress: progressMessages
          }, { status: 500 }));
          return;
        }

        try {
          // Combine all output chunks into a single string
          const output = Buffer.concat(outputChunks).toString('utf-8');
          
          console.log('Raw Python output length:', output.length);
          console.log('Raw Python output (first 500 chars):', output.substring(0, 500));
          console.log('Raw Python output (last 500 chars):', output.substring(Math.max(0, output.length - 500)));
          
          // Clean the output - remove any stderr messages or extra data
          const lines = output.split('\n');
          let jsonStart = -1;
          let jsonEnd = -1;
          
          // Find the first line that starts with {
          for (let i = 0; i < lines.length; i++) {
            if (lines[i].trim().startsWith('{')) {
              jsonStart = i;
              break;
            }
          }
          
          // Find the last line that ends with }
          for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].trim().endsWith('}')) {
              jsonEnd = i;
              break;
            }
          }
          
          if (jsonStart === -1 || jsonEnd === -1 || jsonStart > jsonEnd) {
            console.error('No valid JSON found in output');
            console.error('Output lines:', lines.length);
            console.error('First few lines:', lines.slice(0, 5));
            resolve(NextResponse.json({ 
              error: 'No valid JSON output found from Python script',
              output: output.substring(0, 1000),
              progress: progressMessages
            }, { status: 500 }));
            return;
          }
          
          // Extract just the JSON lines
          const jsonLines = lines.slice(jsonStart, jsonEnd + 1);
          const jsonStr = jsonLines.join('\n');
          
          console.log('Extracted JSON from lines', jsonStart, 'to', jsonEnd);
          console.log('JSON string length:', jsonStr.length);
          
          const analysisResults = JSON.parse(jsonStr);
          
          if (analysisResults.error) {
            resolve(NextResponse.json({ 
              error: analysisResults.error,
              details: analysisResults.traceback,
              progress: progressMessages
            }, { status: 500 }));
            return;
          }
          
          // Log what we're returning
          console.log('Analysis results keys:', Object.keys(analysisResults));
          console.log('Scenarios count:', analysisResults.scenarios?.length || 0);
          console.log('Summary available:', !!analysisResults.summary);
          console.log('Market research available:', !!analysisResults.market_research);
          
          // Process and structure the market research data properly
          const marketResearch = analysisResults.market_research || {};
          
          // Ensure acquirers have the expected structure
          if (marketResearch.acquirers) {
            marketResearch.acquirers = marketResearch.acquirers.map((acquirer: any) => ({
              name: acquirer.name || acquirer,
              type: acquirer.type || 'Strategic',
              market_cap: acquirer.market_cap || 0,
              acquisition_history: Array.isArray(acquirer.acquisition_history) ? acquirer.acquisition_history : []
            }));
          }
          
          // Return the enhanced PWERM analysis results
          resolve(NextResponse.json({
            success: true,
            core_inputs: analysisResults.core_inputs || {
              company_name: companyData.name,
              current_arr_usd: currentArr,
              growth_rate: growthRate,
              sector: sector
            },
            market_research: marketResearch,
            scenarios: analysisResults.scenarios || [],
            waterfall_analysis: analysisResults.waterfall_analysis || {},
            charts: analysisResults.charts || {},
            summary: analysisResults.summary || {},
            analysis_timestamp: analysisResults.analysis_timestamp || new Date().toISOString(),
            progress: progressMessages
          }));
          
        } catch (parseError) {
          console.error('Error parsing Python output:', parseError);
          console.error('Raw output length:', output.length);
          console.error('Raw output (first 1000 chars):', output.substring(0, 1000));
          
          // Check if it's the "Extra data" error
          const errorMessage = parseError instanceof Error ? parseError.message : 'Unknown parse error';
          if (errorMessage.includes('Extra data')) {
            console.error('JSON parsing failed due to extra data. Attempting to extract first JSON object...');
            
            // Try to extract just the first JSON object
            try {
              const firstBrace = output.indexOf('{');
              if (firstBrace !== -1) {
                let braceCount = 0;
                let inString = false;
                let escapeNext = false;
                let lastBrace = -1;
                
                for (let i = firstBrace; i < output.length; i++) {
                  const char = output[i];
                  
                  if (escapeNext) {
                    escapeNext = false;
                    continue;
                  }
                  
                  if (char === '\\') {
                    escapeNext = true;
                    continue;
                  }
                  
                  if (char === '"' && !escapeNext) {
                    inString = !inString;
                    continue;
                  }
                  
                  if (!inString) {
                    if (char === '{') braceCount++;
                    else if (char === '}') {
                      braceCount--;
                      if (braceCount === 0) {
                        lastBrace = i;
                        break;
                      }
                    }
                  }
                }
                
                if (lastBrace !== -1) {
                  const firstJsonObject = output.substring(firstBrace, lastBrace + 1);
                  console.log('Extracted first JSON object, length:', firstJsonObject.length);
                  const analysisResults = JSON.parse(firstJsonObject);
                  
                  if (analysisResults.error) {
                    resolve(NextResponse.json({ 
                      error: analysisResults.error,
                      details: analysisResults.traceback,
                      progress: progressMessages
                    }, { status: 500 }));
                    return;
                  }
                  
                  // Successfully parsed first JSON object
                  console.log('Analysis results keys:', Object.keys(analysisResults));
                  console.log('Scenarios count:', analysisResults.scenarios?.length || 0);
                  console.log('Summary available:', !!analysisResults.summary);
                  console.log('Market research available:', !!analysisResults.market_research);
                  
                  // Process and structure the market research data properly
                  const marketResearch = analysisResults.market_research || {};
                  
                  // Ensure acquirers have the expected structure
                  if (marketResearch.acquirers) {
                    marketResearch.acquirers = marketResearch.acquirers.map((acquirer: any) => ({
                      name: acquirer.name || acquirer,
                      type: acquirer.type || 'Strategic',
                      market_cap: acquirer.market_cap || 0,
                      acquisition_history: Array.isArray(acquirer.acquisition_history) ? acquirer.acquisition_history : []
                    }));
                  }
                  
                  // Return the enhanced PWERM analysis results
                  resolve(NextResponse.json({
                    success: true,
                    core_inputs: analysisResults.core_inputs || {
                      company_name: companyData.name,
                      current_arr_usd: currentArr,
                      growth_rate: growthRate,
                      sector: sector
                    },
                    market_research: marketResearch,
                    scenarios: analysisResults.scenarios || [],
                    waterfall_analysis: analysisResults.waterfall_analysis || {},
                    charts: analysisResults.charts || {},
                    summary: analysisResults.summary || {},
                    analysis_timestamp: analysisResults.analysis_timestamp || new Date().toISOString(),
                    progress: progressMessages
                  }));
                  return;
                }
              }
            } catch (secondError) {
              console.error('Failed to extract first JSON object:', secondError);
            }
          }
          
          resolve(NextResponse.json({ 
            error: 'Failed to parse analysis results',
            parseError: errorMessage,
            output: output.substring(0, 1000), // First 1000 chars for debugging
            progress: progressMessages
          }, { status: 500 }));
        }
      });
    });

  } catch (error) {
    console.error('PWERM API error:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
} 