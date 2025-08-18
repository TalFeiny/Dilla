'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';

export default function TestBasicModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const fetchAnalysis = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/documents/11/analysis');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Analysis data received:', data);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <h1 className="text-3xl font-bold mb-8">Basic Modal Test</h1>
      
      <div className="space-y-4 mb-8">
        <Button onClick={fetchAnalysis}>
          Fetch Analysis Data
        </Button>
        <Button onClick={() => setIsOpen(true)}>
          Open Basic Modal
        </Button>
      </div>

      <div className="space-y-2">
        <p>Loading: {loading ? 'Yes' : 'No'}</p>
        <p>Error: {error || 'None'}</p>
        <p>Analysis: {analysis ? 'Loaded' : 'Not loaded'}</p>
        {analysis && (
          <div>
            <p>ID: {analysis.id}</p>
            <p>Raw text length: {analysis.raw_text?.length || 0}</p>
            <p>Has comparables: {analysis.comparables_analysis ? 'Yes' : 'No'}</p>
          </div>
        )}
      </div>

      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Basic Modal</h2>
              <Button onClick={() => setIsOpen(false)} variant="ghost" size="sm">
                ✕
              </Button>
            </div>
            
            <div className="space-y-4">
              <p>Modal is open!</p>
              
              {loading && <p>Loading analysis...</p>}
              {error && <p>Error: {error}</p>}
              
              {analysis && (
                <div>
                  <p>Analysis loaded successfully!</p>
                  <p>Document ID: {analysis.id}</p>
                  <p>Raw text length: {analysis.raw_text?.length || 0}</p>
                  
                  <h3>Basic Info:</h3>
                  <p>Has extracted_data: {analysis.extracted_data ? 'Yes' : 'No'}</p>
                  <p>Has comparables_analysis: {analysis.comparables_analysis ? 'Yes' : 'No'}</p>
                  <p>Has issue_analysis: {analysis.issue_analysis ? 'Yes' : 'No'}</p>
                  <p>Has processing_summary: {analysis.processing_summary ? 'Yes' : 'No'}</p>
                  
                  {analysis.comparables_analysis && (
                    <div>
                      <h3>Comparables Analysis:</h3>
                      <p>Companies found: {analysis.comparables_analysis.companies_found}</p>
                      <p>M&A transactions count: {analysis.comparables_analysis.ma_transactions?.length || 0}</p>
                      <p>M&A deals count: {analysis.comparables_analysis.ma_deals?.length || 0}</p>
                    </div>
                  )}
                </div>
              )}
              
              <Button onClick={() => setIsOpen(false)}>
                Close Modal
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 