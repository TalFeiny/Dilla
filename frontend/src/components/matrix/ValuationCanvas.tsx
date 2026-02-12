'use client';

import React, { useState, useCallback } from 'react';
import { FluidResultBox, ResultType } from './FluidResultBox';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Sparkles, Loader2 } from 'lucide-react';
import { MatrixData } from './UnifiedMatrix';

interface ValuationMethod {
  value: string;
  label: string;
  description: string;
  category: 'Early Stage' | 'Growth' | 'Late Stage' | 'General';
}

const VALUATION_METHODS: ValuationMethod[] = [
  {
    value: 'auto',
    label: 'AUTO',
    description: 'Auto-select based on company stage',
    category: 'General',
  },
  {
    value: 'pwerm',
    label: 'PWERM',
    description: 'Probability Weighted Expected Return Method',
    category: 'Early Stage',
  },
  {
    value: 'dcf',
    label: 'DCF',
    description: 'Discounted Cash Flow analysis',
    category: 'Late Stage',
  },
  {
    value: 'opm',
    label: 'OPM',
    description: 'Option Pricing Model',
    category: 'Late Stage',
  },
  {
    value: 'waterfall',
    label: 'WATERFALL',
    description: 'Liquidation waterfall analysis',
    category: 'Growth',
  },
  {
    value: 'recent_transaction',
    label: 'RECENT TRANSACTION',
    description: 'Recent transaction method',
    category: 'General',
  },
  {
    value: 'cost_method',
    label: 'COST METHOD',
    description: 'Cost-based valuation',
    category: 'General',
  },
  {
    value: 'milestone',
    label: 'MILESTONE',
    description: 'Milestone-based valuation',
    category: 'Early Stage',
  },
];

interface ParsedResult {
  type: ResultType;
  data: any;
}

interface ValuationCanvasProps {
  onQuery?: (query: string, method?: string) => Promise<MatrixData | any>;
  initialQuery?: string;
  onMatrixDataChange?: (data: MatrixData | null) => void;
}

export function ValuationCanvas({ onQuery, initialQuery = '', onMatrixDataChange }: ValuationCanvasProps) {
  const [query, setQuery] = useState(initialQuery);
  const [valuationMethod, setValuationMethod] = useState<string>('auto');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<ParsedResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const parseResults = useCallback((data: any): ParsedResult[] => {
    const parsed: ParsedResult[] = [];

    // Check if it's a matrix
    if (data.columns && data.rows) {
      parsed.push({
        type: 'matrix',
        data: {
          ...data,
          title: 'Financial Matrix',
        },
      });
    }

    // Check for companies
    if (Array.isArray(data.companies)) {
      data.companies.forEach((company: any) => {
        parsed.push({
          type: 'company',
          data: company,
        });
      });
    }

    // Check for metrics
    if (data.metrics) {
      Object.entries(data.metrics).forEach(([key, value]: [string, any]) => {
        parsed.push({
          type: 'metric',
          data: {
            label: key,
            value: typeof value === 'number' ? value.toLocaleString() : value,
            unit: data.metricUnits?.[key],
          },
        });
      });
    }

    // Check for documents
    if (Array.isArray(data.documents)) {
      data.documents.forEach((doc: any) => {
        parsed.push({
          type: 'document',
          data: doc,
        });
      });
    }

    // Check for text/analysis
    if (data.analysis || data.text || data.summary) {
      parsed.push({
        type: 'text',
        data: {
          title: 'Analysis',
          content: data.analysis || data.text || data.summary,
          citations: data.citations,
        },
      });
    }

    // If no structured data found, treat as text
    if (parsed.length === 0 && data) {
      parsed.push({
        type: 'text',
        data: {
          title: 'Result',
          content: typeof data === 'string' ? data : JSON.stringify(data, null, 2),
        },
      });
    }

    return parsed;
  }, []);

  const handleQuery = async () => {
    if (!query.trim() || !onQuery) return;

    setIsLoading(true);
    setError(null);
    setResults([]);

    try {
      const result = await onQuery(query, valuationMethod);
      const parsed = parseResults(result);
      setResults(parsed);
      
      // If result contains matrix data, notify parent
      if (result.columns && result.rows) {
        const matrixData: MatrixData = {
          columns: result.columns,
          rows: result.rows,
          formulas: result.formulas || {},
          metadata: {
            ...result.metadata,
            query,
            lastUpdated: new Date().toISOString(),
          },
        };
        onMatrixDataChange?.(matrixData);
      } else {
        onMatrixDataChange?.(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute query');
      console.error('Query error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const groupedMethods = VALUATION_METHODS.reduce((acc, method) => {
    if (!acc[method.category]) {
      acc[method.category] = [];
    }
    acc[method.category].push(method);
    return acc;
  }, {} as Record<string, ValuationMethod[]>);

  return (
    <div className="min-h-screen w-full canvas-container">
      {/* Wide Input Bar */}
      <div className="wide-input-bar">
        <div className="flex items-center gap-4 w-full">
          <div className="flex-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleQuery();
                }
              }}
              placeholder="Enter your valuation query... (e.g., 'Value Stripe using DCF' or 'Compare @Stripe @Square @Adyen')"
              className="w-full h-14 text-base px-6"
            />
          </div>
          
          <div className="w-80">
            <Select value={valuationMethod} onValueChange={setValuationMethod}>
              <SelectTrigger className="h-14 text-base">
                <SelectValue placeholder="Select valuation method" />
              </SelectTrigger>
              <SelectContent className="max-h-[400px]">
                {Object.entries(groupedMethods).map(([category, methods]) => (
                  <div key={category}>
                    <div className="px-2 py-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      {category}
                    </div>
                    {methods.map((method) => (
                      <SelectItem key={method.value} value={method.value}>
                        <div className="flex flex-col">
                          <span className="font-medium">{method.label}</span>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {method.description}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </div>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={handleQuery}
            disabled={isLoading || !query.trim()}
            className="h-14 px-8 text-base"
            size="lg"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 mr-2" />
                Query
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Results Canvas */}
      <div className="results-canvas">
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {isLoading && results.length === 0 && (
          <div className="loading-skeleton">
            <div className="skeleton-box" />
            <div className="skeleton-box" />
            <div className="skeleton-box" />
          </div>
        )}

        {results.length > 0 && (
          <div className="results-grid">
            {results.map((result, index) => (
              <FluidResultBox
                key={index}
                type={result.type}
                data={result.data}
                index={index}
              />
            ))}
          </div>
        )}

        {!isLoading && results.length === 0 && !error && (
          <div className="empty-state">
            <p className="text-gray-500 dark:text-gray-400 text-lg">
              Enter a query above to generate valuation results
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
