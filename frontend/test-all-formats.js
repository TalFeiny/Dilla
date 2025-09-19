#!/usr/bin/env node

/**
 * Test script to verify all output formats are working correctly
 * Run with: node test-all-formats.js
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Test configurations for each format
const formatTests = [
  {
    name: 'Spreadsheet Format',
    format: 'spreadsheet',
    prompt: 'Create a DCF model for @Ramp with 10% discount rate',
    expectedFields: ['commands', 'hasFormulas', 'hasCharts']
  },
  {
    name: 'Matrix Format',
    format: 'matrix',
    prompt: 'Compare @Stripe @Square @Adyen key metrics',
    expectedFields: ['data', 'headers', 'rows']
  },
  {
    name: 'Deck Format',
    format: 'deck',
    prompt: 'Create a 5-slide pitch deck for @Mercury',
    expectedFields: ['slides', 'title', 'theme']
  },
  {
    name: 'Docs Format',
    format: 'docs',
    prompt: 'Write a detailed analysis of @Deel business model',
    expectedFields: ['content', 'financialAnalyses']
  },
  {
    name: 'Analysis Format (default)',
    format: 'analysis',
    prompt: 'Analyze @Clay unit economics',
    expectedFields: ['summary', 'keyMetrics']
  }
];

async function testFormat(config) {
  console.log(`\n${'='.repeat(50)}`);
  console.log(`Testing: ${config.name}`);
  console.log(`Format: ${config.format}`);
  console.log(`Prompt: ${config.prompt}`);
  console.log(`${'='.repeat(50)}`);
  
  try {
    const startTime = Date.now();
    
    // Test non-streaming first
    console.log('\n📋 Testing non-streaming response...');
    const response = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: config.prompt,
        output_format: config.format,
        stream: false
      })
    });
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(`HTTP ${response.status}: ${error}`);
    }
    
    const data = await response.json();
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
    
    console.log(`✅ Response received in ${elapsed}s`);
    
    // Check if response has expected structure
    if (data.success) {
      console.log('✅ Success flag: true');
      
      // Check for expected fields
      console.log('\n📊 Checking expected fields:');
      for (const field of config.expectedFields) {
        const hasField = data.result && field.split('.').reduce((obj, key) => obj?.[key], data.result) !== undefined;
        console.log(`  ${hasField ? '✅' : '❌'} ${field}: ${hasField ? 'present' : 'missing'}`);
      }
      
      // For spreadsheet format, check commands
      if (config.format === 'spreadsheet' && data.result?.commands) {
        console.log(`\n📝 Commands found: ${data.result.commands.length}`);
        if (data.result.commands.length > 0) {
          console.log('Sample commands:');
          data.result.commands.slice(0, 3).forEach(cmd => {
            console.log(`  - ${cmd.substring(0, 60)}...`);
          });
        }
      }
      
      // For matrix format, check data structure
      if (config.format === 'matrix' && data.result?.data) {
        const { headers, rows } = data.result.data;
        console.log(`\n📊 Matrix data:`);
        console.log(`  - Headers: ${headers?.length || 0} columns`);
        console.log(`  - Rows: ${rows?.length || 0} rows`);
        if (headers?.length > 0) {
          console.log(`  - Sample headers: ${headers.slice(0, 5).join(', ')}`);
        }
      }
      
      // For deck format, check slides
      if (config.format === 'deck' && data.result?.slides) {
        console.log(`\n🎯 Deck structure:`);
        console.log(`  - Slides: ${data.result.slides.length}`);
        console.log(`  - Title: ${data.result.title || 'No title'}`);
        data.result.slides.forEach((slide, i) => {
          console.log(`  - Slide ${i + 1}: ${slide.title || slide.type}`);
        });
      }
      
      // Check for citations
      if (data.result?.citations) {
        console.log(`\n📚 Citations: ${data.result.citations.length} sources`);
      }
      
    } else {
      console.log('❌ Success flag: false');
      console.log('Error:', data.error);
    }
    
    // Test streaming
    console.log('\n\n🌊 Testing streaming response...');
    const streamResponse = await fetch(`${BACKEND_URL}/api/agent/unified-brain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: config.prompt,
        output_format: config.format,
        stream: true
      })
    });
    
    if (!streamResponse.ok) {
      throw new Error(`Streaming failed: ${streamResponse.status}`);
    }
    
    const reader = streamResponse.body.getReader();
    const decoder = new TextDecoder();
    let eventCount = 0;
    let hasComplete = false;
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          eventCount++;
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') {
            console.log('✅ Stream completed');
            break;
          }
          
          try {
            const event = JSON.parse(dataStr);
            if (event.type === 'complete') {
              hasComplete = true;
              console.log('✅ Complete event received');
              
              // For spreadsheet, check for commands in complete event
              if (config.format === 'spreadsheet' && event.result?.commands) {
                console.log(`  - Commands in complete event: ${event.result.commands.length}`);
              }
            }
          } catch (e) {
            // Ignore parse errors for partial chunks
          }
        }
      }
    }
    
    console.log(`📊 Stream stats: ${eventCount} events, complete: ${hasComplete ? 'yes' : 'no'}`);
    
    return { success: true, format: config.format };
    
  } catch (error) {
    console.error(`\n❌ Test failed: ${error.message}`);
    return { success: false, format: config.format, error: error.message };
  }
}

async function runAllTests() {
  console.log('🚀 Starting Format Tests');
  console.log(`Backend URL: ${BACKEND_URL}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);
  
  const results = [];
  
  for (const test of formatTests) {
    const result = await testFormat(test);
    results.push(result);
    
    // Add delay between tests to avoid overwhelming the backend
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  // Summary
  console.log(`\n\n${'='.repeat(50)}`);
  console.log('📊 TEST SUMMARY');
  console.log(`${'='.repeat(50)}`);
  
  const passed = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;
  
  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    console.log(`${icon} ${result.format}: ${result.success ? 'PASSED' : 'FAILED'}`);
    if (result.error) {
      console.log(`   Error: ${result.error}`);
    }
  });
  
  console.log(`\n📈 Results: ${passed} passed, ${failed} failed`);
  
  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
runAllTests().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});