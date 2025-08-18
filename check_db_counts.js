const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function checkDatabaseCounts() {
  try {
    console.log('=== VC Platform Database Status Check ===\n');

    // Check companies table
    const { data: companyCount, error: companyError } = await supabase
      .from('companies')
      .select('id', { count: 'exact', head: true });
    
    if (companyError) {
      console.error('Error fetching companies count:', companyError);
    } else {
      console.log(`📊 COMPANIES: ${companyCount || 0} companies in database`);
      
      // Check for recent company imports
      const { data: recentCompanies, error: recentCompaniesError } = await supabase
        .from('companies')
        .select('name, created_at')
        .order('created_at', { ascending: false })
        .limit(5);
      
      if (recentCompaniesError) {
        console.error('Error fetching recent companies:', recentCompaniesError);
      } else {
        console.log('   Recent companies:');
        recentCompanies?.forEach(company => {
          console.log(`   - ${company.name} (added: ${new Date(company.created_at).toLocaleString()})`);
        });
      }
    }

    console.log('');

    // Check LPs table
    const { data: lpCount, error: lpError } = await supabase
      .from('lps')
      .select('id', { count: 'exact', head: true });
    
    if (lpError) {
      console.error('Error fetching LPs count:', lpError);
    } else {
      console.log(`👥 LIMITED PARTNERS: ${lpCount || 0} LPs in database`);
      
      // Check for recent LP imports
      const { data: recentLPs, error: recentLPsError } = await supabase
        .from('lps')
        .select('name, created_at')
        .order('created_at', { ascending: false })
        .limit(5);
      
      if (recentLPsError) {
        console.error('Error fetching recent LPs:', recentLPsError);
      } else {
        console.log('   Recent LPs:');
        recentLPs?.forEach(lp => {
          console.log(`   - ${lp.name} (added: ${new Date(lp.created_at).toLocaleString()})`);
        });
      }
    }

    console.log('');

    // Check other key tables
    const tables = ['documents', 'portfolio_companies', 'pwerm_results', 'funds'];
    
    for (const table of tables) {
      const { data: count, error } = await supabase
        .from(table)
        .select('id', { count: 'exact', head: true });
      
      if (error) {
        console.log(`❌ ${table.toUpperCase()}: Error - ${error.message}`);
      } else {
        console.log(`📋 ${table.toUpperCase()}: ${count || 0} records`);
      }
    }

    console.log('\n=== Summary ===');
    const totalCompanies = companyCount || 0;
    const totalLPs = lpCount || 0;
    
    if (totalCompanies >= 1000) {
      console.log('✅ Companies: FULL DATASET (1000+) loaded');
    } else if (totalCompanies > 0) {
      console.log(`⚠️  Companies: PARTIAL DATASET (${totalCompanies}/1000) - need to import more`);
    } else {
      console.log('❌ Companies: NO DATA - need to run import scripts');
    }
    
    if (totalLPs > 0) {
      console.log(`✅ LPs: ${totalLPs} Limited Partners loaded`);
    } else {
      console.log('❌ LPs: NO DATA - need to run LP import scripts');
    }

  } catch (err) {
    console.error('Error:', err);
  } finally {
    process.exit(0);
  }
}

checkDatabaseCounts();