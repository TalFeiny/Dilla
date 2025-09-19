/**
 * Test Dynamic Skill Chains
 * Run with: node test-skill-chains.js
 */

async function testSkillChains() {
  const API_URL = 'http://localhost:3001/api/agent/unified-brain';
  
  const testCases = [
    {
      name: 'Company Comparison',
      prompt: 'Compare @Ramp and @Brex',
      outputFormat: 'matrix',
      expectedSkills: ['company-fetcher', 'deal-comparer', 'chart-generator']
    },
    {
      name: 'Valuation Analysis',
      prompt: 'Value @Cursor using DCF',
      outputFormat: 'spreadsheet',
      expectedSkills: ['company-fetcher', 'financial-analyzer', 'valuation-engine', 'excel-generator']
    },
    {
      name: 'PWERM Scenarios',
      prompt: 'Calculate PWERM for @Deel with exit scenarios',
      outputFormat: 'spreadsheet',
      expectedSkills: ['company-fetcher', 'scenario-generator', 'pwerm-calculator']
    },
    {
      name: 'Market Research',
      prompt: 'Analyze the AI coding assistant market',
      outputFormat: 'memo',
      expectedSkills: ['market-analyzer', 'competitive-intelligence', 'memo-writer']
    },
    {
      name: 'Deck Generation',
      prompt: 'Create a deck for @Anthropic',
      outputFormat: 'deck',
      expectedSkills: ['company-fetcher', 'market-analyzer', 'chart-generator', 'deck-storytelling']
    }
  ];
  
  console.log('🧪 Testing Dynamic Skill Chains...\n');
  
  for (const test of testCases) {
    console.log(`\n📝 Test: ${test.name}`);
    console.log(`   Prompt: "${test.prompt}"`);
    console.log(`   Format: ${test.outputFormat}`);
    console.log(`   Expected skills: ${test.expectedSkills.join(' → ')}`);
    
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: test.prompt,
          outputFormat: test.outputFormat
        })
      });
      
      if (!response.ok) {
        console.log(`   ❌ API returned ${response.status}`);
        const error = await response.text();
        console.log(`   Error: ${error.substring(0, 200)}`);
        continue;
      }
      
      const data = await response.json();
      
      // Check if expected data is present
      if (test.outputFormat === 'spreadsheet' && Array.isArray(data)) {
        console.log(`   ✅ Received ${data.length} spreadsheet commands`);
      } else if (test.outputFormat === 'deck' && data.slides) {
        console.log(`   ✅ Received deck with ${data.slides.length} slides`);
      } else if (test.outputFormat === 'matrix' && data.matrix) {
        console.log(`   ✅ Received comparison matrix`);
      } else if (test.outputFormat === 'memo' && data.content) {
        console.log(`   ✅ Received memo (${data.content.length} chars)`);
      } else {
        console.log(`   ⚠️  Unexpected response format`);
        console.log(`   Keys: ${Object.keys(data).join(', ')}`);
      }
      
    } catch (error) {
      console.log(`   ❌ Error: ${error.message}`);
    }
  }
  
  console.log('\n✨ Test complete!\n');
}

// Test skill chain builder separately
async function testChainBuilder() {
  console.log('\n🔗 Testing Chain Builder...\n');
  
  // Import the modules (this won't work in Node directly, showing the logic)
  const testPrompts = [
    'Compare @Ramp and @Brex revenue growth',
    'Value @Cursor with PWERM and DCF',
    'Create investment deck for @Anthropic',
    'Analyze unit economics for @Deel',
    'Market research on AI coding assistants'
  ];
  
  testPrompts.forEach(prompt => {
    console.log(`\nPrompt: "${prompt}"`);
    
    // Extract companies
    const companies = (prompt.match(/@(\w+)/g) || []).map(m => m.substring(1));
    console.log(`Companies: ${companies.join(', ') || 'none'}`);
    
    // Detect intents
    const intents = [];
    if (/compar/i.test(prompt)) intents.push('compare');
    if (/valu|pwerm|dcf/i.test(prompt)) intents.push('value');
    if (/deck|presentation/i.test(prompt)) intents.push('deck');
    if (/unit|economics|cac|ltv/i.test(prompt)) intents.push('metrics');
    if (/market|research/i.test(prompt)) intents.push('market');
    
    console.log(`Intents: ${intents.join(', ')}`);
    
    // Suggest skill chain
    const chain = [];
    if (companies.length > 0) chain.push('company-fetcher');
    if (intents.includes('compare')) chain.push('deal-comparer');
    if (intents.includes('value')) chain.push('valuation-engine');
    if (intents.includes('deck')) chain.push('deck-storytelling');
    if (intents.includes('metrics')) chain.push('unit-economics-analyzer');
    if (intents.includes('market')) chain.push('market-analyzer');
    
    console.log(`Suggested chain: ${chain.join(' → ')}`);
  });
}

// Run tests
console.log('🚀 Dynamic Skill Chain Test Suite\n');
console.log('================================\n');

testChainBuilder();

console.log('\n================================\n');
console.log('Now testing with API (make sure server is running)...\n');

testSkillChains().catch(console.error);