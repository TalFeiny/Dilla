#!/usr/bin/env node

/**
 * Test script to verify grid integration
 * Run with: node test-grid-integration.js
 */

const fetch = require('node-fetch');

async function testGridIntegration() {
  console.log('🧪 Testing Grid Integration...\n');
  
  const BACKEND_URL = 'http://localhost:8000';
  const testPrompt = 'Compare @Ramp and @Mercury with revenue, valuation, and charts';
  
  try {
    console.log('📡 Sending request to backend...');
    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: testPrompt,
        output_format: 'spreadsheet',
        context: {
          includeFormulas: true,
          includeCitations: true
        }
      })
    });
    
    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }
    
    const data = await response.json();
    
    console.log('✅ Response received!\n');
    console.log('📊 Commands generated:', data.result?.commands?.length || 0);
    
    if (data.result?.commands) {
      console.log('\n📝 Sample commands:');
      data.result.commands.slice(0, 5).forEach(cmd => {
        console.log(`  - ${cmd}`);
      });
      
      // Check for different command types
      const writeCommands = data.result.commands.filter(c => c.includes('write('));
      const formulaCommands = data.result.commands.filter(c => c.includes('formula('));
      const styleCommands = data.result.commands.filter(c => c.includes('style('));
      const chartCommands = data.result.commands.filter(c => c.includes('createChart'));
      
      console.log('\n📈 Command breakdown:');
      console.log(`  - Write commands: ${writeCommands.length}`);
      console.log(`  - Formula commands: ${formulaCommands.length}`);
      console.log(`  - Style commands: ${styleCommands.length}`);
      console.log(`  - Chart commands: ${chartCommands.length}`);
      
      // Check for citations
      const citationCommands = data.result.commands.filter(c => c.includes('HYPERLINK'));
      console.log(`  - Citation links: ${citationCommands.length}`);
      
      console.log('\n✅ Grid integration test PASSED!');
    } else {
      console.log('⚠️ No commands found in response');
      console.log('Response structure:', Object.keys(data));
    }
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
    process.exit(1);
  }
}

// Run the test
testGridIntegration();