import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import fs from 'fs';
import { parse } from 'csv-parse/sync';

export const maxDuration = 60; // Allow 60 seconds for this operation

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    const results = {
      duplicatesRemoved: 0,
      companiesAdded: 0,
      datesUpdated: 0,
      errors: [] as string[]
    };

    // Step 1: Get all existing companies
    console.log('Fetching all existing companies...');
    const { data: allCompanies, error: fetchError } = await supabaseService
      .from('companies')
      .select('*')
      .range(0, 49999);

    if (fetchError) {
      throw new Error(`Failed to fetch companies: ${fetchError.message}`);
    }

    console.log(`Found ${allCompanies?.length || 0} total records`);

    // Step 2: Remove duplicates - keep only the first occurrence of each company
    const seen = new Set<string>();
    const toDelete: string[] = [];
    const uniqueCompanies = new Map<string, any>();

    for (const company of allCompanies || []) {
      if (seen.has(company.name)) {
        toDelete.push(company.id);
        results.duplicatesRemoved++;
      } else {
        seen.add(company.name);
        uniqueCompanies.set(company.name, company);
      }
    }

    // Delete duplicates in batches
    if (toDelete.length > 0) {
      console.log(`Removing ${toDelete.length} duplicate companies...`);
      const batchSize = 100;
      for (let i = 0; i < toDelete.length; i += batchSize) {
        const batch = toDelete.slice(i, i + batchSize);
        const { error: deleteError } = await supabaseService
          .from('companies')
          .delete()
          .in('id', batch);
        
        if (deleteError) {
          results.errors.push(`Delete error: ${deleteError.message}`);
        }
      }
    }

    // Step 3: Read CSV and prepare data
    const csvPath = '/Users/admin/Downloads/Secos 2 - Imported table-Grid view.csv';
    console.log('Reading CSV file...');
    
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

    // Get organization ID
    const orgId = allCompanies?.[0]?.organization_id;
    if (!orgId) {
      throw new Error('No organization ID found');
    }

    // Step 4: Process CSV data
    const companiesToAdd: any[] = [];
    const datesToUpdate = new Map<string, { quarter: string, amount: number | null }>();

    for (const row of csvData) {
      const companyName = row['Company']?.trim();
      if (!companyName) continue;

      // Parse amount
      let amountUsd: number | null = null;
      const amountStr = row['Amount Raised']?.trim();
      if (amountStr && amountStr !== '$0.00M') {
        const cleaned = amountStr.replace(/[$M,]/g, '');
        const parsed = parseFloat(cleaned);
        if (!isNaN(parsed) && parsed > 0) {
          amountUsd = parsed * 1000000;
        }
      }

      // Get quarter
      const quarter = row['Raised']?.trim() || null;

      // Check if company exists
      if (uniqueCompanies.has(companyName)) {
        // Update existing company's date if available
        if (quarter) {
          datesToUpdate.set(companyName, { quarter, amount: amountUsd });
        }
      } else {
        // Add new company (primarily N-Z companies)
        companiesToAdd.push({
          name: companyName,
          sector: row['Sector']?.trim() || 'Technology',
          amount_raised: amountUsd,
          quarter_raised: quarter,
          country: row['Country']?.trim() || 'Global',
          revenue: row['Revenue (M$)']?.trim(),
          growth_rate: row['Growth Rate']?.trim()
        });
      }
    }

    // Step 5: Add new companies (N-Z and any missing ones)
    if (companiesToAdd.length > 0) {
      console.log(`Adding ${companiesToAdd.length} new companies...`);
      const batchSize = 50;
      
      for (let i = 0; i < companiesToAdd.length; i += batchSize) {
        const batch = companiesToAdd.slice(i, i + batchSize);
        const insertBatch = batch.map(company => ({
          organization_id: orgId,
          name: company.name,
          sector: company.sector,
          amount_raised: company.amount_raised,
          quarter_raised: company.quarter_raised,
          location: {
            geography: company.country,
            data_source: 'csv_import',
            amount_raised_usd: company.amount_raised
          },
          status: 'active'
        }));

        const { error: insertError } = await supabaseService
          .from('companies')
          .insert(insertBatch);

        if (insertError) {
          results.errors.push(`Insert error: ${insertError.message}`);
        } else {
          results.companiesAdded += batch.length;
        }
      }
    }

    // Step 6: Update funding dates for existing companies
    if (datesToUpdate.size > 0) {
      console.log(`Updating dates for ${datesToUpdate.size} companies...`);
      
      for (const [name, data] of datesToUpdate) {
        const company = uniqueCompanies.get(name);
        if (company) {
          const { error: updateError } = await supabaseService
            .from('companies')
            .update({
              quarter_raised: data.quarter,
              amount_raised: data.amount
            })
            .eq('id', company.id);

          if (updateError) {
            results.errors.push(`Update error for ${name}: ${updateError.message}`);
          } else {
            results.datesUpdated++;
          }
        }
      }
    }

    // Step 7: Get final statistics
    const { count: finalCount } = await supabaseService
      .from('companies')
      .select('*', { count: 'exact', head: true });

    const { data: sampleCompanies } = await supabaseService
      .from('companies')
      .select('name')
      .order('name')
      .range(0, 49999);

    const uniqueNames = [...new Set(sampleCompanies?.map(c => c.name) || [])];
    const distribution: Record<string, number> = {};
    
    for (const letter of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
      const count = uniqueNames.filter(n => n[0].toUpperCase() === letter).length;
      if (count > 0) distribution[letter] = count;
    }

    return NextResponse.json({
      success: true,
      results: {
        ...results,
        finalCount,
        uniqueCompanies: uniqueNames.length,
        distribution
      }
    });

  } catch (error) {
    console.error('Fix companies error:', error);
    return NextResponse.json({ 
      error: 'Failed to fix companies',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}