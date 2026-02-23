'use client';

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown } from 'lucide-react';

export interface CompanyAnalysisData {
  company?: string;
  name?: string;
  valuation?: number;
  revenue?: number;
  arr?: number;
  growth_rate?: number;
  gross_margin?: number;
  business_model?: string;
  product_description?: string;
  fund_fit_score?: number;
  funding?: {
    total_raised?: number;
    last_round_type?: string;
    last_round_amount?: number;
    last_round_date?: string;
  };
  cap_table?: {
    investors?: Array<{ name: string; ownership: number; round?: string }>;
    liquidation_stack?: Array<{ investor: string; amount: number; multiple: number }>;
  };
  valuation_methods?: {
    pwerm?: number;
    dcf?: number;
    comparables?: number;
  };
}

function formatCurrency(value: number | undefined | null): string {
  if (value == null) return '--';
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

function formatPercent(value: number | undefined | null): string {
  if (value == null) return '--';
  const pct = Math.abs(value) <= 1 ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

interface MetricCellProps {
  label: string;
  value: string;
  sub?: string;
}

function MetricCell({ label, value, sub }: MetricCellProps) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide truncate">{label}</span>
      <span className="text-sm font-semibold tabular-nums truncate">{value}</span>
      {sub && <span className="text-[10px] text-muted-foreground truncate">{sub}</span>}
    </div>
  );
}

export function CompanyAnalysisCard({ data }: { data: CompanyAnalysisData }) {
  const companyName = data.company || data.name || 'Unknown';
  const stage = data.funding?.last_round_type;
  const growthPositive = data.growth_rate != null && data.growth_rate > 0;

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30 p-3 space-y-2.5">
      {/* Header */}
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-semibold text-sm truncate">{companyName}</span>
        {stage && (
          <Badge variant="outline" className="text-[10px] h-4 px-1.5 shrink-0">{stage}</Badge>
        )}
        {data.fund_fit_score != null && (
          <Badge
            variant="secondary"
            className={`text-[10px] h-4 px-1.5 shrink-0 ${
              data.fund_fit_score >= 70 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' :
              data.fund_fit_score >= 40 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' :
              'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            }`}
          >
            Fit: {data.fund_fit_score}
          </Badge>
        )}
        {data.growth_rate != null && (
          <span className={`flex items-center gap-0.5 text-[10px] font-medium shrink-0 ${growthPositive ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
            {growthPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {formatPercent(data.growth_rate)}
          </span>
        )}
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-3 gap-x-4 gap-y-2">
        <MetricCell label="Valuation" value={formatCurrency(data.valuation)} />
        <MetricCell
          label={data.arr ? 'ARR' : 'Revenue'}
          value={formatCurrency(data.arr || data.revenue)}
        />
        <MetricCell label="Gross Margin" value={formatPercent(data.gross_margin)} />
        <MetricCell
          label="Total Raised"
          value={formatCurrency(data.funding?.total_raised)}
        />
        <MetricCell
          label="Last Round"
          value={data.funding?.last_round_amount ? formatCurrency(data.funding.last_round_amount) : '--'}
          sub={data.funding?.last_round_date || undefined}
        />
        {data.valuation_methods ? (
          <MetricCell
            label="PWERM"
            value={formatCurrency(data.valuation_methods.pwerm)}
            sub={data.valuation_methods.dcf ? `DCF: ${formatCurrency(data.valuation_methods.dcf)}` : undefined}
          />
        ) : (
          <MetricCell label="Model" value={data.business_model || '--'} />
        )}
      </div>

      {/* Business description */}
      {data.product_description && (
        <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
          {data.product_description}
        </p>
      )}

      {/* Mini cap table — top 3 investors */}
      {data.cap_table?.investors && data.cap_table.investors.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Top Investors</span>
          <div className="space-y-0.5">
            {data.cap_table.investors.slice(0, 3).map((inv, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px]">
                <span className="truncate flex-1 min-w-0">{inv.name}</span>
                {inv.round && <span className="text-muted-foreground text-[10px] shrink-0">{inv.round}</span>}
                <div className="w-16 shrink-0 flex items-center gap-1">
                  <div className="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-blue-500 dark:bg-blue-400"
                      style={{ width: `${Math.min((inv.ownership * 100), 100)}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-[10px] w-8 text-right">{(inv.ownership * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
