// Test script for matrix generation
const testMatrixGeneration = async () => {
  try {
    console.log('Testing matrix generation...');
    
    const response = await fetch('http://localhost:3001/api/agent/unified-brain', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: 'Compare @Stripe and @Square financial metrics',
        outputFormat: 'matrix'
      })
    });
    
    const data = await response.json();
    
    console.log('Response status:', response.status);
    console.log('Response data:', JSON.stringify(data, null, 2));
    
    if (data.result?.columns && data.result?.rows) {
      console.log('\n✅ Matrix generated successfully!');
      console.log('Columns:', data.result.columns.map(c => c.name).join(', '));
      console.log('Rows:', data.result.rows.length);
    } else {
      console.log('\n❌ Matrix generation failed');
      console.log('Result:', data.result);
    }
    
  } catch (error) {
    console.error('Test failed:', error);
  }
};

// Run the test
testMatrixGeneration();