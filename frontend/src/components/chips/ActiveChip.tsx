'use client';

import React, { useCallback, useState } from 'react';
import type { ActiveChip as ActiveChipType, ChipParamDef } from '@/lib/chips/types';
import { DOMAIN_COLORS } from './Chip';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { X, ChevronDown } from 'lucide-react';

interface ActiveChipProps {
  chip: ActiveChipType;
  /** Update a parameter value */
  onUpdate: (instanceId: string, key: string, value: any) => void;
  /** Remove this chip from the input */
  onRemove: (instanceId: string) => void;
  /** Whether the input is disabled */
  disabled?: boolean;
}

/**
 * ActiveChip — rendered inline in the input area.
 * Shows the chip label + configured param summary.
 * Click to open a popover for parameter configuration.
 */
export function ActiveChip({ chip, onUpdate, onRemove, disabled }: ActiveChipProps) {
  const [open, setOpen] = useState(false);
  const colors = DOMAIN_COLORS[chip.def.domain] ?? DOMAIN_COLORS.data;

  // Build the display label with param values
  const paramDisplay = chip.def.params
    .map((p) => {
      const val = chip.values[p.key] ?? p.default;
      if (p.chipDisplay) return p.chipDisplay(val);
      if (p.type === 'percent') return `${val}%`;
      if (p.type === 'select') {
        const opt = p.options?.find((o) => o.value === val);
        return opt?.label ?? val;
      }
      if (val === '' || val === p.default) return null;
      return String(val);
    })
    .filter(Boolean)
    .join(' ');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <span
          role="button"
          tabIndex={0}
          className={cn(
            'inline-flex items-center gap-0.5 rounded-full border px-1.5 py-px',
            'text-[11px] font-medium leading-tight',
            'cursor-pointer select-none whitespace-nowrap',
            'transition-all duration-100',
            'hover:shadow-sm',
            colors.bg,
            colors.text,
            colors.border,
            disabled && 'opacity-50 pointer-events-none',
          )}
          contentEditable={false}
          suppressContentEditableWarning
        >
          {chip.def.label}
          {paramDisplay && (
            <span className="opacity-70 ml-0.5">{paramDisplay}</span>
          )}
          <ChevronDown className="h-2.5 w-2.5 opacity-50" />
        </span>
      </PopoverTrigger>

      <PopoverContent
        className="w-56 p-2"
        align="start"
        sideOffset={4}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">{chip.def.label}</span>
            <button
              type="button"
              onClick={() => onRemove(chip.instanceId)}
              className="text-muted-foreground hover:text-foreground p-0.5"
              title="Remove chip"
            >
              <X className="h-3 w-3" />
            </button>
          </div>

          {chip.def.params.map((param) => (
            <ParamEditor
              key={param.key}
              param={param}
              value={chip.values[param.key] ?? param.default}
              onChange={(val) => onUpdate(chip.instanceId, param.key, val)}
            />
          ))}

          {chip.def.params.length === 0 && (
            <p className="text-[10px] text-muted-foreground">No parameters to configure</p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Inline param editor
// ---------------------------------------------------------------------------

function ParamEditor({
  param,
  value,
  onChange,
}: {
  param: ChipParamDef;
  value: any;
  onChange: (val: any) => void;
}) {
  switch (param.type) {
    case 'select':
      return (
        <label className="block">
          <span className="text-[10px] text-muted-foreground">{param.label}</span>
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="mt-0.5 w-full rounded border border-input bg-background px-2 py-1 text-xs"
          >
            {param.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      );

    case 'number':
    case 'months':
    case 'days':
      return (
        <label className="block">
          <span className="text-[10px] text-muted-foreground">{param.label}</span>
          <Input
            type="number"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            min={param.min}
            max={param.max}
            step={param.step ?? 1}
            className="mt-0.5 h-7 text-xs"
          />
        </label>
      );

    case 'percent':
      return (
        <label className="block">
          <span className="text-[10px] text-muted-foreground">{param.label}</span>
          <div className="flex items-center gap-1 mt-0.5">
            <Input
              type="number"
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              min={param.min ?? -100}
              max={param.max ?? 100}
              step={param.step ?? 1}
              className="h-7 text-xs flex-1"
            />
            <span className="text-xs text-muted-foreground">%</span>
          </div>
        </label>
      );

    case 'currency':
      return (
        <label className="block">
          <span className="text-[10px] text-muted-foreground">{param.label}</span>
          <div className="flex items-center gap-1 mt-0.5">
            <span className="text-xs text-muted-foreground">$</span>
            <Input
              type="number"
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              min={param.min}
              max={param.max}
              step={param.step ?? 1000}
              className="h-7 text-xs flex-1"
            />
          </div>
        </label>
      );

    case 'text':
    case 'metric':
    default:
      return (
        <label className="block">
          <span className="text-[10px] text-muted-foreground">{param.label}</span>
          <Input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={param.label}
            className="mt-0.5 h-7 text-xs"
          />
        </label>
      );
  }
}
