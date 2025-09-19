// Simple test for matrix generation
const test = async () => {
  const data = {
    prompt: 'Compare @Stripe and @Square revenue and valuation',
    outputFormat: 'matrix'
  };
  
  console.log('Request:', JSON.stringify(data, null, 2));
  console.log('\nSending to API...\n');
  
  try {
    const response = await fetch('http://localhost:3001/api/agent/unified-brain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      console.error('Response not OK:', response.status, response.statusText);
      const text = await response.text();
      console.error('Error body:', text);
      return;
    }
    
    const result = await response.json();
    
    if (result.result?.columns) {
      console.log('✅ Matrix Generated!');
      console.log('Columns:', result.result.columns.map(c => c.name));
      console.log('Rows:', result.result.rows?.length || 0);
      
      // Display first few rows
      if (result.result.rows?.length > 0) {
        console.log('\nFirst row data:');
        const firstRow = result.result.rows[0];
        result.result.columns.forEach((col, idx) => {
          const cell = firstRow.cells[col.id];
          console.log(`  ${col.name}: ${cell?.displayValue || 'N/A'}`);
        });
      }
    } else {
      console.log('❌ No matrix in response');
      console.log('Result:', JSON.stringify(result.result, null, 2));
    }
  } catch (error) {
    console.error('Request failed:', error.message);
  }
};

test();