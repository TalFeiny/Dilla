const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');

// Load environment variables
const envPath = path.join(process.cwd(), '.env.local');
let SUPABASE_URL = '';
let SUPABASE_KEY = '';

if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf8');
  envContent.split('\n').forEach(line => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    
    const equalIndex = trimmed.indexOf('=');
    if (equalIndex === -1) return;
    
    const key = trimmed.substring(0, equalIndex).trim();
    const value = trimmed.substring(equalIndex + 1).trim()
      .replace(/^["']|["']$/g, '');
    
    if (key === 'NEXT_PUBLIC_SUPABASE_URL') SUPABASE_URL = value;
    if (key === 'SUPABASE_SERVICE_ROLE_KEY') SUPABASE_KEY = value;
  });
}

async function checkCompanyData() {
  const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
  
  // Get companies with real financial data
  const { data: companies, error } = await supabase
    .from('companies')
    .select('name, sector, current_arr_usd, current_valuation_usd, total_invested_usd, amount_raised, latest_investment_date, quarter_raised')
    .not('current_arr_usd', 'is', null)
    .not('current_valuation_usd', 'is', null)
    .order('current_valuation_usd', { ascending: false })
    .limit(20);
  
  if (error) {
    console.error('Error fetching companies:', error);
    return;
  }
  
  console.log('\n=== Companies with Real Financial Data ===\n');
  console.log(`Found ${companies.length} companies with valuation data\n`);
  
  // Calculate statistics
  const stats = {
    avgARR: 0,
    avgValuation: 0,
    avgMultiple: 0,
    sectors: {},
    fundingRounds: {}
  };
  
  companies.forEach(company => {
    const arr = company.current_arr_usd / 1000000; // Convert to millions
    const valuation = company.current_valuation_usd / 1000000;
    const multiple = valuation / arr;
    
    stats.avgARR += arr;
    stats.avgValuation += valuation;
    stats.avgMultiple += multiple;
    
    // Track sectors
    if (company.sector) {
      stats.sectors[company.sector] = (stats.sectors[company.sector] || 0) + 1;
    }
    
    // Track funding rounds
    if (company.quarter_raised) {
      stats.fundingRounds[company.quarter_raised] = (stats.fundingRounds[company.quarter_raised] || 0) + 1;
    }
    
    console.log(`${company.name}:`);
    console.log(`  Sector: ${company.sector || 'Unknown'}`);
    console.log(`  ARR: $${arr.toFixed(1)}M`);
    console.log(`  Valuation: $${valuation.toFixed(1)}M`);
    console.log(`  ARR Multiple: ${multiple.toFixed(1)}x`);
    console.log(`  Total Invested: $${(company.total_invested_usd / 1000000).toFixed(1)}M`);
    console.log(`  Latest Round: ${company.quarter_raised || 'Unknown'}`);
    console.log('');
  });
  
  // Print statistics
  const count = companies.length;
  console.log('\n=== Statistics ===\n');
  console.log(`Average ARR: $${(stats.avgARR / count).toFixed(1)}M`);
  console.log(`Average Valuation: $${(stats.avgValuation / count).toFixed(1)}M`);
  console.log(`Average ARR Multiple: ${(stats.avgMultiple / count).toFixed(1)}x`);
  
  console.log('\nSector Distribution:');
  Object.entries(stats.sectors).forEach(([sector, count]) => {
    console.log(`  ${sector}: ${count} companies`);
  });
  
  console.log('\nFunding Round Distribution:');
  Object.entries(stats.fundingRounds).forEach(([round, count]) => {
    console.log(`  ${round}: ${count} companies`);
  });
  
  // Get M&A transactions
  const { data: transactions, error: maError } = await supabase
    .from('ma_transactions')
    .select('*')
    .limit(10);
  
  if (!maError && transactions && transactions.length > 0) {
    console.log('\n=== Recent M&A Transactions ===\n');
    transactions.forEach(tx => {
      console.log(`${tx.target_company} acquired by ${tx.acquirer}:`);
      console.log(`  Deal Value: $${tx.deal_value_usd ? (tx.deal_value_usd / 1000000).toFixed(1) + 'M' : 'Undisclosed'}`);
      console.log(`  Revenue Multiple: ${tx.revenue_multiple || 'N/A'}x`);
      console.log(`  Date: ${tx.transaction_date}`);
      console.log('');
    });
  }
}

checkCompanyData().catch(console.error);