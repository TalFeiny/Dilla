'use client';

import { MCPOrchestrator } from '@/components/MCPOrchestrator';

export default function MCPPage() {
  return (
    <div className="min-h-screen bg-secondary py-8">
      <div className="container mx-auto px-4">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-foreground mb-4">
            MCP Tool Orchestration
          </h1>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Intelligent task decomposition and execution using Tavily and Firecrawl.
            Enter complex prompts and watch as they're broken down into actionable tasks
            and executed in parallel.
          </p>
        </div>
        
        <MCPOrchestrator 
          onResultsReceived={(results) => {
            console.log('MCP Results:', results);
          }}
        />
        
        <div className="mt-12 grid md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="font-semibold text-lg mb-2">🔍 Tavily Search</h3>
            <p className="text-muted-foreground text-sm">
              Advanced web search with semantic understanding. Finds relevant
              information, answers questions, and provides context.
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="font-semibold text-lg mb-2">🌐 Firecrawl Scraping</h3>
            <p className="text-muted-foreground text-sm">
              Deep website analysis and content extraction. Scrapes structured
              data, extracts key information, and processes documents.
            </p>
          </div>
          
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="font-semibold text-lg mb-2">🎯 Hybrid Mode</h3>
            <p className="text-muted-foreground text-sm">
              Combines both tools for comprehensive analysis. Search for information
              then scrape top results for deeper insights.
            </p>
          </div>
        </div>
        
        <div className="mt-8 max-w-6xl mx-auto">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="font-semibold text-lg mb-3">Example Prompts</h3>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span>Research the AI startup ecosystem and analyze Anthropic's competitive position</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span>Find and analyze Y Combinator's latest batch companies in the fintech sector</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span>Scrape OpenAI's website and extract their product offerings and pricing</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span>Research market size for enterprise AI and identify top 5 competitors</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}