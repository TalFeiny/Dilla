'use client';

import React, { useCallback } from 'react';
import type { ChipDef } from '@/lib/chips/types';
import { DOMAIN_META } from '@/lib/chips/types';
import { cn } from '@/lib/utils';

// Domain → tailwind bg/text color classes
const DOMAIN_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  fpa:        { bg: 'bg-emerald-50',  text: 'text-emerald-700',  border: 'border-emerald-200' },
  analytics:  { bg: 'bg-blue-50',     text: 'text-blue-700',     border: 'border-blue-200' },
  scenario:   { bg: 'bg-amber-50',    text: 'text-amber-700',    border: 'border-amber-200' },
  driver:     { bg: 'bg-purple-50',   text: 'text-purple-700',   border: 'border-purple-200' },
  capital:    { bg: 'bg-indigo-50',   text: 'text-indigo-700',   border: 'border-indigo-200' },
  macro:      { bg: 'bg-red-50',      text: 'text-red-700',      border: 'border-red-200' },
  intel:      { bg: 'bg-cyan-50',     text: 'text-cyan-700',     border: 'border-cyan-200' },
  report:     { bg: 'bg-slate-50',    text: 'text-slate-700',    border: 'border-slate-200' },
  compliance: { bg: 'bg-rose-50',     text: 'text-rose-700',     border: 'border-rose-200' },
  data:       { bg: 'bg-zinc-50',     text: 'text-zinc-700',     border: 'border-zinc-200' },
  comms:      { bg: 'bg-orange-50',   text: 'text-orange-700',   border: 'border-orange-200' },
  funding:    { bg: 'bg-teal-50',     text: 'text-teal-700',     border: 'border-teal-200' },
  portfolio:  { bg: 'bg-violet-50',   text: 'text-violet-700',   border: 'border-violet-200' },
  // V2 domains:
  modeling:   { bg: 'bg-lime-50',     text: 'text-lime-700',     border: 'border-lime-200' },
  ops:        { bg: 'bg-yellow-50',   text: 'text-yellow-700',   border: 'border-yellow-200' },
  transform:  { bg: 'bg-sky-50',      text: 'text-sky-700',      border: 'border-sky-200' },
  chart:      { bg: 'bg-pink-50',     text: 'text-pink-700',     border: 'border-pink-200' },
  bridge:     { bg: 'bg-fuchsia-50',  text: 'text-fuchsia-700',  border: 'border-fuchsia-200' },
};

export { DOMAIN_COLORS };

interface ChipProps {
  def: ChipDef;
  /** Called when user clicks the chip (to insert into input) */
  onSelect: (def: ChipDef) => void;
  /** Compact mode for tray display */
  compact?: boolean;
  className?: string;
}

/**
 * Chip — a small colored badge representing a backend capability.
 * Sits in the tray. Click to insert into the active input.
 * Draggable into the input area.
 */
export function Chip({ def, onSelect, compact, className }: ChipProps) {
  const colors = DOMAIN_COLORS[def.domain] ?? DOMAIN_COLORS.data;

  const handleClick = useCallback(() => {
    onSelect(def);
  }, [def, onSelect]);

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      e.dataTransfer.setData('application/chip-id', def.id);
      e.dataTransfer.effectAllowed = 'copy';
    },
    [def.id],
  );

  return (
    <button
      type="button"
      draggable
      onDragStart={handleDragStart}
      onClick={handleClick}
      title={def.description}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5',
        'text-[11px] font-medium leading-tight',
        'cursor-grab active:cursor-grabbing',
        'transition-all duration-150',
        'hover:shadow-sm hover:scale-[1.03] active:scale-[0.97]',
        'select-none whitespace-nowrap',
        colors.bg,
        colors.text,
        colors.border,
        className,
      )}
    >
      {def.label}
      {def.costTier === 'expensive' && (
        <span className="ml-0.5 text-[9px] opacity-50" title="Expensive operation">$$</span>
      )}
    </button>
  );
}
