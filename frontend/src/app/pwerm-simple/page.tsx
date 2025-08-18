'use client';

import { useState } from 'react';

export default function SimplePWERMTest() {
  const [status, setStatus] = useState('Ready');
  const [result, setResult] = useState<any>(null);

  const testAPI = async () => {
    setStatus('Starting...');
    setResult(null);
    
    try {
      setStatus('Sending request...');
      const response = await fetch('/api/pwerm-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: 'Deel',
          current_arr: 500,
          growth_rate: 0.80,
          sector: 'SaaS-HR Tech'
        })
      });
      
      setStatus(`Response status: ${response.status}`);
      
      if (!response.ok) {
        const error = await response.json();
        setStatus(`Error: ${error.error}`);
        return;
      }
      
      setStatus('Parsing response...');
      const data = await response.json();
      
      setStatus('Success!');
      setResult({
        keys: Object.keys(data),
        hasSummary: !!data.summary,
        hasMarketResearch: !!data.market_research,
        hasScenarios: !!data.scenarios,
        summaryData: data.summary
      });
      
    } catch (err) {
      setStatus(`Error: ${err.message}`);
      console.error('Full error:', err);
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Simple PWERM Test</h1>
      <button 
        onClick={testAPI}
        className="bg-blue-500 text-white px-4 py-2 rounded mb-4"
      >
        Test API
      </button>
      <div className="mb-4">
        <strong>Status:</strong> {status}
      </div>
      {result && (
        <div className="bg-gray-100 p-4 rounded">
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}