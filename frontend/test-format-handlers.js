#!/usr/bin/env node

/**
 * Test Format Handlers with GPU Cost Spectrum Analysis
 * Tests deck, matrix, docs, and spreadsheet formats with AI valuation data
 */

const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));

// Test companies with varying GPU cost profiles
const TEST_PROMPTS = {
  // High GPU cost (Gamma-like - code generation)
  highGPU: {
    prompt: "Analyze @Cursor @Lovable @Replit - code generation AI companies with high GPU costs",
    expectedGPUProfile: "extreme",
    expectedMarginImpact: 0.40
  },
  
  // Medium GPU cost (Perplexity-like - search synthesis)
  mediumGPU: {
    prompt: "Research @Perplexity @You.com @Phind - AI search companies with moderate GPU usage",
    expectedGPUProfile: "high", 
    expectedMarginImpact: 0.25
  },
  
  // Low GPU cost (Traditional SaaS with 10% AI)
  lowGPU: {
    prompt: "Compare @Ramp @Deel @Mercury - fintech SaaS with light AI features",
    expectedGPUProfile: "moderate",
    expectedMarginImpact: 0.15
  },
  
  // Roll-up model test
  rollUp: {
    prompt: "Analyze @Compressor @Teamshares - roll-up business models acquiring SMBs",
    expectedModel: "roll-up",
    expectedMultiple: 4
  },
  
  // Vertical SaaS test  
  verticalSaaS: {
    prompt: "Research @Toast @Veeva @Procore - vertical SaaS companies in specific industries",
    expectedModel: "vertical_saas",
    expectedMultiple: 20
  }
};

// Output formats to test
const FORMATS = ['deck', 'matrix', 'docs', 'spreadsheet', 'analysis'];

async function testFormat(format, prompt, testName) {
  console.log(`\n📊 Testing ${format.toUpperCase()} format - ${testName}`);
  console.log(`   Prompt: "${prompt}"`);
  
  try {
    const response = await fetch('http://localhost:3001/api/agent/unified-brain', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: prompt,
        output_format: format,
        context: {
          includeGPUAnalysis: true,
          includeMarginImpact: true,
          includeValuationMultiples: true
        }
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    // Validate response structure
    console.log(`   ✅ Response received`);
    console.log(`   - Has result: ${!!data.result}`);
    console.log(`   - Has citations: ${!!data.citations} (${data.citations?.length || 0} items)`);
    console.log(`   - Has metadata: ${!!data.metadata}`);
    
    if (data.metadata) {
      console.log(`   📈 Metadata:`);
      console.log(`      - Companies: ${data.metadata.companies?.join(', ') || 'None'}`);
      console.log(`      - Format: ${data.metadata.format}`);
      console.log(`      - Has Charts: ${data.metadata.hasCharts}`);
      console.log(`      - Has Scoring: ${data.metadata.hasScoring}`);
      
      if (data.metadata.winner) {
        console.log(`      - Winner: ${data.metadata.winner}`);
      }
    }
    
    // Format-specific validation
    switch(format) {
      case 'deck':
        validateDeckFormat(data.result);
        break;
      case 'matrix':
        validateMatrixFormat(data.result);
        break;
      case 'docs':
        validateDocsFormat(data.result);
        break;
      case 'spreadsheet':
        validateSpreadsheetFormat(data.result);
        break;
      case 'analysis':
        validateAnalysisFormat(data.result);
        break;
    }
    
    // Check for GPU cost data in results
    if (data.result) {
      checkGPUCostData(data.result, format);
    }
    
    return { success: true, data };
    
  } catch (error) {
    console.error(`   ❌ Error: ${error.message}`);
    return { success: false, error: error.message };
  }
}

function validateDeckFormat(result) {
  console.log(`   🎯 Deck Validation:`);
  console.log(`      - Has slides: ${!!result.slides} (${result.slides?.length || 0} slides)`);
  console.log(`      - Has title: ${!!result.title}`);
  console.log(`      - Has charts: ${result.charts?.length || 0}`);
  
  if (result.slides?.length > 0) {
    const firstSlide = result.slides[0];
    console.log(`      - First slide type: ${firstSlide.type}`);
    console.log(`      - Has content: ${!!firstSlide.content}`);
  }
}

function validateMatrixFormat(result) {
  console.log(`   🎯 Matrix Validation:`);
  console.log(`      - Has rows: ${!!result.rows} (${result.rows?.length || 0} rows)`);
  console.log(`      - Has columns: ${!!result.columns} (${result.columns?.length || 0} columns)`);
  console.log(`      - Has scoring: ${!!result.scoring}`);
  
  if (result.columns?.length > 0) {
    console.log(`      - Columns: ${result.columns.map(c => c.key).join(', ')}`);
  }
}

function validateDocsFormat(result) {
  console.log(`   🎯 Docs Validation:`);
  console.log(`      - Has sections: ${!!result.sections} (${result.sections?.length || 0} sections)`);
  console.log(`      - Has title: ${!!result.title}`);
  console.log(`      - Has executive summary: ${!!result.executiveSummary}`);
  
  if (result.sections?.length > 0) {
    console.log(`      - Section titles: ${result.sections.map(s => s.title).join(', ')}`);
  }
}

function validateSpreadsheetFormat(result) {
  console.log(`   🎯 Spreadsheet Validation:`);
  console.log(`      - Has data: ${!!result.data} (${result.data?.length || 0} rows)`);
  console.log(`      - Has columns: ${!!result.columns} (${result.columns?.length || 0} columns)`);
  console.log(`      - Has formulas: ${!!result.formulas}`);
  
  if (result.columns?.length > 0) {
    console.log(`      - Column names: ${result.columns.map(c => c.name).join(', ')}`);
  }
}

function validateAnalysisFormat(result) {
  console.log(`   🎯 Analysis Validation:`);
  console.log(`      - Has companies: ${!!result.companies} (${Object.keys(result.companies || {}).length} companies)`);
  console.log(`      - Has summary: ${!!result.summary}`);
  console.log(`      - Has recommendations: ${!!result.recommendations}`);
  
  if (result.companies) {
    for (const [company, data] of Object.entries(result.companies)) {
      console.log(`      - ${company}: ${data.business_model || 'Unknown model'}, Stage: ${data.stage || 'Unknown'}`);
    }
  }
}

function checkGPUCostData(result, format) {
  console.log(`   💰 GPU Cost Analysis:`);
  
  let gpuData = null;
  
  // Extract GPU data based on format
  if (format === 'analysis' && result.companies) {
    // Check first company for GPU data
    const firstCompany = Object.values(result.companies)[0];
    gpuData = firstCompany?.gpu_metrics || firstCompany?.gross_margin_analysis;
  } else if (format === 'spreadsheet' && result.data) {
    // Look for GPU cost columns
    const gpuColumns = result.columns?.filter(c => 
      c.name.toLowerCase().includes('gpu') || 
      c.name.toLowerCase().includes('compute')
    );
    console.log(`      - GPU columns found: ${gpuColumns?.length || 0}`);
  } else if (format === 'matrix' && result.rows) {
    // Check for GPU metrics in matrix rows
    const firstRow = result.rows[0];
    if (firstRow) {
      gpuData = {
        compute_intensity: firstRow.compute_intensity,
        gpu_costs: firstRow.gpu_costs,
        margin_impact: firstRow.margin_impact
      };
    }
  }
  
  if (gpuData) {
    console.log(`      - Compute intensity: ${gpuData.compute_intensity || 'N/A'}`);
    console.log(`      - GPU cost/transaction: ${gpuData.gpu_cost_per_transaction || 'N/A'}`);
    console.log(`      - Annual GPU costs: ${gpuData.annual_gpu_costs || 'N/A'}`);
    console.log(`      - Margin impact: ${gpuData.margin_impact || 'N/A'}`);
  } else {
    console.log(`      - No GPU data found in ${format} format`);
  }
}

async function runAllTests() {
  console.log('🚀 Starting Format Handler Tests with GPU Cost Spectrum\n');
  console.log('Testing spectrum from:');
  console.log('  - Low AI usage (10% costs) → Traditional SaaS');
  console.log('  - Medium AI usage (25% costs) → Search/synthesis');  
  console.log('  - High AI usage (40%+ costs) → Code generation (Gamma-like)\n');
  
  const results = [];
  
  // Test each prompt with each format
  for (const [testName, testConfig] of Object.entries(TEST_PROMPTS)) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`TEST SET: ${testName}`);
    console.log(`${'='.repeat(80)}`);
    
    for (const format of FORMATS) {
      const result = await testFormat(format, testConfig.prompt, testName);
      results.push({
        testName,
        format,
        success: result.success,
        error: result.error
      });
      
      // Small delay to avoid overwhelming the API
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  
  // Summary
  console.log(`\n${'='.repeat(80)}`);
  console.log('📊 TEST SUMMARY');
  console.log(`${'='.repeat(80)}`);
  
  const successful = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  
  console.log(`✅ Successful: ${successful}/${results.length}`);
  console.log(`❌ Failed: ${failed}/${results.length}`);
  
  if (failed > 0) {
    console.log('\nFailed tests:');
    results.filter(r => !r.success).forEach(r => {
      console.log(`  - ${r.testName} / ${r.format}: ${r.error}`);
    });
  }
  
  // Test GPU cost spectrum specifically
  console.log('\n💰 GPU COST SPECTRUM VALIDATION:');
  console.log('Expected spectrum:');
  console.log('  1. Gamma/Lovable (code gen): 40% margin impact, $5-20/transaction');
  console.log('  2. Perplexity (search): 25% margin impact, $0.10-0.50/query');
  console.log('  3. Traditional SaaS: 15% margin impact, $0.01-0.05/interaction');
  console.log('  4. No AI: 0% margin impact, $0 cost');
}

// Run the tests
runAllTests().then(() => {
  console.log('\n✨ All tests completed!');
  process.exit(0);
}).catch(error => {
  console.error('\n💥 Test suite failed:', error);
  process.exit(1);
});