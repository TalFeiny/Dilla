// Test the REAL CIM scraper with actual API calls
const testRealScraper = async () => {
  // Import the actual enhanced CIM scraper
  const { EnhancedCIMScraper } = await import('./src/lib/enhanced-cim-scraper.ts');
  
  const scraper = new EnhancedCIMScraper();
  
  // Test with various company names (not hardcoded solutions)
  const testCompanies = [
    'artificialsocieties',  // Your example
    'openai',               // No camelCase
    'databricks',           // Compound word
    'clearbit',             // Another compound
    'snowflake'             // Single word
  ];
  
  console.log('Testing REAL website finding...\n');
  
  for (const company of testCompanies) {
    try {
      console.log(`Testing: ${company}`);
      const result = await scraper.findCompanyWebsite(company);
      console.log(`  → Found: ${result}\n`);
    } catch (error) {
      console.log(`  → Error: ${error.message}\n`);
    }
  }
};

// Check if we have the required env vars
if (!process.env.TAVILY_API_KEY && !process.env.NEXT_PUBLIC_TAVILY_API_KEY) {
  console.error('ERROR: No Tavily API key found in environment');
  console.log('Set TAVILY_API_KEY or NEXT_PUBLIC_TAVILY_API_KEY');
  process.exit(1);
}

testRealScraper().catch(console.error);