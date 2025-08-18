'use client';

import { useState, useEffect } from 'react';
import { Search, Sparkles, Database, Globe, Zap, Info, ChevronRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface QueryResult {
  query: string;
  structured: any;
  results: any[];
  metadata: {
    total: number;
    sources: {
      database: number;
      web: number;
      api: number;
    };
    sql?: string;
    webQuery?: string;
  };
  entities?: any[];
  plan?: any;
  confidence?: number;
}

export default function SemanticQueryInterface() {
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<QueryResult | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);

  // Example queries for inspiration
  const exampleQueries = [
    "Show me all SaaS companies with revenue over 100M",
    "Compare Stripe's growth rate to industry average",
    "Find AI startups with >50% YoY growth",
    "What's the average burn rate of Series B companies?",
    "Show unicorns founded after 2020",
    "List profitable fintech companies",
    "Find competitors to OpenAI with similar valuation",
    "Top 10 fastest growing companies by revenue",
    "Companies with CAC payback under 12 months",
    "Show me companies like Figma in design space"
  ];

  const processQuery = async () => {
    if (!query.trim()) return;
    
    setIsProcessing(true);
    setResults(null);
    
    try {
      const response = await fetch('/api/data/semantic-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      
      if (!response.ok) throw new Error('Query failed');
      
      const data = await response.json();
      setResults(data);
      
      // Add to history
      setQueryHistory(prev => [query, ...prev.filter(q => q !== query)].slice(0, 10));
      
    } catch (error) {
      console.error('Query error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const formatValue = (value: any, column: string) => {
    if (value === null || value === undefined) return '-';
    
    // Currency columns
    if (['revenue', 'valuation', 'funding', 'burn_rate'].includes(column)) {
      const num = typeof value === 'number' ? value : parseFloat(value);
      if (num >= 1e9) return `$${(num / 1e9).toFixed(1)}B`;
      if (num >= 1e6) return `$${(num / 1e6).toFixed(1)}M`;
      if (num >= 1e3) return `$${(num / 1e3).toFixed(0)}K`;
      return `$${num.toLocaleString()}`;
    }
    
    // Percentage columns
    if (['growth_rate', 'margin', 'churn_rate'].includes(column)) {
      const num = typeof value === 'number' ? value : parseFloat(value);
      return `${(num * 100).toFixed(1)}%`;
    }
    
    // Default
    return String(value);
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600';
    if (confidence >= 0.7) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="h-full flex flex-col">
      {/* Query Input */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && processQuery()}
              placeholder="Ask anything about companies... e.g., 'Show me profitable SaaS companies with >50% growth'"
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={processQuery}
            disabled={isProcessing || !query.trim()}
            className={cn(
              "px-4 py-2 rounded-lg font-medium flex items-center gap-2",
              isProcessing || !query.trim()
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700"
            )}
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Search
              </>
            )}
          </button>
        </div>
        
        {/* Example Queries */}
        <div className="mt-2 flex gap-2 flex-wrap">
          <span className="text-xs text-gray-500">Try:</span>
          {exampleQueries.slice(0, 3).map((example, i) => (
            <button
              key={i}
              onClick={() => setQuery(example)}
              className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-700"
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      {/* Query Understanding */}
      {results && (
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-700 mb-1">Understood as:</div>
              <div className="flex flex-wrap gap-2">
                {results.structured?.intent && (
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                    Intent: {results.structured.intent}
                  </span>
                )}
                {results.structured?.entities?.companies?.map((company: string) => (
                  <span key={company} className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                    Company: {company}
                  </span>
                ))}
                {results.structured?.entities?.metrics?.map((metric: string) => (
                  <span key={metric} className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs">
                    Metric: {metric}
                  </span>
                ))}
              </div>
            </div>
            
            {/* Data Sources */}
            <div className="flex gap-2">
              {results.metadata.sources.database > 0 && (
                <div className="flex items-center gap-1 text-xs text-gray-600">
                  <Database className="w-3 h-3" />
                  {results.metadata.sources.database}
                </div>
              )}
              {results.metadata.sources.web > 0 && (
                <div className="flex items-center gap-1 text-xs text-gray-600">
                  <Globe className="w-3 h-3" />
                  {results.metadata.sources.web}
                </div>
              )}
            </div>
          </div>
          
          {/* Show SQL/Query Details */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="mt-2 text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
          >
            <ChevronRight className={cn("w-3 h-3 transition-transform", showDetails && "rotate-90")} />
            {showDetails ? 'Hide' : 'Show'} query details
          </button>
          
          {showDetails && (
            <div className="mt-2 space-y-2">
              {results.metadata.sql && (
                <div className="p-2 bg-gray-900 text-gray-100 rounded text-xs font-mono">
                  SQL: {results.metadata.sql}
                </div>
              )}
              {results.metadata.webQuery && (
                <div className="p-2 bg-blue-900 text-blue-100 rounded text-xs">
                  Web Search: {results.metadata.webQuery}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Results Table */}
      {results && results.results.length > 0 && (
        <div className="flex-1 overflow-auto p-4">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                {Object.keys(results.results[0]).filter(k => !k.startsWith('_') && k !== 'sources').map(column => (
                  <th key={column} className="text-left py-2 px-3 text-sm font-medium text-gray-700">
                    {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </th>
                ))}
                <th className="text-left py-2 px-3 text-sm font-medium text-gray-700">Sources</th>
              </tr>
            </thead>
            <tbody>
              {results.results.map((row, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  {Object.entries(row).filter(([k]) => !k.startsWith('_') && k !== 'sources').map(([column, value]) => (
                    <td key={column} className="py-2 px-3 text-sm">
                      {formatValue(value, column)}
                    </td>
                  ))}
                  <td className="py-2 px-3">
                    {row.sources && (
                      <div className="flex gap-1">
                        {row.sources.map((source: any, j: number) => (
                          <span
                            key={j}
                            className={cn(
                              "px-1 py-0.5 rounded text-xs",
                              source.type === 'database' ? "bg-blue-100 text-blue-700" :
                              source.type === 'web' ? "bg-green-100 text-green-700" :
                              "bg-gray-100 text-gray-700"
                            )}
                            title={source.url || source.type}
                          >
                            {source.type === 'database' ? <Database className="w-3 h-3" /> :
                             source.type === 'web' ? <Globe className="w-3 h-3" /> :
                             <Zap className="w-3 h-3" />}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {/* No Results */}
      {results && results.results.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Info className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600">No results found</p>
            <p className="text-sm text-gray-500 mt-1">Try adjusting your query</p>
          </div>
        </div>
      )}
      
      {/* Initial State */}
      {!results && !isProcessing && (
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-2xl text-center">
            <Sparkles className="w-12 h-12 text-blue-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Semantic Company Search
            </h2>
            <p className="text-gray-600 mb-6">
              Ask questions in natural language and get instant answers from multiple data sources
            </p>
            
            {/* Query History */}
            {queryHistory.length > 0 && (
              <div className="text-left">
                <div className="text-sm font-medium text-gray-700 mb-2">Recent queries:</div>
                <div className="space-y-1">
                  {queryHistory.slice(0, 5).map((q, i) => (
                    <button
                      key={i}
                      onClick={() => setQuery(q)}
                      className="block w-full text-left px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded text-sm text-gray-700"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}