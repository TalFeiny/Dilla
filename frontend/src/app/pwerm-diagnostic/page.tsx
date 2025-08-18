'use client';

import { useState } from 'react';
import { PWERMResultsDisplay } from '@/components/pwerm/PWERMResultsDisplay';

export default function PWERMDiagnostic() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = (message: string) => {
    setLogs(prev => [...prev, `${new Date().toISOString()}: ${message}`]);
  };

  const runTest = async () => {
    setLoading(true);
    setResults(null);
    setLogs([]);
    addLog('Starting PWERM analysis...');

    try {
      addLog('Sending request to API...');
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

      addLog(`Response status: ${response.status}`);

      if (!response.ok) {
        const error = await response.json();
        addLog(`Error: ${JSON.stringify(error)}`);
        return;
      }

      addLog('Reading response...');
      const text = await response.text();
      addLog(`Response size: ${text.length} bytes`);

      addLog('Parsing JSON...');
      const data = JSON.parse(text);
      
      addLog(`Response keys: ${Object.keys(data).join(', ')}`);
      addLog(`Summary: ${JSON.stringify(data.summary)}`);
      addLog(`Scenarios count: ${data.scenarios?.length}`);
      addLog(`Has exit chart: ${!!data.exit_distribution_chart}`);

      addLog('Setting results...');
      setResults(data);
      addLog('Results set successfully!');

    } catch (err) {
      addLog(`Error: ${err.message}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">PWERM Diagnostic Test</h1>
      
      <button
        onClick={runTest}
        disabled={loading}
        className="bg-blue-500 text-white px-4 py-2 rounded mb-4 disabled:opacity-50"
      >
        {loading ? 'Running...' : 'Run PWERM Analysis'}
      </button>

      <div className="mb-6 bg-gray-100 p-4 rounded">
        <h2 className="font-bold mb-2">Logs:</h2>
        <pre className="text-xs">{logs.join('\n')}</pre>
      </div>

      {results && (
        <div>
          <h2 className="text-2xl font-bold mb-4">Results:</h2>
          <div className="mb-4 bg-green-100 p-4 rounded">
            <p>✅ Results loaded successfully!</p>
            <p>Expected exit value: ${results.summary?.expected_exit_value?.toFixed(1)}M</p>
          </div>
          <PWERMResultsDisplay results={results} />
        </div>
      )}
    </div>
  );
}