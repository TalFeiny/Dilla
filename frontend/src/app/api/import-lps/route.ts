import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import fs from 'fs';
import { parse } from 'csv-parse/sync';

export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const csvPath = '/Users/admin/Downloads/India LP list - Sheet1.csv';
    console.log('Reading India LPs CSV...');
    
    // Read and parse CSV
    let csvData: any[];
    try {
      const fileContent = fs.readFileSync(csvPath, 'utf-8');
      csvData = parse(fileContent, {
        columns: true,
        skip_empty_lines: true,
        relax_quotes: true,
        relax_column_count: true
      });
    } catch (error) {
      throw new Error(`Failed to read CSV: ${error}`);
    }

    console.log(`CSV has ${csvData.length} rows`);

    // Get organization ID from existing company (or create a default org)
    const { data: existingCompany } = await supabaseService
      .from('companies')
      .select('organization_id')
      .limit(1)
      .single();

    const orgId = existingCompany?.organization_id || 'default-org-id';

    // Process LPs
    const lpsToInsert = [];
    for (const row of csvData) {
      const name = row['Name']?.trim();
      if (!name) continue;

      // Parse net worth
      let netWorthUsd = null;
      const netWorth = row['Net Worth']?.trim();
      if (netWorth) {
        // Extract number from formats like "$119.5 B" or "$24.5 B"
        const match = netWorth.match(/\$([\d.]+)\s*([BMT])?/i);
        if (match) {
          let value = parseFloat(match[1]);
          const unit = match[2]?.toUpperCase();
          
          // Convert to USD
          if (unit === 'B') {
            value = value * 1000000000; // Billion
          } else if (unit === 'M') {
            value = value * 1000000; // Million
          } else if (unit === 'T') {
            value = value * 1000000000000; // Trillion
          }
          
          netWorthUsd = value;
        }
      }

      // Extract LinkedIn profiles
      const linkedinUrls = [];
      for (const key in row) {
        if (key.includes('Key Person') && row[key]?.includes('linkedin.com')) {
          linkedinUrls.push(row[key].trim());
        }
      }

      lpsToInsert.push({
        organization_id: orgId,
        name: name,
        lp_type: name.toLowerCase().includes('family') ? 'family_office' : 'individual',
        country: 'India',
        status: 'active',
        contact_name: name,
        investment_capacity_usd: netWorthUsd ? netWorthUsd * 0.01 : null, // Assume 1% of net worth
        investment_focus: {
          net_worth_usd: netWorthUsd,
          industry: row['Industry']?.trim() || null,
          linkedin_profiles: linkedinUrls.length > 0 ? linkedinUrls : null,
          notes: row['Notes']?.trim() || null,
          preferred_sectors: row['Industry'] ? [row['Industry']] : null,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      });
    }

    console.log(`Prepared ${lpsToInsert.length} LPs for insertion`);

    // Check if limited_partners table exists
    const { error: tableCheckError } = await supabaseService
      .from('limited_partners')
      .select('id')
      .limit(1);

    if (tableCheckError && tableCheckError.code === 'PGRST116') {
      console.log('limited_partners table does not exist - run the migration first');
    }

    // Insert LPs in batches
    const batchSize = 50;
    let inserted = 0;
    const errors = [];

    for (let i = 0; i < lpsToInsert.length; i += batchSize) {
      const batch = lpsToInsert.slice(i, i + batchSize);
      
      const { data, error } = await supabaseService
        .from('limited_partners')
        .insert(batch)
        .select();

      if (error) {
        console.error(`Batch ${i/batchSize + 1} error:`, error);
        errors.push(`Batch ${i/batchSize + 1}: ${error.message || error.code || JSON.stringify(error)}`);
      } else {
        inserted += data?.length || 0;
        console.log(`Inserted batch ${i/batchSize + 1}: ${data?.length} LPs`);
      }
    }

    // Get final count
    const { count: finalCount } = await supabaseService
      .from('limited_partners')
      .select('*', { count: 'exact', head: true });

    // Get distribution by net worth
    const { data: allLps } = await supabaseService
      .from('limited_partners')
      .select('name, net_worth_usd, industry')
      .order('net_worth_usd', { ascending: false });

    const billionaires = allLps?.filter(lp => lp.net_worth_usd && lp.net_worth_usd >= 1000000000).length || 0;
    const millionaires = allLps?.filter(lp => lp.net_worth_usd && lp.net_worth_usd >= 1000000 && lp.net_worth_usd < 1000000000).length || 0;

    return NextResponse.json({
      success: true,
      results: {
        csvRows: csvData.length,
        lpsProcessed: lpsToInsert.length,
        lpsInserted: inserted,
        errors: errors,
        finalCount: finalCount,
        distribution: {
          billionaires,
          millionaires,
          byCountry: { India: finalCount }
        },
        topLps: allLps?.slice(0, 10).map(lp => ({
          name: lp.name,
          netWorth: `$${(lp.net_worth_usd / 1000000000).toFixed(1)}B`,
          industry: lp.industry
        }))
      }
    });

  } catch (error) {
    console.error('Import LPs error:', error);
    return NextResponse.json({ 
      error: 'Failed to import LPs',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}