'use client';

import { useState, useEffect } from 'react';
import { PWERMResultsDisplayV2 } from '@/components/pwerm/PWERMResultsDisplayV2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export default function PWERMTestPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  
  // Debug state changes
  useEffect(() => {
    console.log('Results state updated:', results);
  }, [results]);
  
  useEffect(() => {
    console.log('Error state updated:', error);
  }, [error]);
  
  useEffect(() => {
    console.log('Loading state updated:', loading);
  }, [loading]);
  
  // Form state
  const [formData, setFormData] = useState({
    company_name: 'Deel',
    current_arr: 500,
    growth_rate: 0.80,
    sector: 'SaaS-HR Tech'
  });

  const testPWERMAnalysis = async () => {
    console.log('Current formData state:', formData);
    console.log('Company name value:', formData.company_name);
    
    setLoading(true);
    setError(null);
    setResults(null);
    setLoadingMessage('Initializing analysis...');

    try {
      console.log('Sending PWERM request with data:', {
        company_name: formData.company_name,
        current_arr: formData.current_arr,
        growth_rate: formData.growth_rate,
        sector: formData.sector
      });

      // Create an AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.log('Request timing out after 5 minutes');
        controller.abort();
      }, 300000); // 5 minute timeout

      setLoadingMessage('Sending request to server...');
      
      // First try the test endpoint to verify frontend works
      const useTestEndpoint = false; // Use original endpoint
      const endpoint = useTestEndpoint ? '/api/test-pwerm-direct' : '/api/pwerm-analysis';
      
      let response;
      try {
        response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({
            company_name: formData.company_name,
            current_arr: formData.current_arr,
            growth_rate: formData.growth_rate,
            sector: formData.sector
          }),
          signal: controller.signal,
          // Increase buffer size for large responses
          keepalive: false,
        });
      } catch (fetchError) {
        console.error('Fetch error:', fetchError);
        throw new Error(`Network error: ${fetchError instanceof Error ? fetchError.message : 'Unknown'}`);
      }
      
      clearTimeout(timeoutId);

      console.log('Response received:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries())
      });

      setLoadingMessage('Received response from server...');

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch (e) {
          console.error('Failed to parse error response:', e);
          errorData = { error: `HTTP ${response.status}: ${response.statusText}` };
        }
        console.error('PWERM API Error:', errorData);
        throw new Error(errorData.error || 'Analysis failed');
      }

      setLoadingMessage('Processing response data...');
      
      // Parse JSON response directly without cloning
      const data = await response.json();
      console.log('PWERM API Response parsed successfully');
      console.log('Response keys:', Object.keys(data));
      console.log('Has summary:', !!data.summary);
      console.log('Has market_research:', !!data.market_research);
      console.log('Has scenarios:', !!data.scenarios);

      // Validate the response structure
      if (!data || typeof data !== 'object') {
        console.error('Response is not an object:', data);
        throw new Error('Invalid response - not an object');
      }

      if (!data.summary) {
        console.error('Missing summary in response:', data);
        throw new Error('Invalid response format - missing summary');
      }
      
      if (!data.market_research) {
        console.error('Missing market_research in response:', data);
        throw new Error('Invalid response format - missing market_research');
      }
      
      if (!data.scenarios) {
        console.error('Missing scenarios in response:', data);
        throw new Error('Invalid response format - missing scenarios');
      }

      console.log('Setting results with valid data');
      console.log('Data to be set:', {
        summary: data.summary,
        scenariosCount: data.scenarios?.length,
        hasChart: !!data.exit_distribution_chart
      });
      setResults(data);
      setLoadingMessage('');
      console.log('PWERM results set successfully:', data);
    } catch (err) {
      console.error('PWERM Analysis Error:', err);
      if (err instanceof Error) {
        if (err.name === 'AbortError') {
          setError('Request timed out - analysis is taking too long');
        } else {
          setError(err.message);
        }
      } else {
        setError('Unknown error occurred');
      }
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Intelligent PWERM Analysis</h1>
      
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Company Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="company_name">Company Name</Label>
              <Input
                id="company_name"
                value={formData.company_name}
                onChange={(e) => {
                  console.log('Company name input changed to:', e.target.value);
                  setFormData({...formData, company_name: e.target.value});
                }}
                placeholder="e.g., Deel, Rippling, Gusto"
              />
            </div>
            <div>
              <Label htmlFor="sector">Sector/Subsector</Label>
              <Select
                value={formData.sector}
                onValueChange={(value) => setFormData({...formData, sector: value})}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select sector" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="AI-Gen AI">AI - Generative AI</SelectItem>
                  <SelectItem value="AI-ML Infra">AI - ML Infrastructure</SelectItem>
                  <SelectItem value="AI-Applied AI">AI - Applied AI</SelectItem>
                  <SelectItem value="SaaS-HR Tech">SaaS - HR Tech</SelectItem>
                  <SelectItem value="SaaS-Sales/CRM">SaaS - Sales/CRM</SelectItem>
                  <SelectItem value="SaaS-DevTools">SaaS - Developer Tools</SelectItem>
                  <SelectItem value="SaaS-Data/Analytics">SaaS - Data/Analytics</SelectItem>
                  <SelectItem value="Fintech-Payments">Fintech - Payments</SelectItem>
                  <SelectItem value="Fintech-Banking">Fintech - Banking</SelectItem>
                  <SelectItem value="Fintech-Lending">Fintech - Lending</SelectItem>
                  <SelectItem value="Health-Telemedicine">Health - Telemedicine</SelectItem>
                  <SelectItem value="Health-Digital Health">Health - Digital Health</SelectItem>
                  <SelectItem value="Marketplace-Commerce">Marketplace - Commerce</SelectItem>
                  <SelectItem value="Marketplace-Mobility">Marketplace - Mobility</SelectItem>
                  <SelectItem value="B2B Fintech">B2B Fintech</SelectItem>
                  <SelectItem value="B2C Fintech">B2C Fintech</SelectItem>
                  <SelectItem value="E-com">E-commerce</SelectItem>
                  <SelectItem value="Edtech">Education Tech</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="current_arr">Current ARR ($M)</Label>
              <Input
                id="current_arr"
                type="number"
                value={formData.current_arr}
                onChange={(e) => setFormData({...formData, current_arr: parseFloat(e.target.value) || 0})}
                placeholder="e.g., 500"
              />
            </div>
            <div>
              <Label htmlFor="growth_rate">Annual Growth Rate</Label>
              <Input
                id="growth_rate"
                type="number"
                value={(formData.growth_rate * 100).toFixed(0)}
                onChange={(e) => setFormData({...formData, growth_rate: (parseFloat(e.target.value) || 0) / 100})}
                placeholder="e.g., 80"
                min="0"
                max="500"
              />
              <p className="text-sm text-muted-foreground mt-1">{(formData.growth_rate * 100).toFixed(0)}% annual growth</p>
            </div>
          </div>
          
          <button
            onClick={testPWERMAnalysis}
            disabled={loading}
            className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mt-4 disabled:opacity-50 w-full md:w-auto"
          >
            {loading ? loadingMessage || 'Running Analysis...' : 'Run PWERM Analysis'}
          </button>
        </CardContent>
      </Card>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <strong>Error:</strong> {error}
        </div>
      )}

      {results && <PWERMResultsDisplayV2 results={results} />}
    </div>
  );
} 