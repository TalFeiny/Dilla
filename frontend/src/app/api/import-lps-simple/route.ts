import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';
import fs from 'fs';
import { parse } from 'csv-parse/sync';

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // First, test with a single simple LP to see what fields are required
    const testLp = {
      name: 'Test LP',
      type: 'individual',
      country: 'India'
    };

    console.log('Testing with simple LP:', testLp);
    
    const { data: testData, error: testError } = await supabaseService
      .from('lps')
      .insert([testLp])
      .select();

    if (testError) {
      console.error('Test error details:', testError);
      return NextResponse.json({ 
        error: 'Failed to insert test LP',
        details: testError,
        attemptedData: testLp
      }, { status: 400 });
    }

    // If test succeeded, delete it and proceed with actual import
    if (testData && testData[0]) {
      await supabaseService
        .from('lps')
        .delete()
        .eq('id', testData[0].id);
    }

    // Now read and import the actual data
    const csvPath = '/Users/admin/Downloads/India LP list - Sheet1.csv';
    const fileContent = fs.readFileSync(csvPath, 'utf-8');
    const csvData = parse(fileContent, {
      columns: true,
      skip_empty_lines: true,
      relax_quotes: true,
      relax_column_count: true
    });

    const lpsToInsert = [];
    for (const row of csvData) {
      const name = row['Name']?.trim();
      if (!name) continue;

      // Parse net worth
      let netWorthUsd = 0;
      const netWorth = row['Net Worth']?.trim();
      if (netWorth) {
        const match = netWorth.match(/\$([\d.]+)\s*([BMT])?/i);
        if (match) {
          let value = parseFloat(match[1]);
          const unit = match[2]?.toUpperCase();
          
          if (unit === 'B') {
            value = value * 1000000000;
          } else if (unit === 'M') {
            value = value * 1000000;
          } else if (unit === 'T') {
            value = value * 1000000000000;
          }
          
          netWorthUsd = value;
        }
      }

      // Create minimal LP object with only essential fields
      lpsToInsert.push({
        name: name,
        type: name.includes('family') ? 'family_office' : 'individual',
        country: 'India',
        // Add other fields that might exist in the table
        net_worth: netWorthUsd > 0 ? netWorthUsd : null,
        industry: row['Industry']?.trim() || null,
        notes: row['Notes']?.trim() || null
      });
    }

    // Insert in small batches
    const batchSize = 10;
    let inserted = 0;
    const results = [];

    for (let i = 0; i < Math.min(lpsToInsert.length, 10); i += batchSize) { // Try just first 10
      const batch = lpsToInsert.slice(i, i + batchSize);
      
      console.log(`Inserting batch ${i/batchSize + 1}:`, batch);
      
      const { data, error } = await supabaseService
        .from('lps')
        .insert(batch)
        .select();

      if (error) {
        console.error('Insert error:', error);
        results.push({
          batch: i/batchSize + 1,
          error: error,
          attemptedData: batch
        });
      } else {
        inserted += data?.length || 0;
        results.push({
          batch: i/batchSize + 1,
          success: true,
          inserted: data?.length || 0
        });
      }
    }

    // Get final count
    const { count } = await supabaseService
      .from('lps')
      .select('*', { count: 'exact', head: true });

    return NextResponse.json({
      success: inserted > 0,
      results: {
        totalRows: csvData.length,
        attempted: Math.min(lpsToInsert.length, 10),
        inserted: inserted,
        finalCount: count,
        batchResults: results
      }
    });

  } catch (error) {
    console.error('Import error:', error);
    return NextResponse.json({ 
      error: 'Failed to import LPs',
      details: error instanceof Error ? error.message : error
    }, { status: 500 });
  }
}