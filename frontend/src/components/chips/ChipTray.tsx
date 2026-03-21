'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { ChipDef } from '@/lib/chips/types';
import { DOMAIN_META, type ChipDomain } from '@/lib/chips/types';
import { CHIP_REGISTRY, chipsByDomain } from '@/lib/chips/registry';
import { loadDriverChips } from '@/lib/chips/driver-chips';
import { Chip } from './Chip';
import { ChipSearch } from './ChipSearch';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface ChipTrayProps {
  /** Active company ID for loading driver chips */
  companyId?: string;
  /** Called when a chip is selected (to insert into input) */
  onSelectChip: (def: ChipDef) => void;
  /** Whether the tray is collapsed */
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}

/** Domain display order */
const DOMAIN_ORDER: ChipDomain[] = [
  'fpa', 'modeling', 'ops', 'analytics', 'scenario', 'driver', 'capital', 'funding',
  'macro', 'intel', 'bridge', 'transform', 'chart', 'report', 'compliance',
  'portfolio', 'data', 'comms',
];

/**
 * ChipTray — always-visible panel showing all capabilities grouped by domain.
 * Collapsible. Searchable. Driver chips load dynamically per company.
 */
export function ChipTray({
  companyId,
  onSelectChip,
  collapsed,
  onToggleCollapse,
  className,
}: ChipTrayProps) {
  const [driverChips, setDriverChips] = useState<ChipDef[]>([]);
  const [searchResults, setSearchResults] = useState<ChipDef[] | null>(null);
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set(DOMAIN_ORDER));

  // Load driver chips when company changes
  useEffect(() => {
    if (!companyId) return;
    loadDriverChips(companyId).then(setDriverChips).catch(() => {});
  }, [companyId]);

  // All chips = static registry + dynamic drivers
  const allChips = useMemo(
    () => [...CHIP_REGISTRY, ...driverChips],
    [driverChips],
  );

  // Grouped by domain
  const grouped = useMemo(() => {
    const chips = searchResults ?? allChips;
    const g: Record<string, ChipDef[]> = {};
    for (const chip of chips) {
      (g[chip.domain] ??= []).push(chip);
    }
    return g;
  }, [allChips, searchResults]);

  const toggleDomain = useCallback((domain: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(domain)) next.delete(domain);
      else next.add(domain);
      return next;
    });
  }, []);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggleCollapse}
        className={cn(
          'flex items-center gap-1 px-2 py-1 text-[10px] text-muted-foreground',
          'hover:text-foreground transition-colors',
          className,
        )}
      >
        <ChevronRight className="h-3 w-3" />
        Tools
      </button>
    );
  }

  return (
    <div className={cn('border-b border-border/40 bg-muted/20', className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-2 pt-1.5 pb-1">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-0.5"
        >
          <ChevronDown className="h-3 w-3" />
          Tools
        </button>
        <ChipSearch onResults={setSearchResults} className="flex-1 max-w-[200px]" />
      </div>

      {/* Domain rows */}
      <div className="px-2 pb-1.5 space-y-0.5 max-h-[200px] overflow-y-auto">
        {DOMAIN_ORDER.map((domain) => {
          const chips = grouped[domain];
          if (!chips || chips.length === 0) return null;
          const meta = DOMAIN_META[domain];
          const expanded = expandedDomains.has(domain);

          return (
            <div key={domain}>
              <button
                type="button"
                onClick={() => toggleDomain(domain)}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground py-0.5 w-full text-left"
              >
                {expanded ? (
                  <ChevronDown className="h-2.5 w-2.5" />
                ) : (
                  <ChevronRight className="h-2.5 w-2.5" />
                )}
                <span className="font-medium min-w-[50px]">{meta.label}</span>
              </button>

              {expanded && (
                <div className="flex flex-wrap gap-1 pl-4 pb-0.5">
                  {chips.map((chip) => (
                    <Chip
                      key={chip.id}
                      def={chip}
                      onSelect={onSelectChip}
                      compact
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
