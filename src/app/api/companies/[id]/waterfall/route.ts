import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import { spawn } from 'child_process';
import path from 'path';

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

    // Get fund data if company is in a fund
    let fundData = null;
    if (company.fund_id) {
      const { data: fund, error: fundError } = await supabaseService
        .from('funds')
        .select('*')
        .eq('id', company.fund_id)
        .single();

      if (!fundError && fund) {
        fundData = fund;
      }
    }

    // Prepare data for waterfall analysis
    const waterfallData = {
      company_name: company.name,
      sector: company.sector,
      current_arr_usd: company.current_arr_usd || 0,
      total_invested_usd: company.total_invested_usd || 0,
      ownership_percentage: company.ownership_percentage || 0,
      exit_value_usd: company.exit_value_usd || 0,
      exit_multiple: company.exit_multiple || 0,
      fund_size_usd: fundData?.fund_size_usd || 0,
      target_net_multiple_bps: fundData?.target_net_multiple_bps || 30000,
      status: company.status,
      fund_id: company.fund_id
    };

    // Call Python waterfall script (you'll need to create this)
    const pythonScriptPath = path.join(process.cwd(), '..', 'waterfall_analysis.py');
    
    return new Promise((resolve) => {
      const pythonProcess = spawn('python3', [pythonScriptPath], {
        stdio: ['pipe', 'pipe', 'pipe']
      });

      // Send data to Python script
      pythonProcess.stdin.write(JSON.stringify(waterfallData));
      pythonProcess.stdin.end();

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', async (code) => {
        if (code !== 0) {
          console.error('Python script error:', errorOutput);
          resolve(NextResponse.json({ 
            error: 'Waterfall analysis failed', 
            details: errorOutput 
          }, { status: 500 }));
          return;
        }

        try {
          const waterfallResults = JSON.parse(output);
          
          // Store results in Supabase (you might want to create a waterfall_results table)
          const { error: updateError } = await supabaseService
            .from('companies')
            .update({
              latest_waterfall_run_at: new Date().toISOString()
            })
            .eq('id', companyId);

          if (updateError) {
            console.error('Error updating company waterfall status:', updateError);
          }

          resolve(NextResponse.json({
            success: true,
            company_id: companyId,
            waterfall_results: waterfallResults
          }));
        } catch (parseError) {
          console.error('Error parsing Python output:', parseError);
          resolve(NextResponse.json({ 
            error: 'Failed to parse waterfall results',
            output: output
          }, { status: 500 }));
        }
      });
    });

  } catch (error) {
    console.error('Error in waterfall analysis:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
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

    // Get company waterfall status
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('latest_waterfall_run_at')
      .eq('id', companyId)
      .single();

    if (companyError) {
      console.error('Error fetching company waterfall status:', companyError);
      return NextResponse.json({ error: 'Failed to fetch company waterfall status' }, { status: 500 });
    }

    return NextResponse.json({
      has_waterfall_model: !!company.latest_waterfall_run_at,
      latest_waterfall_run_at: company.latest_waterfall_run_at
    });

  } catch (error) {
    console.error('Error in waterfall status check:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
} 