import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import fs from 'fs/promises';
import { supabaseService } from '@/lib/supabase';
import { resolveScriptPath } from '@/lib/scripts-path';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const { companyId, scenarios } = await request.json();

    // Fetch funding history from database
    if (!supabaseService) {
      return NextResponse.json({ error: 'Database not configured' }, { status: 500 });
    }
    const { data: fundingRounds, error: fundingError } = await supabaseService
      .from('funding_rounds')
      .select('*')
      .eq('company_id', companyId)
      .order('round_date', { ascending: true });

    if (fundingError) {
      console.error('Error fetching funding rounds:', fundingError);
      return NextResponse.json(
        { error: 'Failed to fetch funding history' },
        { status: 500 }
      );
    }

    // Fetch company details
    const { data: company, error: companyError } = await supabaseService
      .from('companies')
      .select('*')
      .eq('id', companyId)
      .single();

    if (companyError) {
      console.error('Error fetching company:', companyError);
      return NextResponse.json(
        { error: 'Failed to fetch company data' },
        { status: 500 }
      );
    }

    // Prepare cap table data
    const capTableData = {
      company: {
        name: company.name,
        common_shares: company.common_shares || {},
        option_pool: company.option_pool_shares || 0
      },
      funding_rounds: fundingRounds.map(round => ({
        round_name: round.round_name,
        amount_raised: round.amount_raised,
        pre_money_valuation: round.pre_money_valuation,
        liquidation_multiple: round.liquidation_multiple || 1.0,
        liquidation_type: round.liquidation_type || 'non_participating',
        participation_cap: round.participation_cap,
        investors: round.investors || {},
        date: round.round_date
      })),
      scenarios: scenarios
    };

    // Run Python liquidation analysis
    const { path: scriptPath, tried } = resolveScriptPath('run_liquidation_analysis.py');
    if (!scriptPath) {
      return NextResponse.json(
        { error: `Liquidation script not found. Tried: ${tried.join(', ')}. Set SCRIPTS_DIR or run from repo root.` },
        { status: 500 }
      );
    }
    const inputPath = path.join('/tmp', `liq_input_${Date.now()}.json`);
    const outputPath = path.join('/tmp', `liq_output_${Date.now()}.json`);

    // Write input data
    await fs.writeFile(inputPath, JSON.stringify(capTableData));

    // Execute Python script
    const { stdout, stderr } = await execAsync(
      `python3 "${scriptPath}" "${inputPath}" "${outputPath}"`,
      { maxBuffer: 10 * 1024 * 1024 }
    );

    if (stderr && !stderr.includes('Warning')) {
      console.error('Python stderr:', stderr);
    }

    // Read results
    const resultsJson = await fs.readFile(outputPath, 'utf-8');
    const results = JSON.parse(resultsJson);

    // Clean up temp files
    await fs.unlink(inputPath).catch(() => {});
    await fs.unlink(outputPath).catch(() => {});

    // Save analysis results to database
    const { error: saveError } = await supabaseService
      .from('liquidation_analyses')
      .insert({
        company_id: companyId,
        analysis_date: new Date().toISOString(),
        preference_stack: results.preference_stack,
        conversion_thresholds: results.conversion_thresholds,
        scenario_returns: results.enhanced_scenarios,
        waterfall_data: results.waterfall_chart_data
      });

    if (saveError) {
      console.error('Error saving analysis:', saveError);
    }

    return NextResponse.json({
      success: true,
      analysis: results,
      fundingHistory: fundingRounds
    });

  } catch (error) {
    console.error('Liquidation analysis error:', error);
    return NextResponse.json(
      { error: 'Failed to perform liquidation analysis' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const companyId = searchParams.get('companyId');

  if (!companyId) {
    return NextResponse.json(
      { error: 'Company ID required' },
      { status: 400 }
    );
  }

  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Database not configured' }, { status: 500 });
    }
    // Fetch latest liquidation analysis
    const { data, error } = await supabaseService
      .from('liquidation_analyses')
      .select('*')
      .eq('company_id', companyId)
      .order('analysis_date', { ascending: false })
      .limit(1)
      .single();

    if (error) {
      return NextResponse.json(
        { error: 'No liquidation analysis found' },
        { status: 404 }
      );
    }

    return NextResponse.json(data);

  } catch (error) {
    console.error('Error fetching liquidation analysis:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analysis' },
      { status: 500 }
    );
  }
}