/**
 * Test if company websites are being found and scraped properly
 */

import { enhancedCimScraper } from './src/lib/enhanced-cim-scraper.js';
import { firecrawlScraper } from './src/lib/firecrawl-scraper.js';
import { fetchCompanyData } from './src/lib/agent-skills/real-skill-implementations.js';

async function testWebsiteScraping() {
  const testCompanies = ['@Ramp', '@Deel', '@Brex'];
  
  console.log('🔍 Testing Website Discovery & Scraping\n');
  console.log('=' .repeat(50));
  
  for (const company of testCompanies) {
    console.log(`\n\n📊 Testing: ${company}`);
    console.log('-'.repeat(40));
    
    try {
      // Test 1: CIM Scraper (finds website)
      console.log('\n1️⃣ CIM Scraper - Finding website...');
      const cimResult = await enhancedCimScraper.scrapeCompanyWithVision(company.replace('@', ''));
      
      if (cimResult?.websiteUrl) {
        console.log(`   ✅ Website found: ${cimResult.websiteUrl}`);
        
        if (cimResult.funding) {
          console.log(`   💰 Funding found:`, {
            total: cimResult.funding.totalRaised,
            lastRound: cimResult.funding.lastRound?.series,
            amount: cimResult.funding.lastRound?.amount
          });
        }
      } else {
        console.log(`   ❌ No website found`);
      }
      
      // Test 2: Firecrawl Scraper (scrapes website)
      console.log('\n2️⃣ Firecrawl - Scraping website...');
      const firecrawlResult = await firecrawlScraper.scrapeCompanyWebsite(company.replace('@', ''));
      
      if (firecrawlResult) {
        console.log(`   ✅ Website scraped successfully`);
        if (firecrawlResult.funding) {
          console.log(`   💰 Funding extracted:`, firecrawlResult.funding);
        }
        if (firecrawlResult.websiteUrl) {
          console.log(`   🌐 URL: ${firecrawlResult.websiteUrl}`);
        }
      } else {
        console.log(`   ❌ Scraping failed`);
      }
      
      // Test 3: Full fetchCompanyData flow
      console.log('\n3️⃣ Full Flow - fetchCompanyData...');
      const fullData = await fetchCompanyData(company);
      
      console.log(`   📝 Sources used: ${fullData.sources.join(', ')}`);
      
      if (fullData.data.overview?.website) {
        console.log(`   ✅ Website in final data: ${fullData.data.overview.website}`);
      }
      
      if (fullData.data.funding) {
        console.log(`   💰 Funding in final data:`, {
          total: fullData.data.funding.totalRaised,
          lastRound: fullData.data.funding.lastRound
        });
      }
      
      console.log(`   📚 Citations: ${fullData.citations?.length || 0} sources`);
      
    } catch (error) {
      console.error(`   ⚠️ Error testing ${company}:`, error.message);
    }
  }
  
  console.log('\n\n' + '='.repeat(50));
  console.log('✅ Test Complete\n');
}

// Run the test
testWebsiteScraping().catch(console.error);