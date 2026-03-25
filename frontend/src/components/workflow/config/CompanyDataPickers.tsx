'use client';

import { useMemo } from 'react';
import { useWorkflowStore } from '@/lib/workflow/store';
import type { CompanyDataSnapshot } from '@/lib/workflow/assumptions';

// ── Shared styles ────────────────────────────────────────────────────────────

const selectClass = 'w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500';
const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500';

// ── Category grouping for RowPicker ──────────────────────────────────────────

const ROW_GROUPS: { label: string; prefix: string[] }[] = [
  { label: 'Revenue', prefix: ['revenue', 'arr', 'mrr', 'nrr'] },
  { label: 'Cost of Goods', prefix: ['cogs', 'cost_of'] },
  { label: 'Gross Profit', prefix: ['gross_profit', 'gross_margin'] },
  { label: 'Operating Expenses', prefix: ['opex', 'rd', 'sm', 'ga', 'marketing', 'sales'] },
  { label: 'EBITDA / Profit', prefix: ['ebitda', 'ebit', 'net_income', 'operating_income'] },
  { label: 'Cash & Capital', prefix: ['cash', 'burn', 'runway', 'capex', 'debt', 'funding'] },
  { label: 'Workforce', prefix: ['headcount', 'payroll', 'salary', 'employee'] },
  { label: 'Unit Economics', prefix: ['cac', 'ltv', 'churn', 'arpu', 'acv'] },
];

function groupCategory(cat: string): string {
  const lower = cat.toLowerCase();
  for (const g of ROW_GROUPS) {
    if (g.prefix.some((p) => lower.startsWith(p) || lower.includes(p))) {
      return g.label;
    }
  }
  return 'Other';
}

function formatValue(v: number | undefined): string {
  if (v == null) return '';
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── RowPicker ────────────────────────────────────────────────────────────────

interface RowPickerProps {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  placeholder?: string;
  /** Allow selecting multiple rows */
  multi?: boolean;
  /** Currently selected rows (for multi mode) */
  multiValue?: string[];
  onMultiChange?: (v: string[]) => void;
}

export function RowPicker({ value, onChange, label, placeholder, multi, multiValue, onMultiChange }: RowPickerProps) {
  const companyData = useWorkflowStore((s) => s.companyData);
  const companyDataLoading = useWorkflowStore((s) => s.companyDataLoading);

  const grouped = useMemo(() => {
    if (!companyData?.metadata?.categories) return null;
    const groups = new Map<string, { key: string; label: string; value: string }[]>();
    for (const cat of companyData.metadata.categories) {
      const group = groupCategory(cat);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)!.push({
        key: cat,
        label: formatLabel(cat),
        value: formatValue(companyData.latest?.[cat]),
      });
    }
    return groups;
  }, [companyData]);

  if (companyDataLoading) {
    return (
      <PickerField label={label}>
        <div className="text-xs text-gray-500 animate-pulse py-2">Loading company data...</div>
      </PickerField>
    );
  }

  if (!grouped || grouped.size === 0) {
    return (
      <PickerField label={label}>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
          placeholder={placeholder || 'e.g. revenue, opex, ebitda'}
        />
        <div className="mt-1 text-[10px] text-gray-600">Select a company to see available rows</div>
      </PickerField>
    );
  }

  // Multi-select mode
  if (multi && onMultiChange) {
    const selected = new Set(multiValue || []);
    return (
      <PickerField label={label}>
        <div className="space-y-1 max-h-48 overflow-y-auto bg-gray-900 border border-gray-700 rounded-lg p-2">
          {Array.from(grouped.entries()).map(([group, items]) => (
            <div key={group}>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider px-1 pt-1">{group}</div>
              {items.map((item) => (
                <label key={item.key} className="flex items-center gap-2 px-1 py-0.5 rounded hover:bg-gray-800 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.has(item.key)}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(item.key);
                      else next.delete(item.key);
                      onMultiChange(Array.from(next));
                    }}
                    className="rounded border-gray-600 bg-gray-800 text-emerald-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <span className="text-xs text-gray-300 flex-1">{item.label}</span>
                  {item.value && <span className="text-[10px] text-gray-500 font-mono">{item.value}</span>}
                </label>
              ))}
            </div>
          ))}
        </div>
        {selected.size > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {Array.from(selected).map((k) => (
              <span key={k} className="text-[10px] px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded border border-emerald-500/20">
                {formatLabel(k)}
              </span>
            ))}
          </div>
        )}
      </PickerField>
    );
  }

  // Single-select mode
  return (
    <PickerField label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
        <option value="">Select a row...</option>
        {Array.from(grouped.entries()).map(([group, items]) => (
          <optgroup key={group} label={group}>
            {items.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}{item.value ? ` — ${item.value}` : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </PickerField>
  );
}

// ── PeriodPicker ─────────────────────────────────────────────────────────────

interface PeriodPickerProps {
  value: string;
  onChange: (v: string) => void;
  label?: string;
  placeholder?: string;
  /** Show an "All periods" option */
  allowAll?: boolean;
  /** Show the value for a given row key in each period */
  rowKey?: string;
}

export function PeriodPicker({ value, onChange, label, placeholder, allowAll = true, rowKey }: PeriodPickerProps) {
  const companyData = useWorkflowStore((s) => s.companyData);
  const companyDataLoading = useWorkflowStore((s) => s.companyDataLoading);

  const periods = companyData?.periods || [];
  const timeSeries = rowKey ? companyData?.timeSeries?.[rowKey] : null;

  if (companyDataLoading) {
    return (
      <PickerField label={label}>
        <div className="text-xs text-gray-500 animate-pulse py-2">Loading periods...</div>
      </PickerField>
    );
  }

  if (periods.length === 0) {
    return (
      <PickerField label={label}>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
          placeholder={placeholder || 'e.g. 2025-03'}
        />
        <div className="mt-1 text-[10px] text-gray-600">Select a company to see available periods</div>
      </PickerField>
    );
  }

  return (
    <PickerField label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
        {allowAll && <option value="">All periods</option>}
        {!allowAll && <option value="">Select a period...</option>}
        {periods.map((p) => {
          const val = timeSeries?.[p];
          return (
            <option key={p} value={p}>
              {p}{val != null ? ` — ${formatValue(val)}` : ''}
            </option>
          );
        })}
      </select>
    </PickerField>
  );
}

// ── CompanyBadge — shows current company context ─────────────────────────────

export function CompanyBadge() {
  const companyId = useWorkflowStore((s) => s.companyId);
  const companyName = useWorkflowStore((s) => s.companyName);
  const companyData = useWorkflowStore((s) => s.companyData);

  if (!companyId) {
    return (
      <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
        No company selected — connect a company from the Matrix to populate data.
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2">
      <div className="w-2 h-2 rounded-full bg-emerald-500" />
      <span className="text-xs text-gray-300 font-medium">{companyName || companyId}</span>
      {companyData && (
        <span className="text-[10px] text-gray-500 ml-auto">
          {companyData.metadata.categories.length} rows · {companyData.periods.length} periods
        </span>
      )}
    </div>
  );
}

// ── Helper ───────────────────────────────────────────────────────────────────

function PickerField({ label, children }: { label?: string; children: React.ReactNode }) {
  if (!label) return <>{children}</>;
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1.5">{label}</label>
      {children}
    </div>
  );
}
