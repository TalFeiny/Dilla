import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { PWERMPlaygroundConfig, CreatePWERMAnalysisRequest } from '@/types/portfolio';
import { spawn } from 'child_process';
import path from 'path';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const supabase = createClient(supabaseUrl, supabaseServiceKey);

export async function POST(request: NextRequest) {
  try {
    const body: PWERMPlaygroundConfig = await request.json();
    
    // Validate required fields
    if (!body.company_id || !body.base_assumptions) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    
    // Get company data
    const { data: company, error: companyError } = await supabase
      .from('companies')
      .select('*')
      .eq('id', body.company_id)
      .single();
    
    if (companyError || !company) {
      return NextResponse.json({ error: 'Company not found' }, { status: 404 });
    }
    
    // Create temporary config file for the Python script
    const configData = {
      company_id: body.company_id,
      portfolio_company_id: body.portfolio_company_id,
      base_assumptions: body.base_assumptions,
      custom_scenarios: body.custom_scenarios,
      ai_monitoring_config: body.ai_monitoring_config
    };
    
    // Run the PWERM Python script
    const result = await runPWERMScript(configData);
    
    if (!result.success) {
      return NextResponse.json({ error: result.error }, { status: 500 });
    }
    
    // If we have a portfolio company ID, save the analysis
    if (body.portfolio_company_id) {
      const analysisRequest: CreatePWERMAnalysisRequest = {
        portfolio_company_id: body.portfolio_company_id,
        analyst_name: 'AI Playground',
        base_assumptions: body.base_assumptions,
        scenarios: result.data.scenarios
      };
      
      const { error: saveError } = await supabase
        .from('pwerm_analyses')
        .insert({
          portfolio_company_id: body.portfolio_company_id,
          analyst_name: analysisRequest.analyst_name,
          base_assumptions: analysisRequest.base_assumptions,
          scenarios: analysisRequest.scenarios,
          expected_return_usd: result.data.expected_return_usd,
          expected_multiple: result.data.expected_multiple,
          expected_irr: result.data.expected_irr,
          risk_adjusted_return: result.data.risk_adjusted_return,
          confidence_interval_lower: result.data.confidence_interval_95[0],
          confidence_interval_upper: result.data.confidence_interval_95[1],
          scenario_count: result.data.scenario_count,
          analysis_metadata: result.data.analysis_metadata
        });
      
      if (saveError) {
        console.error('Error saving PWERM analysis:', saveError);
      }
    }
    
    return NextResponse.json({
      success: true,
      data: result.data,
      company: company
    });
    
  } catch (error) {
    console.error('Error in PWERM playground:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

async function runPWERMScript(config: any): Promise<{ success: boolean; data?: any; error?: string }> {
  return new Promise((resolve) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'pwerm8_playground.py');
    const configJson = JSON.stringify(config);
    
    const child = spawn('python3', [scriptPath, '--config', configJson], {
      env: {
        ...process.env,
        NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY
      }
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });
    
    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });
    
    child.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve({ success: true, data: result });
        } catch (error) {
          resolve({ success: false, error: 'Failed to parse PWERM script output' });
        }
      } else {
        resolve({ success: false, error: stderr || 'PWERM script failed' });
      }
    });
    
    child.on('error', (error) => {
      resolve({ success: false, error: error.message });
    });
  });
} 