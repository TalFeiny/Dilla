import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { resolveScriptPath } from '@/lib/scripts-path';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: companyId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Get company data from Supabase
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    if (companyError) {
      console.error('Error fetching company:', companyError);
      return NextResponse.json({ error: 'Failed to fetch company' }, { status: 500 });
    }

    if (!company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }

    // Get request body for assumptions and optional document analysis (SERVICE_ALIGNED_FIELDS)
    const body = await request.json();
    const assumptions = body.assumptions || {};
    const documentAnalysis = body.document_analysis || body.extracted_data;

    // Merge document extraction into company when provided (aligns extraction → valuation)
    let mergedCompany = { ...company };
    if (documentAnalysis) {
      const fi = documentAnalysis.financial_metrics ?? documentAnalysis;
      const ci = documentAnalysis.company_info ?? documentAnalysis;
      mergedCompany = {
        ...mergedCompany,
        current_arr_usd: mergedCompany.current_arr_usd ?? fi?.arr ?? fi?.revenue,
        sector: mergedCompany.sector ?? ci?.sector ?? documentAnalysis.sector,
        business_model: mergedCompany.business_model ?? ci?.business_model ?? documentAnalysis.business_model,
        category: mergedCompany.category ?? ci?.category ?? documentAnalysis.category,
        revenue_growth_annual_pct: mergedCompany.revenue_growth_annual_pct ?? (fi?.growth_rate != null ? fi.growth_rate * 100 : undefined),
      };
    }

    // Prepare data for PWERM analysis in the format expected by the Python script
    const pwermInput = {
      company_name: mergedCompany.name || company.name,
      current_arr_usd: (mergedCompany.current_arr_usd || 1000000) / 1000000, // Convert to millions if needed
      growth_rate: (mergedCompany.revenue_growth_annual_pct || 70) / 100, // Convert percentage to decimal
      sector: mergedCompany.sector || 'Technology',
      assumptions: {
        ...assumptions,
        burn_rate_monthly_usd: mergedCompany.burn_rate_monthly_usd ?? company.burn_rate_monthly_usd,
        runway_months: mergedCompany.runway_months ?? company.runway_months,
        total_invested_usd: (mergedCompany.total_invested_usd ?? company.total_invested_usd) || 0,
        ownership_percentage: (mergedCompany.ownership_percentage ?? company.ownership_percentage) || 0
      }
    };

    const { path: scriptPath, tried } = resolveScriptPath('pwerm_analysis.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `PWERM script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const scriptsDir = path.dirname(scriptPath);
    
    console.log('PWERM Input Structure:', JSON.stringify(pwermInput, null, 2));

    // Debug: Log if API keys are available
    console.log('TAVILY_API_KEY available:', !!process.env.TAVILY_API_KEY);
    console.log('ANTHROPIC_API_KEY available:', !!process.env.ANTHROPIC_API_KEY);
    console.log('OPENAI_API_KEY available:', !!process.env.OPENAI_API_KEY);
    
    const result = await runPythonScript(scriptPath, [], scriptsDir, JSON.stringify(pwermInput));

    console.log('Python Script Result:', JSON.stringify(result, null, 2));

    if (!result.success) {
      console.error('PWERM analysis failed:', result.error);
      throw new Error(`PWERM analysis failed: ${result.error}`);
    }

    const pwermResults = result.data;
    console.log('PWERM Results Structure:', {
      hasMarketResearch: !!pwermResults.market_research,
      hasSummary: !!pwermResults.summary,
      scenarioCount: pwermResults.scenarios?.length || 0,
      hasCharts: !!pwermResults.charts
    });

    // Update company record with PWERM results
    const { error: updateError } = await supabaseService
        .from('companies')
        .update({
          has_pwerm_model: true,
          latest_pwerm_run_at: new Date().toISOString(),
          pwerm_scenarios_count: pwermResults.summary?.total_scenarios || 499,
          thesis_match_score: pwermResults.summary?.success_probability ? pwermResults.summary.success_probability * 100 : 50,
          // Store the full PWERM results in a JSON column if it exists
          pwerm_results: pwermResults
        })
        .eq('id', companyId);

      if (updateError) {
        console.error('Error updating company PWERM status:', updateError);
        // If pwerm_results column doesn't exist, try without it
        const { error: fallbackError } = await supabaseService
          .from('companies')
          .update({
            has_pwerm_model: true,
            latest_pwerm_run_at: new Date().toISOString(),
            pwerm_scenarios_count: pwermResults.summary?.total_scenarios || 499,
            thesis_match_score: pwermResults.summary?.success_probability ? pwermResults.summary.success_probability * 100 : 50
          })
          .eq('id', companyId);
        
        if (fallbackError) {
          console.error('Error updating company PWERM status (fallback):', fallbackError);
        }
      }

      // Return enhanced response format
      return NextResponse.json({
        success: true,
        message: 'PWERM analysis completed successfully',
        company_id: companyId,
        results: pwermResults
      });

  } catch (error) {
    console.error('POST /api/companies/[id]/pwerm error:', error);
    return NextResponse.json({ 
      error: 'PWERM analysis failed', 
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: companyId } = await params;
    
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Get company PWERM status and results
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('has_pwerm_model, latest_pwerm_run_at, pwerm_scenarios_count, pwerm_results')
      .eq('id', companyId)
      .single();

    if (companyError) {
      console.error('Error fetching company PWERM status:', companyError);
      return NextResponse.json({ error: 'Failed to fetch company PWERM status' }, { status: 500 });
    }

    return NextResponse.json({
      has_pwerm_model: company.has_pwerm_model || false,
      latest_pwerm_run_at: company.latest_pwerm_run_at,
      pwerm_scenarios_count: company.pwerm_scenarios_count || 0,
      latest_results: company.pwerm_results || null
    });

  } catch (error) {
    console.error('Error in PWERM status check:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

function runPythonScript(
  scriptPath: string, 
  args: string[], 
  cwd: string,
  stdinData?: string
): Promise<{ success: boolean; data?: any; error?: string }> {
  return new Promise((resolve) => {
    // Explicitly construct environment variables
    const env = {
      ...process.env,
      PYTHONPATH: cwd,
      // Pass API keys from environment
      TAVILY_API_KEY: process.env.TAVILY_API_KEY,
      ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY,
      // Set working directory for .env.local file
      PWD: process.cwd()
    };
    
    console.log('Python environment check:', {
      TAVILY_API_KEY: env.TAVILY_API_KEY ? 'SET' : 'NOT SET',
      ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY ? 'SET' : 'NOT SET',
      OPENAI_API_KEY: env.OPENAI_API_KEY ? 'SET' : 'NOT SET',
      cwd: cwd,
      scriptPath: scriptPath
    });
    
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
      const message = data.toString();
      stderr += message;
      // Log Python stderr to Node console for debugging
      console.log('[Python]', message.trim());
    });

    // Send stdin data if provided
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
