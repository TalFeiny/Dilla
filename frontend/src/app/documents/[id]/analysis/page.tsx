'use client';

import React, { useState, useEffect, useMemo, Suspense } from 'react';
import { useParams } from 'next/navigation';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { formatCurrencyCompact, formatPercentage, formatNumber } from '@/utils/formatters';
import { Skeleton, SkeletonCard, SkeletonText } from '@/components/ui/skeleton';

// Loading skeleton for analysis data
const AnalysisSkeleton = () => (
  <div className="space-y-6">
    <div>
      <Skeleton className="h-8 w-1/3 mb-4" />
      <SkeletonText lines={3} className="mt-2" />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  </div>
);

interface AnalysisData {
  extracted_data: {
    market_size?: { tam_usd?: number; sam_usd?: number; som_usd?: number; tam_description?: string; methodology?: string };
    red_flags?: string[];
    implications?: string[];
    company_info?: {
      name?: string;
      sector?: string;
      stage?: string;
      achievements?: string[];
      challenges?: string[];
      competitors?: string[];
      industry_terms?: string[];
      partners_mentioned?: string[];
    };
    financial_metrics?: { arr?: number; burn_rate?: number; runway_months?: number; revenue?: number; growth_rate?: number };
    operational_metrics?: { headcount?: number; customer_count?: number; churn_rate?: number; cac?: number; new_hires?: number; ltv?: number };
    [key: string]: unknown;
  };
  issue_analysis: any;
  comparables_analysis: any;
  processing_summary: any;
  raw_text_preview: string;
  document_metadata: {
    filename: string;
    processed_at: string;
    document_type: string;
    status: string;
  };
  processing_required?: boolean;
  message?: string;
}

export default function AnalysisPage() {
  const params = useParams();
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [processingRequired, setProcessingRequired] = useState(false);

  // Handle hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  // Handle async params in Next.js 15
  useEffect(() => {
    if (!mounted) return;
    
    const getDocumentId = async () => {
      try {
        const resolvedParams = await params;
        const id = Array.isArray(resolvedParams.id) ? resolvedParams.id[0] : resolvedParams.id;
        setDocumentId(id || null);
      } catch (error) {
        console.error('Error resolving params:', error);
        setError('Invalid document ID');
      }
    };
    
    getDocumentId();
  }, [params, mounted]);

  // Fetch analysis data when documentId is available
  useEffect(() => {
    if (!documentId || !mounted) return;

    const fetchAnalysis = async () => {
      try {
        setLoading(true);
        setError(null);

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout

        const response = await fetch(`/api/documents/${documentId}/analysis`, {
          signal: controller.signal,
          headers: {
            'Cache-Control': 'max-age=300'
          }
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data: AnalysisData = await response.json();
        setAnalysisData(data);
        setProcessingRequired(data.processing_required || false);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setError('Request timed out - please try again');
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load analysis');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
  }, [documentId, mounted]);

  // Memoized tab navigation (text-only labels)
  const tabs = useMemo(() => [
    { id: 'overview', label: 'Overview' },
    { id: 'financial', label: 'Financial' },
    { id: 'business', label: 'Business Updates' },
    { id: 'issues', label: 'Issues' },
    { id: 'comparables', label: 'Comparables' },
    { id: 'raw_text', label: 'Raw Text' },
    { id: 'market', label: 'Market Mapper' },
  ], []);

  // Prevent hydration mismatch by showing loading until mounted
  if (!mounted || loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="mb-6">
          <Skeleton className="h-8 w-1/3 mb-2" />
          <Skeleton className="h-4 w-1/2" />
        </div>
        <AnalysisSkeleton />
        <div className="mt-4 text-center">
          <div className="inline-flex items-center px-4 py-2 bg-muted/50 text-muted-foreground rounded-lg border border-border">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-muted-foreground mr-2"></div>
            Loading analysis data...
          </div>
        </div>
      </div>
    );
  }

  // Show processing required message
  if (processingRequired) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">
            {analysisData?.document_metadata?.filename || 'Document Analysis'}
          </h1>
          <p className="text-gray-600">
            Analysis • {analysisData?.document_metadata?.document_type || 'Unknown'}
          </p>
        </div>
        
        <div className="bg-muted/50 border border-border rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-muted-foreground" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-foreground">Analysis in Progress</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {analysisData?.message || 'Document analysis is still being processed. Please wait for the analysis to complete.'}
              </p>
              <div className="mt-3">
                <button
                  onClick={() => window.location.reload()}
                  className="inline-flex items-center px-3 py-2 border border-border text-sm leading-4 font-medium rounded-md text-foreground bg-muted hover:bg-muted/80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-muted-foreground/30"
                >
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Check Again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-muted/50 border border-border rounded-lg p-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-destructive" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-foreground">Error loading analysis</h3>
              <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              <div className="mt-3 space-x-2">
                <button
                  onClick={() => window.location.reload()}
                  className="inline-flex items-center px-3 py-2 border border-border text-sm leading-4 font-medium rounded-md text-destructive bg-muted hover:bg-muted/80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-destructive/30"
                >
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Try again
                </button>
                <button
                  onClick={() => window.location.reload()}
                  className="inline-flex items-center px-3 py-2 border border-border text-sm leading-4 font-medium rounded-md text-foreground bg-muted/30 hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-muted-foreground/30"
                >
                  Reload page
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!analysisData) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="text-center">
          <p className="text-muted-foreground">No analysis data available</p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">
                {analysisData?.document_metadata?.filename || 'Document Analysis'}
              </h1>
              <p className="text-muted-foreground">
                Analysis • {analysisData?.document_metadata?.document_type || 'Unknown'} •
                {mounted && analysisData?.document_metadata?.processed_at ? new Date(analysisData.document_metadata.processed_at).toLocaleDateString() : 'Unknown date'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={async () => {
                  try {
                    const slides = [
                      {
                        title: 'Executive Summary',
                        content: {
                          company: analysisData?.extracted_data?.company_info?.name || 'Unknown',
                          sector: analysisData?.extracted_data?.company_info?.sector,
                          stage: analysisData?.extracted_data?.company_info?.stage,
                          financial_metrics: analysisData?.extracted_data?.financial_metrics,
                          operational_metrics: analysisData?.extracted_data?.operational_metrics,
                        },
                      },
                      {
                        title: 'Issue Analysis',
                        content: {
                          red_flags: analysisData?.issue_analysis?.red_flags,
                          key_risks: analysisData?.issue_analysis?.key_risks,
                          sentiment: analysisData?.issue_analysis?.overall_sentiment,
                        },
                      },
                      {
                        title: 'Market Analysis',
                        content: {
                          market_size: analysisData?.extracted_data?.market_size,
                          competitors: analysisData?.extracted_data?.company_info?.competitors,
                        },
                      },
                      {
                        title: 'Comparables',
                        content: analysisData?.comparables_analysis,
                      },
                    ];
                    const res = await fetch('/api/export/deck', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        slides,
                        outputFormat: 'memo',
                        documentId,
                        companyName: analysisData?.extracted_data?.company_info?.name || 'Analysis',
                      }),
                    });
                    if (res.ok) {
                      const blob = await res.blob();
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `${analysisData?.extracted_data?.company_info?.name || 'analysis'}-memo.pdf`;
                      a.click();
                      URL.revokeObjectURL(url);
                    }
                  } catch (err) {
                    console.error('Export failed:', err);
                  }
                }}
                className="inline-flex items-center px-3 py-2 border border-border text-sm font-medium rounded-md text-foreground bg-muted hover:bg-muted/80"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export PDF
              </button>
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-muted/50 text-muted-foreground border border-border">
                {analysisData?.document_metadata?.status || 'unknown'}
              </span>
            </div>
          </div>
        </div>

      {/* Tab Navigation */}
      <div className="mb-6">
        <nav className="flex space-x-8 border-b border-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <Suspense fallback={<AnalysisSkeleton />}>
        <div className="space-y-6">
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Company Overview */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Company Overview</h3>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Company:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.name || 'Unknown'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Sector:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.sector || 'Unknown'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Stage:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.stage || 'Unknown'}
                    </p>
                  </div>
                  {analysisData?.extracted_data?.company_info?.achievements?.length > 0 && (
                    <div>
                      <span className="text-sm text-muted-foreground">Achievements:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.company_info.achievements.length}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Financial Metrics */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Financial Metrics</h3>
                <div className="space-y-3">
                  {analysisData?.extracted_data?.financial_metrics?.arr && (
                    <div>
                      <span className="text-sm text-muted-foreground">ARR:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.financial_metrics.arr)}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.burn_rate && (
                    <div>
                      <span className="text-sm text-muted-foreground">Monthly Burn:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {formatCurrencyCompact(Math.abs(analysisData.extracted_data.financial_metrics.burn_rate))}/mo
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.runway_months && (
                    <div>
                      <span className="text-sm text-muted-foreground">Runway:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {formatNumber(analysisData.extracted_data.financial_metrics.runway_months)} months
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.revenue && (
                    <div>
                      <span className="text-sm text-muted-foreground">Revenue:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.financial_metrics.revenue)}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Issues Summary */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Issues Summary</h3>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Red Flags:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.issue_analysis?.red_flags?.length || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Key Concerns:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.issue_analysis?.key_risks?.length || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Sentiment:</span>
                    <p className="text-lg font-semibold text-foreground capitalize">
                      {analysisData?.issue_analysis?.overall_sentiment || 'neutral'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Confidence:</span>
                    <p className="text-lg font-semibold text-foreground capitalize">
                      {analysisData?.issue_analysis?.confidence_level || 'medium'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Comparables Summary */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Comparables</h3>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Companies Found:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.comparables_analysis?.companies_found || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">M&A Transactions:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.comparables_analysis?.ma_transactions?.length || 0}
                    </p>
                  </div>
                  {analysisData?.comparables_analysis?.valuation_multiples?.ev_revenue_multiples && (
                    <div>
                      <span className="text-sm text-muted-foreground">Avg EV/Revenue:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.comparables_analysis.valuation_multiples.ev_revenue_multiples.mean?.toFixed(1)}x
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Operational Metrics Summary */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Operational Metrics</h3>
                <div className="space-y-3">
                  {analysisData?.extracted_data?.operational_metrics?.headcount && (
                    <div>
                      <span className="text-sm text-muted-foreground">Headcount:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.operational_metrics.headcount}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.customer_count && (
                    <div>
                      <span className="text-sm text-muted-foreground">Customers:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.operational_metrics.customer_count}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.churn_rate && (
                    <div>
                      <span className="text-sm text-muted-foreground">Churn Rate:</span>
                      <p className="text-lg font-semibold text-foreground">
                        {(analysisData.extracted_data.operational_metrics.churn_rate * 100).toFixed(1)}%
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.cac && (
                    <div>
                      <span className="text-sm text-muted-foreground">CAC:</span>
                      <p className="text-lg font-semibold text-foreground">
                        ${analysisData.extracted_data.operational_metrics.cac.toLocaleString()}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Business Updates Summary */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Business Updates</h3>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Achievements:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.achievements?.length || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Challenges:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.challenges?.length || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Competitors:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.competitors?.length || 0}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Industry Terms:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.extracted_data?.company_info?.industry_terms?.length || 0}
                    </p>
                  </div>
                </div>
              </div>

              {/* Processing Summary */}
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Processing Info</h3>
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-muted-foreground">Document Type:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.document_metadata?.document_type || 'Unknown'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Status:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.document_metadata?.status || 'Unknown'}
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Text Length:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.processing_summary?.text_length?.toLocaleString() || 'Unknown'} chars
                    </p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Processing Time:</span>
                    <p className="text-lg font-semibold text-foreground">
                      {analysisData?.processing_summary?.processing_time_seconds || 0}s
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'financial' && (
            <div className="space-y-6">
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Financial Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {analysisData?.extracted_data?.financial_metrics?.arr && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Annual Recurring Revenue (ARR)</span>
                      <p className="text-2xl font-bold text-foreground">
                        ${(analysisData.extracted_data.financial_metrics.arr / 1000000).toFixed(1)}M
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.burn_rate && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Monthly Burn Rate</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(Math.abs(analysisData.extracted_data.financial_metrics.burn_rate))}/mo
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.runway_months && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Runway (Months)</span>
                      <p className="text-2xl font-bold text-foreground">
                        {analysisData.extracted_data.financial_metrics.runway_months}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.financial_metrics?.growth_rate && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Growth Rate</span>
                      <p className="text-2xl font-bold text-foreground">
                        {(analysisData.extracted_data.financial_metrics.growth_rate * 100).toFixed(1)}%
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Operational Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {analysisData?.extracted_data?.operational_metrics?.headcount && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Headcount</span>
                      <p className="text-2xl font-bold text-foreground">
                        {analysisData.extracted_data.operational_metrics.headcount}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.new_hires && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">New Hires</span>
                      <p className="text-2xl font-bold text-foreground">
                        {analysisData.extracted_data.operational_metrics.new_hires}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.customer_count && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Customer Count</span>
                      <p className="text-2xl font-bold text-foreground">
                        {analysisData.extracted_data.operational_metrics.customer_count}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.churn_rate && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Churn Rate</span>
                      <p className="text-2xl font-bold text-red-600">
                        {formatPercentage(analysisData.extracted_data.operational_metrics.churn_rate)}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.cac && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Customer Acquisition Cost</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.operational_metrics.cac)}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.operational_metrics?.ltv && (
                    <div className="rounded-lg p-4 bg-muted/30 border border-border">
                      <span className="text-sm text-muted-foreground">Lifetime Value</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.operational_metrics.ltv)}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Company Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {analysisData?.extracted_data?.company_info?.name && (
                    <div>
                      <span className="text-sm text-muted-foreground">Company Name</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.company_info.name}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.company_info?.sector && (
                    <div>
                      <span className="text-sm text-muted-foreground">Sector</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.company_info.sector}
                      </p>
                    </div>
                  )}
                  {analysisData?.extracted_data?.company_info?.stage && (
                    <div>
                      <span className="text-sm text-muted-foreground">Stage</span>
                      <p className="text-lg font-semibold text-foreground">
                        {analysisData.extracted_data.company_info.stage}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'business' && (
            <div className="space-y-6">
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Business Updates</h3>
                
                {analysisData?.extracted_data?.company_info?.achievements && 
                 analysisData.extracted_data.company_info.achievements.length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-md font-semibold text-foreground mb-3">Achievements</h4>
                    <div className="space-y-2">
                      {analysisData.extracted_data.company_info.achievements.map((achievement: string, index: number) => (
                        <div key={index} className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/30">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm text-foreground">{achievement}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.extracted_data?.company_info?.challenges && 
                 analysisData.extracted_data.company_info.challenges.length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-md font-semibold text-foreground mb-3">Challenges</h4>
                    <div className="space-y-2">
                      {analysisData.extracted_data.company_info.challenges.map((challenge: string, index: number) => (
                        <div key={index} className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/30">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-orange-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm text-foreground">{challenge}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.extracted_data?.company_info?.competitors && 
                 analysisData.extracted_data.company_info.competitors.length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-md font-semibold text-foreground mb-3">Competitors Mentioned</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.extracted_data.company_info.competitors.map((competitor: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-red-100 text-foreground rounded-full text-sm">
                          {competitor}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.extracted_data?.company_info?.industry_terms && 
                 analysisData.extracted_data.company_info.industry_terms.length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-md font-semibold text-foreground mb-3">Industry Terms</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.extracted_data.company_info.industry_terms.map((term: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-blue-100 text-foreground rounded-full text-sm">
                          {term}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.extracted_data?.company_info?.partners_mentioned && 
                 analysisData.extracted_data.company_info.partners_mentioned.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Partners Mentioned</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.extracted_data.company_info.partners_mentioned.map((partner: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-green-100 text-foreground rounded-full text-sm">
                          {partner}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'issues' && (
            <div className="space-y-6">
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Issue Analysis</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                  <div className="rounded-lg p-4 bg-muted/30 border border-border">
                    <span className="text-sm text-muted-foreground">Overall Sentiment</span>
                    <p className="text-2xl font-bold capitalize">
                      {analysisData?.issue_analysis?.overall_sentiment || 'neutral'}
                    </p>
                  </div>
                  <div className="rounded-lg p-4 bg-muted/30 border border-border">
                    <span className="text-sm text-muted-foreground">Confidence Level</span>
                    <p className="text-2xl font-bold capitalize">
                      {analysisData?.issue_analysis?.confidence_level || 'medium'}
                    </p>
                  </div>
                  <div className="rounded-lg p-4 bg-muted/30 border border-border">
                    <span className="text-sm text-muted-foreground">Red Flags</span>
                    <p className="text-2xl font-bold text-red-600">
                      {analysisData?.issue_analysis?.red_flags?.length || 0}
                    </p>
                  </div>
                </div>

                {analysisData?.issue_analysis?.red_flags && analysisData.issue_analysis.red_flags.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Red Flags</h4>
                    <div className="space-y-2">
                      {analysisData.issue_analysis.red_flags.map((flag: any, index: number) => (
                        <div key={index} className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/30">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm text-foreground">
                              {typeof flag === 'string' ? flag : flag.description || 'Unknown issue'}
                            </p>
                            {flag.severity && (
                              <p className="text-xs text-red-600 mt-1">
                                Severity: {flag.severity}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.issue_analysis?.key_risks && analysisData.issue_analysis.key_risks.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Key Concerns</h4>
                    <div className="space-y-2">
                      {analysisData.issue_analysis.key_risks.map((risk: string, index: number) => (
                        <div key={index} className="flex items-start space-x-3 p-3 rounded-lg border border-border bg-muted/30">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-orange-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <div>
                            <p className="text-sm text-foreground">{risk}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.issue_analysis?.missing_metrics && analysisData.issue_analysis.missing_metrics.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Missing Metrics</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.issue_analysis.missing_metrics.map((metric: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm">
                          {metric}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.issue_analysis?.business_concerns && analysisData.issue_analysis.business_concerns.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Business Concerns</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.issue_analysis.business_concerns.map((concern: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-red-100 text-foreground rounded-full text-sm">
                          {concern}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.issue_analysis?.language_concerns && analysisData.issue_analysis.language_concerns.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Language Concerns</h4>
                    <div className="flex flex-wrap gap-2">
                      {analysisData.issue_analysis.language_concerns.map((concern: string, index: number) => (
                        <span key={index} className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                          {concern}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {analysisData?.extracted_data?.implications && analysisData.extracted_data.implications.length > 0 && (
                  <div>
                    <h4 className="text-md font-semibold text-foreground mb-3">Implications (reading between the lines)</h4>
                    <div className="space-y-2">
                      {analysisData.extracted_data.implications.map((impl: string, index: number) => (
                        <div key={index} className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                          <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                            </svg>
                          </div>
                          <p className="text-sm text-foreground">{impl}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'comparables' && (
            <div className="space-y-6">
              <div className="rounded-lg p-6 border border-border bg-muted/30">
                <h3 className="text-lg font-semibold text-foreground mb-4">Comparable Companies</h3>
                <div className="mb-4">
                  <span className="text-sm text-muted-foreground">Total Found:</span>
                  <span className="ml-2 text-lg font-semibold text-foreground">
                    {analysisData?.comparables_analysis?.companies_found || 0}
                  </span>
                </div>

                {analysisData?.comparables_analysis?.comparable_companies && 
                 analysisData.comparables_analysis.comparable_companies.length > 0 ? (
                  <div className="space-y-4">
                    {analysisData.comparables_analysis.comparable_companies.map((company: any, index: number) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">{company.name}</h4>
                            {company.ticker && (
                              <p className="text-sm text-muted-foreground">Ticker: {company.ticker}</p>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="text-sm text-muted-foreground">{company.sector}</span>
                            {company.relevance_score && (
                              <p className="text-xs text-foreground">Relevance: {(company.relevance_score * 100).toFixed(1)}%</p>
                            )}
                          </div>
                        </div>
                        {company.description && (
                          <p className="text-sm text-gray-600 mb-3">{company.description}</p>
                        )}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <span className="text-sm text-muted-foreground">Valuation</span>
                            <p className="text-lg font-semibold text-foreground">{company.valuation}</p>
                          </div>
                          <div>
                            <span className="text-sm text-muted-foreground">Revenue</span>
                            <p className="text-lg font-semibold text-foreground">{company.revenue}</p>
                          </div>
                          <div>
                            <span className="text-sm text-muted-foreground">Growth Rate</span>
                            <p className="text-lg font-semibold text-foreground">{company.growth_rate}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No comparable companies found.</p>
                )}
              </div>

              {analysisData?.comparables_analysis?.valuation_multiples && 
               Object.keys(analysisData.comparables_analysis.valuation_multiples).length > 0 && (
                <div className="rounded-lg p-6 border border-border bg-muted/30">
                  <h3 className="text-lg font-semibold text-foreground mb-4">Valuation Multiples</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {analysisData.comparables_analysis.valuation_multiples.ev_revenue_multiples && (
                      <>
                        <div className="bg-blue-50 rounded-lg p-4">
                          <span className="text-sm text-muted-foreground">EV/Revenue Median</span>
                          <p className="text-2xl font-bold text-foreground">
                            {analysisData.comparables_analysis.valuation_multiples.ev_revenue_multiples.median?.toFixed(1)}x
                          </p>
                        </div>
                        <div className="bg-green-50 rounded-lg p-4">
                          <span className="text-sm text-muted-foreground">EV/Revenue Mean</span>
                          <p className="text-2xl font-bold text-foreground">
                            {analysisData.comparables_analysis.valuation_multiples.ev_revenue_multiples.mean?.toFixed(1)}x
                          </p>
                        </div>
                        <div className="bg-purple-50 rounded-lg p-4">
                          <span className="text-sm text-muted-foreground">Companies Analyzed</span>
                          <p className="text-2xl font-bold text-foreground">
                            {analysisData.comparables_analysis.valuation_multiples.ev_revenue_multiples.count || 0}
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {analysisData?.comparables_analysis?.ma_transactions && 
               analysisData.comparables_analysis.ma_transactions.length > 0 && (
                <div className="rounded-lg p-6 border border-border bg-muted/30">
                  <h3 className="text-lg font-semibold text-foreground mb-4">M&A Transactions</h3>
                  <div className="space-y-4">
                    {analysisData.comparables_analysis.ma_transactions.map((deal: any, index: number) => (
                      <div key={index} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <h4 className="text-lg font-semibold text-foreground">{deal.target_company}</h4>
                            {deal.relevance_score && (
                              <p className="text-xs text-foreground">Relevance: {(deal.relevance_score * 100).toFixed(1)}%</p>
                            )}
                          </div>
                          <span className="text-sm text-muted-foreground">{deal.deal_date}</span>
                        </div>
                        {deal.description && (
                          <p className="text-sm text-gray-600 mb-3">{deal.description}</p>
                        )}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <span className="text-sm text-muted-foreground">Acquirer</span>
                            <p className="text-lg font-semibold text-foreground">{deal.acquirer}</p>
                          </div>
                          <div>
                            <span className="text-sm text-muted-foreground">Deal Value</span>
                            <p className="text-lg font-semibold text-foreground">{deal.deal_value}</p>
                          </div>
                          <div>
                            <span className="text-sm text-muted-foreground">Industry</span>
                            <p className="text-lg font-semibold text-foreground">{deal.industry}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'raw_text' && (
            <div className="rounded-lg p-6 border border-border bg-muted/30">
              <h3 className="text-lg font-semibold text-foreground mb-4">Raw Document Text</h3>
              <div className="rounded-lg p-4 bg-muted/30 border border-border max-h-96 overflow-y-auto">
                <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono leading-relaxed">
                  {analysisData?.raw_text_preview || 'No raw text available'}
                </pre>
              </div>
              {analysisData?.raw_text_preview && (
                <div className="mt-2 text-sm text-muted-foreground">
                  Text length: {analysisData.raw_text_preview.length.toLocaleString()} characters
                </div>
              )}
            </div>
          )}

          {activeTab === 'market' && (
            <div className="rounded-lg p-6 border border-border bg-muted/30">
              <h3 className="text-lg font-semibold text-foreground mb-4">Market Size (TAM/SAM/SOM)</h3>
              {analysisData?.extracted_data?.market_size && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {analysisData.extracted_data.market_size.tam_usd && (
                    <div className="bg-blue-50 rounded-lg p-4">
                      <span className="text-sm text-muted-foreground">TAM (Total Addressable Market)</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.market_size.tam_usd)}
                      </p>
                      {analysisData.extracted_data.market_size.tam_description && (
                        <p className="text-sm text-gray-600 mt-1">{analysisData.extracted_data.market_size.tam_description}</p>
                      )}
                    </div>
                  )}
                  {analysisData.extracted_data.market_size.sam_usd && (
                    <div className="bg-green-50 rounded-lg p-4">
                      <span className="text-sm text-muted-foreground">SAM (Serviceable Addressable Market)</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.market_size.sam_usd)}
                      </p>
                    </div>
                  )}
                  {analysisData.extracted_data.market_size.som_usd && (
                    <div className="bg-purple-50 rounded-lg p-4">
                      <span className="text-sm text-muted-foreground">SOM (Serviceable Obtainable Market)</span>
                      <p className="text-2xl font-bold text-foreground">
                        {formatCurrencyCompact(analysisData.extracted_data.market_size.som_usd)}
                      </p>
                    </div>
                  )}
                </div>
              )}
              {analysisData?.extracted_data?.market_size?.methodology && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium text-gray-700">Methodology</span>
                  <p className="text-sm text-gray-600 mt-1">{analysisData.extracted_data.market_size.methodology}</p>
                </div>
              )}
              {(!analysisData?.extracted_data?.market_size || (!analysisData.extracted_data.market_size.tam_usd && !analysisData.extracted_data.market_size.sam_usd && !analysisData.extracted_data.market_size.som_usd)) && (
                <p className="text-gray-600">
                  No market size (TAM/SAM/SOM) data extracted from this document. Upload memos or board decks for market size extraction.
                </p>
              )}
            </div>
          )}
        </div>
      </Suspense>
      </div>
    </ErrorBoundary>
  );
} 