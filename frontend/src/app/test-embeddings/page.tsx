'use client';

import { useState } from 'react';
import { Search, Brain, Database, Zap } from 'lucide-react';

export default function TestEmbeddingsPage() {
  const [rlQuery, setRLQuery] = useState('Revenue should be 350M not 500M');
  const [companyQuery, setCompanyQuery] = useState('AI startup in fintech');
  const [rlResults, setRLResults] = useState<any>(null);
  const [companyResults, setCompanyResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Test RL embedding
  const testRLEmbedding = async () => {
    setLoading(true);
    try {
      // Generate embedding
      const embedResponse = await fetch('/api/agent/embeddings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: rlQuery,
          type: 'rl',
          context: 'feedback'
        })
      });
      
      const embedData = await embedResponse.json();
      
      // Search similar experiences
      const searchResponse = await fetch('/api/agent/rl-experience/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding: embedData.embedding,
          minReward: 0,
          limit: 5
        })
      });
      
      const searchData = await searchResponse.json();
      
      setRLResults({
        embedding: embedData,
        matches: searchData
      });
    } catch (error) {
      console.error('RL embedding test failed:', error);
      setRLResults({ error: error.message });
    }
    setLoading(false);
  };

  // Test company search
  const testCompanySearch = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/agent/embeddings/company', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: companyQuery,
          mode: 'hybrid',
          limit: 10
        })
      });
      
      const data = await response.json();
      setCompanyResults(data);
    } catch (error) {
      console.error('Company search failed:', error);
      setCompanyResults({ error: error.message });
    }
    setLoading(false);
  };

  // Update all company embeddings
  const updateCompanyEmbeddings = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/agent/embeddings/company?updateAll=true');
      const data = await response.json();
      alert(`Company embeddings updated: ${JSON.stringify(data)}`);
    } catch (error) {
      console.error('Failed to update embeddings:', error);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <h1 className="text-3xl font-bold text-gray-900">Dual Embedding System Test</h1>
        
        {/* RL Embeddings Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="w-6 h-6 text-purple-600" />
            <h2 className="text-xl font-semibold">RL Feedback Embeddings (384-dim)</h2>
          </div>
          
          <div className="space-y-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={rlQuery}
                onChange={(e) => setRLQuery(e.target.value)}
                placeholder="Enter feedback or action..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={testRLEmbedding}
                disabled={loading}
                className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                <Search className="w-5 h-5" />
              </button>
            </div>
            
            {rlResults && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold mb-2">Results:</h3>
                
                {rlResults.embedding && (
                  <div className="mb-4">
                    <p className="text-sm text-gray-600">
                      Embedding dimension: {rlResults.embedding.dimension}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      First 10 values: {rlResults.embedding.embedding?.slice(0, 10).map(v => v.toFixed(2)).join(', ')}...
                    </p>
                  </div>
                )}
                
                {rlResults.matches && (
                  <div>
                    <p className="text-sm font-semibold mb-2">
                      Similar experiences: {rlResults.matches.totalMatches || 0}
                    </p>
                    {rlResults.matches.experiences?.map((exp: any, i: number) => (
                      <div key={i} className="p-2 bg-white rounded mb-2">
                        <p className="text-sm">{exp.action_text}</p>
                        <p className="text-xs text-gray-500">
                          Similarity: {(exp.similarity * 100).toFixed(1)}% | 
                          Reward: {exp.reward?.toFixed(2)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                
                {rlResults.error && (
                  <p className="text-red-600">Error: {rlResults.error}</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Company Search Section */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-semibold">Company Semantic Search (768-dim)</h2>
          </div>
          
          <div className="space-y-4">
            <div className="flex gap-2">
              <input
                type="text"
                value={companyQuery}
                onChange={(e) => setCompanyQuery(e.target.value)}
                placeholder="Search companies..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={testCompanySearch}
                disabled={loading}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Search className="w-5 h-5" />
              </button>
            </div>
            
            {companyResults && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold mb-2">
                  Results ({companyResults.mode} mode):
                </h3>
                
                {companyResults.results?.map((company: any, i: number) => (
                  <div key={i} className="p-3 bg-white rounded mb-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-semibold">{company.name}</p>
                        <p className="text-sm text-gray-600">{company.sector}</p>
                        <p className="text-xs text-gray-500">{company.description?.slice(0, 100)}...</p>
                      </div>
                      <div className="text-right text-xs">
                        {company.combined_score && (
                          <p>Score: {(company.combined_score * 100).toFixed(1)}%</p>
                        )}
                        {company.semantic_rank !== undefined && (
                          <p>Semantic: {(company.semantic_rank * 100).toFixed(1)}%</p>
                        )}
                        {company.text_rank !== undefined && (
                          <p>Text: {(company.text_rank * 100).toFixed(1)}%</p>
                        )}
                        {company.similarity && (
                          <p>Similarity: {(company.similarity * 100).toFixed(1)}%</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                
                {companyResults.error && (
                  <p className="text-red-600">Error: {companyResults.error}</p>
                )}
              </div>
            )}
          </div>
          
          <button
            onClick={updateCompanyEmbeddings}
            disabled={loading}
            className="mt-4 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Update All Company Embeddings
          </button>
        </div>

        {/* Instructions */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="font-semibold text-yellow-900 mb-2">Setup Instructions:</h3>
          <ol className="list-decimal list-inside space-y-1 text-sm text-yellow-800">
            <li>Run the SQL scripts in Supabase SQL Editor:
              <code className="bg-yellow-100 px-1 rounded ml-2">setup_dual_embeddings.sql</code>
            </li>
            <li>Click "Update All Company Embeddings" to generate initial embeddings</li>
            <li>Test RL feedback embedding with sample corrections</li>
            <li>Test company search with queries like "AI fintech", "healthcare SaaS", etc.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}