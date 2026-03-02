import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export const maxDuration = 60;

export async function POST(request: NextRequest) {
  try {
    if (!supabaseService) {
      return NextResponse.json({ error: 'Supabase service not configured' }, { status: 500 });
    }

    // Fetch ALL companies using pagination
    const allCompanies = [];
    let offset = 0;
    const batchSize = 1000;
    let hasMore = true;

    console.log('Fetching all companies...');
    while (hasMore) {
      const { data, error } = await supabaseService
        .from('companies')
        .select('*')
        .order('name', { ascending: true })
        .range(offset, offset + batchSize - 1);

      if (error) throw error;

      if (data && data.length > 0) {
        allCompanies.push(...data);
        offset += batchSize;
        hasMore = data.length === batchSize;
      } else {
        hasMore = false;
      }
    }

    console.log(`Found ${allCompanies.length} total companies`);

    // Group companies by name
    const companiesByName = new Map<string, any[]>();
    for (const company of allCompanies) {
      const existing = companiesByName.get(company.name) || [];
      existing.push(company);
      companiesByName.set(company.name, existing);
    }

    // Find duplicates and decide which to keep
    const toDelete = [];
    let duplicateCount = 0;

    for (const [name, companies] of companiesByName) {
      if (companies.length > 1) {
        duplicateCount++;
        
        // Sort by data completeness - keep the one with most data
        companies.sort((a, b) => {
          // Prioritize companies with funding dates
          if (a.quarter_raised && !b.quarter_raised) return -1;
          if (!a.quarter_raised && b.quarter_raised) return 1;
          
          // Then prioritize those with amounts
          if (a.amount_raised && !b.amount_raised) return -1;
          if (!a.amount_raised && b.amount_raised) return 1;
          
          // Then prioritize those with more fields filled
          const aFields = Object.values(a).filter(v => v !== null && v !== '').length;
          const bFields = Object.values(b).filter(v => v !== null && v !== '').length;
          if (aFields !== bFields) return bFields - aFields;
          
          // Finally, keep the older one (lower in database)
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        });

        // Keep the first one (best), delete the rest
        for (let i = 1; i < companies.length; i++) {
          toDelete.push(companies[i].id);
        }
      }
    }

    console.log(`Found ${duplicateCount} duplicate names, will delete ${toDelete.length} records`);

    // Delete duplicates in batches
    let deleted = 0;
    if (toDelete.length > 0) {
      const deleteBatchSize = 100;
      for (let i = 0; i < toDelete.length; i += deleteBatchSize) {
        const batch = toDelete.slice(i, i + deleteBatchSize);
        const { error } = await supabaseService
          .from('companies')
          .delete()
          .in('id', batch);
        
        if (error) {
          console.error('Delete error:', error);
        } else {
          deleted += batch.length;
        }
      }
    }

    // Get final count
    const { count: finalCount } = await supabaseService
      .from('companies')
      .select('*', { count: 'exact', head: true });

    return NextResponse.json({
      success: true,
      results: {
        totalBefore: allCompanies.length,
        uniqueNames: companiesByName.size,
        duplicatesFound: duplicateCount,
        recordsDeleted: deleted,
        finalCount: finalCount
      }
    });

  } catch (error) {
    console.error('Deduplication error:', error);
    return NextResponse.json({ 
      error: 'Failed to deduplicate',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}