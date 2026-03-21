'use client';

import React, { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import { searchChips } from '@/lib/chips/registry';
import type { ChipDef } from '@/lib/chips/types';

interface ChipSearchProps {
  /** Callback with filtered results (or all if query empty) */
  onResults: (chips: ChipDef[]) => void;
  className?: string;
}

/**
 * ChipSearch — compact search input that filters the chip tray.
 * Searches across label, description, domain, and tool name.
 */
export function ChipSearch({ onResults, className }: ChipSearchProps) {
  const [query, setQuery] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setQuery(q);
    onResults(searchChips(q));
  };

  return (
    <div className={`relative ${className ?? ''}`}>
      <Search className="absolute left-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
      <input
        type="text"
        value={query}
        onChange={handleChange}
        placeholder="Search tools..."
        className="w-full h-6 pl-5 pr-2 text-[11px] rounded border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  );
}
