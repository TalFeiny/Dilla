'use client';

import { useState } from 'react';

export default function DebugPWERM() {
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  const testAPI = async () => {
    setLoading(true);
    setOutput('Testing API...');
    
    try {
      const startTime = Date.now();
      const response = await fetch('/api/pwerm-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_name: 'Deel',
          current_arr: 500,
          growth_rate: 0.80,
          sector: 'SaaS-HR Tech'
        })
      });
      
      const endTime = Date.now();
      let result = `Status: ${response.status} ${response.statusText}\n`;
      result += `Time taken: ${endTime - startTime}ms\n`;
      result += `Headers: ${JSON.stringify(Object.fromEntries(response.headers.entries()), null, 2)}\n\n`;
      
      const text = await response.text();
      result += `Response length: ${text.length} bytes\n\n`;
      
      try {
        const data = JSON.parse(text);
        result += `Parsed successfully!\n`;
        result += `Keys: ${Object.keys(data).join(', ')}\n`;
        result += `Has summary: ${!!data.summary}\n`;
        result += `Has market_research: ${!!data.market_research}\n`;
        result += `Has scenarios: ${!!data.scenarios}\n`;
        if (data.scenarios) {
          result += `Scenarios count: ${data.scenarios.length}\n`;
        }
        if (data.summary) {
          result += `\nSummary:\n${JSON.stringify(data.summary, null, 2)}\n`;
        }
        if (data.error) {
          result += `\nError in response: ${data.error}\n`;
          result += `Details: ${data.details}\n`;
        }
      } catch (e) {
        result += `Parse error: ${e.message}\n`;
        result += `First 1000 chars:\n${text.substring(0, 1000)}\n`;
        result += `\nLast 1000 chars:\n${text.substring(text.length - 1000)}\n`;
      }
      
      setOutput(result);
    } catch (error) {
      setOutput(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">PWERM API Debug Test</h1>
      <button 
        onClick={testAPI}
        disabled={loading}
        className="bg-blue-500 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? 'Testing...' : 'Test PWERM API'}
      </button>
      <pre className="mt-4 p-4 bg-gray-100 rounded overflow-auto max-h-[600px] text-xs">
        {output}
      </pre>
    </div>
  );
}