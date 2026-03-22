'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { MemoSectionWrapper } from '../MemoSectionWrapper';
import { useMemoContext, type NarrativeCard, type DriverDef, type DriverValue } from '../MemoContext';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { Loader2, Play, ArrowRight, ChevronDown, ChevronRight } from 'lucide-react';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDriverValue(v: number, unit: DriverDef['unit']): string {
  switch (unit) {
    case 'percentage': return `${(v * 100).toFixed(1)}%`;
    case 'currency':
      if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
      if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
      return `$${v.toLocaleString()}`;
    case 'months': return `${v.toFixed(0)} mo`;
    default: return v.toLocaleString();
  }
}

// ---------------------------------------------------------------------------
// Subcategory collapsible group
// ---------------------------------------------------------------------------

function SubcategoryGroup({ label, count, children }: {
  label: string;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border/50 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 text-[11px] font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {label}
        <span className="text-[9px] ml-auto opacity-60">{count} drivers</span>
      </button>
      {open && <div className="space-y-3 px-3 py-2 border-t border-border/30 bg-muted/20">{children}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface DriversSectionProps {
  onDelete?: () => void;
  readOnly?: boolean;
}

export function DriversSection({ onDelete, readOnly = false }: DriversSectionProps) {
  const ctx = useMemoContext();
  const [narrativeCards, setNarrativeCards] = useState<NarrativeCard[]>([]);
  const [groupFilter, setGroupFilter] = useState<string>('all');
  const [showInherited, setShowInherited] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [pendingOverrides, setPendingOverrides] = useState<Record<string, number>>({});

  const branchId = ctx.activeBranchId || 'base';
  const branchValues = ctx.driverValues[branchId] || [];

  // Merge registry with current values
  const drivers = useMemo(() => {
    return ctx.driverRegistry.map(def => {
      const val = branchValues.find(v => v.id === def.id);
      return {
        ...def,
        currentValue: pendingOverrides[def.id] ?? val?.value ?? def.default ?? 0,
        source: val?.source ?? 'default',
      };
    });
  }, [ctx.driverRegistry, branchValues, pendingOverrides]);

  // Groups
  const groups = useMemo(() => {
    const set = new Set(ctx.driverRegistry.map(d => d.group || 'other'));
    return ['all', ...Array.from(set)];
  }, [ctx.driverRegistry]);

  const filteredDrivers = groupFilter === 'all'
    ? drivers
    : drivers.filter(d => (d.group || 'other') === groupFilter);

  const visibleDrivers = showInherited
    ? filteredDrivers
    : filteredDrivers.filter(d => d.source === 'override');

  // Handle slider change (debounced local, explicit Run Model to push)
  const handleSliderChange = useCallback((driverId: string, value: number) => {
    setPendingOverrides(prev => ({ ...prev, [driverId]: value }));
  }, []);

  // Run Model — push all pending overrides to backend
  const handleRunModel = useCallback(async () => {
    if (Object.keys(pendingOverrides).length === 0) return;
    setRecomputing(true);
    try {
      await ctx.updateDrivers(branchId, pendingOverrides);
      setPendingOverrides({});
    } finally {
      setRecomputing(false);
    }
  }, [ctx, branchId, pendingOverrides]);

  const collapsedSummary = `${ctx.driverRegistry.length} drivers | ${Object.keys(pendingOverrides).length} pending changes`;

  const aiContext = useMemo(() => ({
    drivers: drivers.map(d => ({ id: d.id, label: d.label, value: d.currentValue, unit: d.unit, source: d.source })),
    branchId,
  }), [drivers, branchId]);

  const configBar = (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">Group:</span>
        <Select value={groupFilter} onValueChange={setGroupFilter}>
          <SelectTrigger className="h-6 w-[100px] text-[11px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            {groups.map(g => (
              <SelectItem key={g} value={g}>{g === 'all' ? 'All' : g.charAt(0).toUpperCase() + g.slice(1)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <label className="flex items-center gap-1 cursor-pointer">
        <input type="checkbox" checked={showInherited} onChange={e => setShowInherited(e.target.checked)} className="h-3 w-3 rounded" />
        <span className="text-muted-foreground">Inherited</span>
      </label>
      {!readOnly && (
        <Button variant="outline" size="sm" className="h-6 text-[11px] gap-1 ml-auto" onClick={handleRunModel} disabled={recomputing || Object.keys(pendingOverrides).length === 0}>
          {recomputing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          Run Model
        </Button>
      )}
    </>
  );

  return (
    <MemoSectionWrapper
      sectionType="drivers"
      title="Drivers"
      collapsedSummary={collapsedSummary}
      configContent={configBar}
      narrativeCards={narrativeCards}
      onNarrativeCardsChange={setNarrativeCards}
      aiDataContext={aiContext}
      onDelete={onDelete}
      readOnly={readOnly}
    >
      {visibleDrivers.length > 0 ? (
        <div className="space-y-3">
          {(() => {
            // Split drivers into top-level and subcategory groups
            const topLevel = visibleDrivers.filter(d => !d.parentGroup);
            const subGroups = new Map<string, typeof visibleDrivers>();
            for (const d of visibleDrivers) {
              if (d.parentGroup) {
                const existing = subGroups.get(d.parentGroup) || [];
                existing.push(d);
                subGroups.set(d.parentGroup, existing);
              }
            }

            const renderDriver = (driver: typeof visibleDrivers[0]) => {
              const min = driver.min ?? 0;
              const max = driver.max ?? (driver.unit === 'percentage' ? 1 : 10000000);
              const step = driver.step ?? (driver.unit === 'percentage' ? 0.01 : 1000);
              const hasPending = pendingOverrides[driver.id] !== undefined;
              const rippleTargets = driver.ripple || [];
              const rippleLabels = rippleTargets.map(targetId => {
                const target = ctx.driverRegistry.find(d => d.id === targetId);
                return target?.label || targetId;
              });

              return (
                <div key={driver.id} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium">{driver.label}</span>
                      {driver.source !== 'override' && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-muted text-muted-foreground">{driver.source}</span>
                      )}
                      {hasPending && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">pending</span>
                      )}
                    </div>
                    <span className="tabular-nums font-mono text-[11px]">
                      {formatDriverValue(driver.currentValue, driver.unit)}
                    </span>
                  </div>
                  {!readOnly ? (
                    <Slider
                      min={min}
                      max={max}
                      step={step}
                      value={[driver.currentValue]}
                      onValueChange={([v]) => handleSliderChange(driver.id, v)}
                      className="w-full"
                    />
                  ) : (
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{ width: `${Math.min(100, ((driver.currentValue - min) / (max - min)) * 100)}%` }}
                      />
                    </div>
                  )}
                  {hasPending && rippleLabels.length > 0 && (
                    <div className="flex items-center gap-1 text-[9px] text-blue-600 dark:text-blue-400 mt-0.5">
                      <ArrowRight className="h-2.5 w-2.5 shrink-0" />
                      <span>Ripples to: {rippleLabels.join(', ')}</span>
                    </div>
                  )}
                </div>
              );
            };

            const PARENT_LABELS: Record<string, string> = {
              opex_rd: 'R&D Breakdown',
              opex_sm: 'Sales & Marketing Breakdown',
              opex_ga: 'G&A Breakdown',
              cogs: 'COGS Breakdown',
            };

            return (
              <>
                {topLevel.map(renderDriver)}
                {Array.from(subGroups.entries()).map(([parentKey, subs]) => (
                  <SubcategoryGroup
                    key={parentKey}
                    label={PARENT_LABELS[parentKey] || parentKey}
                    count={subs.length}
                  >
                    {subs.map(renderDriver)}
                  </SubcategoryGroup>
                ))}
              </>
            );
          })()}
        </div>
      ) : (
        <div className="flex items-center justify-center h-[120px] text-xs text-muted-foreground">
          {ctx.driverRegistry.length === 0
            ? 'Build a forecast to populate drivers'
            : 'No drivers match the current filter'}
        </div>
      )}
    </MemoSectionWrapper>
  );
}
