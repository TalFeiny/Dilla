'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Send, Sparkles, History, FileText } from 'lucide-react';

interface NaturalLanguageQueryProps {
  onQuery: (query: string) => Promise<void>;
  isLoading?: boolean;
}

const QUERY_TEMPLATES = [
  "What if Company X gets seed extension, then growth slows to 20%, then distressed acquisition?",
  "Show me revenue projection for the next 5 years with 30% growth",
  "Compare valuation scenarios: base case, optimistic, and downside",
  "What's the impact of a 15% growth rate change on portfolio NAV?",
  "Run sensitivity analysis on exit multiples",
];

export function NaturalLanguageQuery({ onQuery, isLoading = false }: NaturalLanguageQueryProps) {
  const [query, setQuery] = useState('');
  const [history, setHistory] = useState<string[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    const queryText = query.trim();
    setQuery('');
    setHistory(prev => [queryText, ...prev].slice(0, 10)); // Keep last 10
    await onQuery(queryText);
  };

  const handleTemplateClick = (template: string) => {
    setQuery(template);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="w-5 h-5" />
          Natural Language FP&A Query
        </CardTitle>
        <CardDescription>
          Ask questions about scenarios, forecasts, valuations, and more
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., What if Company X gets seed extension, then growth slows to 20%, then distressed acquisition?"
            className="min-h-[100px]"
            disabled={isLoading}
          />
          
          <div className="flex items-center justify-between">
            <Button
              type="submit"
              disabled={!query.trim() || isLoading}
              className="flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Processing...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Run Query
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Query Templates */}
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-gray-700">
            <FileText className="w-4 h-4" />
            Example Queries
          </div>
          <div className="space-y-2">
            {QUERY_TEMPLATES.map((template, idx) => (
              <button
                key={idx}
                onClick={() => handleTemplateClick(template)}
                className="w-full text-left px-3 py-2 text-sm bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors"
              >
                {template}
              </button>
            ))}
          </div>
        </div>

        {/* Query History */}
        {history.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center gap-2 mb-3 text-sm font-medium text-gray-700">
              <History className="w-4 h-4" />
              Recent Queries
            </div>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {history.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(item)}
                  className="w-full text-left px-3 py-2 text-xs bg-gray-50 hover:bg-gray-100 rounded border border-gray-200 transition-colors"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
