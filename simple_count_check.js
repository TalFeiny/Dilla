const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function simpleCountCheck() {
  try {
    console.log('=== Simple Database Count Check ===\n');

    // Check companies table with simple select
    const { data: companies, error: companyError } = await supabase
      .from('companies')
      .select('id, name, created_at')
      .order('created_at', { ascending: false });
    
    if (companyError) {
      console.error('Error fetching companies:', companyError);
    } else {
      console.log(`📊 COMPANIES: ${companies?.length || 0} total companies found`);
      console.log('   Recent 10 companies:');
      companies?.slice(0, 10).forEach((company, index) => {
        console.log(`   ${index + 1}. ${company.name} (added: ${new Date(company.created_at).toLocaleString()})`);
      });
    }

    console.log('');

    // Check if LPs table exists
    const { data: lps, error: lpError } = await supabase
      .from('lps')
      .select('id, name, created_at')
      .order('created_at', { ascending: false })
      .limit(10);
    
    if (lpError) {
      console.log(`❌ LPs table: ${lpError.message}`);
      if (lpError.code === '42P01') {
        console.log('   → LPs table does not exist - need to create it first');
      }
    } else {
      console.log(`👥 LIMITED PARTNERS: ${lps?.length || 0} LPs found`);
      lps?.forEach((lp, index) => {
        console.log(`   ${index + 1}. ${lp.name} (added: ${new Date(lp.created_at).toLocaleString()})`);
      });
    }

    console.log('\n=== Status Assessment ===');
    const companyCount = companies?.length || 0;
    
    if (companyCount >= 1000) {
      console.log('✅ Companies: FULL DATASET (1000+) - Ready for analysis');
    } else if (companyCount >= 500) {
      console.log(`⚠️  Companies: GOOD DATASET (${companyCount}) - Could import more for complete coverage`);
    } else if (companyCount > 0) {
      console.log(`⚠️  Companies: LIMITED DATASET (${companyCount}) - Should import the full 1000 company dataset`);
    } else {
      console.log('❌ Companies: EMPTY - Need to run company import scripts');
    }
    
    if (lpError && lpError.code === '42P01') {
      console.log('❌ LPs: TABLE MISSING - Need to create LPs table and import data');
    } else if (lps && lps.length > 0) {
      console.log(`✅ LPs: ${lps.length} records - LPs data is available`);
    } else {
      console.log('❌ LPs: EMPTY - Need to run LP import scripts');
    }

  } catch (err) {
    console.error('Unexpected error:', err);
  } finally {
    process.exit(0);
  }
}

simpleCountCheck();