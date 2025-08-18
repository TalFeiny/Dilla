const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function setupTable() {
  try {
    // First check if table exists
    const { data: tables } = await supabase
      .from('pwerm_results')
      .select('id')
      .limit(1);
    
    console.log('PWERM results table already exists');
  } catch (error) {
    console.log('Table does not exist, please create it using Supabase dashboard with the SQL from scripts/create_pwerm_results_table.sql');
    console.log('\nSQL to run:');
    const fs = require('fs');
    const sql = fs.readFileSync('scripts/create_pwerm_results_table.sql', 'utf8');
    console.log(sql);
  }
  
  process.exit(0);
}

setupTable();