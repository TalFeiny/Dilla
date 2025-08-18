const { createClient } = require('@supabase/supabase-js');
require('dotenv').config({ path: '.env.local' });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

async function checkPWERMResults() {
  try {
    // Check if table exists and get recent results
    const { data, error } = await supabase
      .from('pwerm_results')
      .select('id, company_name, analysis_timestamp, expected_exit_value, current_arr_usd')
      .order('analysis_timestamp', { ascending: false })
      .limit(10);
    
    if (error) {
      console.error('Error fetching PWERM results:', error);
      return;
    }
    
    console.log(`Found ${data?.length || 0} PWERM results:`);
    if (data && data.length > 0) {
      data.forEach(result => {
        console.log(`- ${result.company_name}: $${result.expected_exit_value}M exit value (analyzed ${new Date(result.analysis_timestamp).toLocaleString()})`);
      });
    } else {
      console.log('No PWERM results found in database.');
    }
  } catch (err) {
    console.error('Error:', err);
  } finally {
    process.exit(0);
  }
}

checkPWERMResults();