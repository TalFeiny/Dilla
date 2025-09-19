#!/usr/bin/env node

/**
 * Test script for parallel company data gathering
 * Tests the unified-brain API with multiple @ mentions
 */

async function testParallelCompanies() {
  const apiUrl = 'http://localhost:3001/api/agent/unified-brain';
  
  // Test cases with multiple companies
  const testCases = [
    {
      name: "Two company comparison",
      prompt: "Compare @Ramp and @Deel funding history and growth",
      expectedCompanies: ["Ramp", "Deel"]
    },
    {
      name: "Three company analysis",
      prompt: "Analyze @Stripe, @Square, and @Adyen market positions",
      expectedCompanies: ["Stripe", "Square", "Adyen"]
    },
    {
      name: "Multiple companies with analysis",
      prompt: "Create a competitive analysis for @Brex vs @Ramp vs @Divvy in the corporate cards space",
      expectedCompanies: ["Brex", "Ramp", "Divvy"]
    }
  ];
  
  console.log('🚀 Testing Parallel Company Processing\n');
  console.log('=' .repeat(60));
  
  for (const testCase of testCases) {
    console.log(`\n📝 Test: ${testCase.name}`);
    console.log(`   Prompt: "${testCase.prompt}"`);
    console.log(`   Expected companies: ${testCase.expectedCompanies.join(', ')}`);
    
    const startTime = Date.now();
    
    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: testCase.prompt,
          outputFormat: 'analysis'
        })
      });
      
      const endTime = Date.now();
      const duration = ((endTime - startTime) / 1000).toFixed(2);
      
      if (!response.ok) {
        console.log(`   ❌ Failed: ${response.status} ${response.statusText}`);
        continue;
      }
      
      const result = await response.json();
      
      // Check if companies were detected
      const detectedCompanies = testCase.expectedCompanies.filter(company => 
        result.analysis?.includes(company) || 
        result.content?.includes(company) ||
        JSON.stringify(result).includes(company)
      );
      
      console.log(`   ✅ Response received in ${duration}s`);
      console.log(`   📊 Companies detected: ${detectedCompanies.length}/${testCase.expectedCompanies.length}`);
      console.log(`   📈 Data sources used: ${result.dataSources?.join(', ') || 'Unknown'}`);
      
      // Check for parallel processing indicators
      if (duration < testCase.expectedCompanies.length * 5) {
        console.log(`   ⚡ Parallel processing likely (fast response)`);
      } else {
        console.log(`   🐌 Sequential processing suspected (slow response)`);
      }
      
    } catch (error) {
      console.log(`   ❌ Error: ${error.message}`);
    }
  }
  
  console.log('\n' + '=' .repeat(60));
  console.log('✅ Test completed\n');
}

// Performance comparison test
async function comparePerformance() {
  console.log('\n🏃 Performance Comparison: Sequential vs Parallel\n');
  console.log('=' .repeat(60));
  
  const apiUrl = 'http://localhost:3001/api/agent/unified-brain';
  
  // Test with increasing number of companies
  const companyCounts = [1, 2, 3, 4];
  const results = [];
  
  for (const count of companyCounts) {
    const companies = ['@Ramp', '@Deel', '@Brex', '@Mercury'].slice(0, count);
    const prompt = `Analyze funding history for ${companies.join(', ')}`;
    
    console.log(`\nTesting with ${count} company(ies): ${companies.join(', ')}`);
    
    const startTime = Date.now();
    
    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt, outputFormat: 'analysis' })
      });
      
      await response.json();
      const duration = ((Date.now() - startTime) / 1000).toFixed(2);
      
      results.push({ count, duration: parseFloat(duration) });
      console.log(`  Time taken: ${duration}s`);
      
    } catch (error) {
      console.log(`  Error: ${error.message}`);
    }
  }
  
  // Analyze results
  console.log('\n📊 Performance Analysis:');
  if (results.length >= 2) {
    const singleCompanyTime = results[0].duration;
    
    for (let i = 1; i < results.length; i++) {
      const expected = singleCompanyTime * results[i].count; // Sequential
      const actual = results[i].duration;
      const speedup = (expected / actual).toFixed(2);
      
      console.log(`  ${results[i].count} companies:`);
      console.log(`    Expected (sequential): ${expected.toFixed(2)}s`);
      console.log(`    Actual: ${actual}s`);
      console.log(`    Speedup: ${speedup}x ${speedup > 1.5 ? '✅ (parallel)' : '⚠️ (not parallel)'}`);
    }
  }
  
  console.log('\n' + '=' .repeat(60));
}

// Run tests
async function main() {
  console.log('🧪 Unified Brain Parallel Processing Test Suite\n');
  
  // Check if server is running
  try {
    const healthCheck = await fetch('http://localhost:3001/api/health').catch(() => null);
    if (!healthCheck) {
      console.log('⚠️  Server not running on port 3001');
      console.log('   Please start the server with: npm run dev');
      process.exit(1);
    }
  } catch (error) {
    // Server might not have health endpoint, continue anyway
  }
  
  await testParallelCompanies();
  await comparePerformance();
  
  console.log('\n✅ All tests completed!\n');
}

// Handle errors
process.on('unhandledRejection', (error) => {
  console.error('Unhandled error:', error);
  process.exit(1);
});

// Run if executed directly
if (require.main === module) {
  main();
}

module.exports = { testParallelCompanies, comparePerformance };