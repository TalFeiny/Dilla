'use client';

import React, { useState, useEffect } from 'react';
import { ChevronRight, ExternalLink, FileText, Loader2, AlertTriangle, Lightbulb, Trophy, Shield, AlertCircle } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { cn } from '@/lib/utils';

interface AnalysisData {
  extracted_data?: {
    company_info?: {
      name?: string;
      sector?: string;
      stage?: string;
      achievements?: string[];
      challenges?: string[];
      summary?: string;
    };
    financial_metrics?: {
      arr?: number;
      revenue?: number;
      burn_rate?: number;
      runway_months?: number;
      cash_balance?: number;
      gross_margin?: number;
    };
    operational_metrics?: { headcount?: number; customer_count?: number };
    market_size?: { tam_usd?: number; sam_usd?: number };
    business_updates?: {
      achievements?: string[];
      challenges?: string[];
      risks?: string[];
      latest_update?: string;
    };
    red_flags?: string[];
    implications?: string[];
  };
  issue_analysis?: {
    overall_sentiment?: string;
    red_flags?: Array<{ description?: string } | string>;
    key_concerns?: string[];
    positive_indicators?: string[];
    recommendations?: string[];
  };
  document_metadata?: { filename?: string; status?: string };
  processing_required?: boolean;
  message?: string;
}

interface DocumentAnalysisCollapsibleProps {
  documentId: string | number;
  documentName: string;
  /** Compact inline style (e.g. in cell) vs full style (e.g. in sheet) */
  variant?: 'compact' | 'full';
  className?: string;
  children?: React.ReactNode;
  /** Optional: open full analysis page in new tab */
  onViewFull?: (documentId: string | number) => void;
}

function toStrArray(arr: unknown[]): string[] {
  return arr
    .filter((x): x is string => typeof x === 'string')
    .filter(Boolean);
}

function extractRedFlags(data: AnalysisData): string[] {
  const extracted = data.extracted_data?.red_flags ?? [];
  const issue = (data.issue_analysis?.red_flags ?? []).map((f) =>
    typeof f === 'string' ? f : (f as { description?: string }).description ?? ''
  );
  return [...toStrArray(extracted), ...issue].filter(Boolean);
}

function extractRisks(data: AnalysisData): string[] {
  const biz = data.extracted_data?.business_updates?.risks ?? [];
  const concerns = data.issue_analysis?.key_concerns ?? [];
  return [...toStrArray(biz), ...toStrArray(concerns)].filter(Boolean);
}

export function DocumentAnalysisCollapsible({
  documentId,
  documentName,
  variant = 'compact',
  className,
  children,
  onViewFull,
}: DocumentAnalysisCollapsibleProps) {
  const [open, setOpen] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !documentId) return;

    const fetchAnalysis = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/documents/${documentId}/analysis`, {
          headers: { 'Cache-Control': 'max-age=60' },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setAnalysis(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalysis();
  }, [open, documentId]);

  const displayName = documentName.length > 24 ? `${documentName.slice(0, 24)}…` : documentName;

  const redFlags = analysis ? extractRedFlags(analysis) : [];
  const implications = toStrArray(analysis?.extracted_data?.implications ?? []);
  const achievements = [
    ...toStrArray(analysis?.extracted_data?.company_info?.achievements ?? []),
    ...toStrArray(analysis?.extracted_data?.business_updates?.achievements ?? []),
  ].filter(Boolean);
  const challenges = [
    ...toStrArray(analysis?.extracted_data?.company_info?.challenges ?? []),
    ...toStrArray(analysis?.extracted_data?.business_updates?.challenges ?? []),
  ].filter(Boolean);
  const risks = analysis ? extractRisks(analysis) : [];

  const insightSections = [
    { key: 'redFlags', label: 'Red flags', items: redFlags, icon: AlertTriangle, className: 'border-amber-200 bg-amber-50 dark:bg-amber-900/10' },
    { key: 'implications', label: 'Implications', items: implications, icon: Lightbulb, className: 'border-blue-200 bg-blue-50 dark:bg-blue-900/10' },
    { key: 'achievements', label: 'Achievements', items: achievements, icon: Trophy, className: 'border-green-200 bg-green-50 dark:bg-green-900/10' },
    { key: 'challenges', label: 'Challenges', items: challenges, icon: Shield, className: 'border-slate-200 bg-slate-50 dark:bg-slate-900/10' },
    { key: 'risks', label: 'Risks', items: risks, icon: AlertCircle, className: 'border-red-200 bg-red-50 dark:bg-red-900/10' },
  ].filter((s) => s.items.length > 0);

  const hasAnyInsights = insightSections.length > 0;
  const fm = analysis?.extracted_data?.financial_metrics;
  const om = analysis?.extracted_data?.operational_metrics;
  const ci = analysis?.extracted_data?.company_info;
  const hasMetrics = !!(fm?.arr ?? fm?.runway_months ?? fm?.cash_balance ?? om?.headcount ?? ci?.name);

  const trigger = children ?? (
    <button
      type="button"
      onClick={(e) => e.stopPropagation()}
      className={cn(
        'text-primary hover:underline truncate max-w-[180px] text-left inline-flex items-center gap-1',
        variant === 'compact' && 'text-sm'
      )}
    >
      <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
      {displayName}
    </button>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild onClick={(e) => e.stopPropagation()}>
        {trigger}
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn(
          'p-0 overflow-hidden',
          variant === 'compact' ? 'w-[380px] max-h-[75vh]' : 'w-[520px] max-h-[85vh]'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/50">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            <span className="font-medium truncate">{documentName}</span>
          </div>
          <div className="flex items-center gap-1">
            {onViewFull && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onViewFull(documentId);
                }}
                className="text-muted-foreground hover:text-foreground p-1"
                title="View full analysis"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-muted-foreground hover:text-foreground p-1"
              aria-label="Close"
            >
              <ChevronRight className="h-4 w-4 rotate-180" />
            </button>
          </div>
        </div>
        <div className="overflow-y-auto p-3">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {error && (
            <p className="text-sm text-destructive py-4">{error}</p>
          )}
          {analysis?.processing_required && (
            <p className="text-sm text-amber-600 py-4">
              {analysis.message || 'Analysis in progress. Try again shortly.'}
            </p>
          )}
          {analysis && !loading && !error && !analysis.processing_required && (
            <div className="space-y-4 text-sm">
              {/* Key metrics */}
              {(ci?.name || fm || om) && (
                <div className="grid grid-cols-2 gap-2">
                  {ci?.name && (
                    <div>
                      <span className="text-muted-foreground">Company</span>
                      <p className="font-medium truncate">{ci.name}</p>
                    </div>
                  )}
                  {fm?.arr != null && (
                    <div>
                      <span className="text-muted-foreground">ARR</span>
                      <p className="font-medium">
                        ${(fm.arr / 1e6).toFixed(1)}M
                      </p>
                    </div>
                  )}
                  {fm?.runway_months != null && (
                    <div>
                      <span className="text-muted-foreground">Runway</span>
                      <p className="font-medium">{fm.runway_months} mo</p>
                    </div>
                  )}
                  {fm?.cash_balance != null && (
                    <div>
                      <span className="text-muted-foreground">Cash</span>
                      <p className="font-medium">
                        ${(fm.cash_balance / 1e6).toFixed(1)}M
                      </p>
                    </div>
                  )}
                  {(om?.headcount ?? 0) > 0 && (
                    <div>
                      <span className="text-muted-foreground">Headcount</span>
                      <p className="font-medium">{om?.headcount}</p>
                    </div>
                  )}
                  {analysis.issue_analysis?.overall_sentiment && (
                    <div>
                      <span className="text-muted-foreground">Sentiment</span>
                      <p className="font-medium capitalize">{analysis.issue_analysis.overall_sentiment}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Insights: red flags, implications, achievements, challenges, risks */}
              {hasAnyInsights && (
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Insights & suggestions</h4>
                  {insightSections.map(({ key, label, items, icon: Icon, className: sectionClass }) => (
                    <div key={key} className={cn('rounded-lg border p-3', sectionClass)}>
                      <h5 className="text-xs font-medium mb-2 flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5" />
                        {label}
                      </h5>
                      <ul className="text-sm space-y-1 list-disc list-inside">
                        {items.map((item, i) => (
                          <li key={i} className="text-muted-foreground">{item}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}

              {!hasMetrics && !hasAnyInsights && (
                <p className="text-muted-foreground">No structured data extracted yet.</p>
              )}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
