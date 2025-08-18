const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function cleanupTestCompanies() {
  console.log('Removing test companies...');
  
  // List of test company names to remove
  const testCompanyNames = [
    'Test Company',
    'Test Corp',
    'Test Inc',
    'test',
    'TEST',
    'Demo Company',
    'Example Corp',
    'Sample Inc'
  ];
  
  try {
    // Delete companies with test names
    for (const name of testCompanyNames) {
      const { data, error } = await supabase
        .from('companies')
        .delete()
        .ilike('name', `%${name}%`);
      
      if (error) {
        console.error(`Error removing ${name}:`, error);
      } else {
        console.log(`Removed companies matching: ${name}`);
      }
    }
    
    // Also remove any company with null or zero ARR that might be test data
    const { data: nullARR, error: nullError } = await supabase
      .from('companies')
      .delete()
      .or('current_arr_usd.is.null,current_arr_usd.eq.0')
      .ilike('name', '%test%');
    
    if (nullError) {
      console.error('Error removing null ARR test companies:', nullError);
    } else {
      console.log('Removed test companies with null/zero ARR');
    }
    
    console.log('Cleanup complete!');
    
    // Show remaining companies count
    const { count } = await supabase
      .from('companies')
      .select('*', { count: 'exact', head: true });
    
    console.log(`Total companies remaining: ${count}`);
    
  } catch (error) {
    console.error('Cleanup failed:', error);
  }
}

cleanupTestCompanies();