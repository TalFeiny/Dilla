'use client';

import { useState, useCallback, useMemo } from 'react';
import { Search, ChevronDown, ChevronRight, GripVertical, PanelLeftClose } from 'lucide-react';
import { CHIP_REGISTRY } from '@/lib/chips/registry';
import { buildPalette } from '@/lib/workflow/palette';
import type { PaletteItem, PaletteCategory, WorkflowNodeData } from '@/lib/workflow/types';
import { DOMAIN_META } from '@/lib/chips/types';
import { useWorkflowStore } from '@/lib/workflow/store';
import { resolveIcon } from './nodes/icon-resolver';

const DOMAIN_COLORS: Record<string, string> = {
  emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  indigo: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  red: 'bg-red-500/10 text-red-400 border-red-500/20',
  cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  slate: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  teal: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
  violet: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  lime: 'bg-lime-500/10 text-lime-400 border-lime-500/20',
  sky: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  pink: 'bg-pink-500/10 text-pink-400 border-pink-500/20',
  zinc: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  fuchsia: 'bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20',
  rose: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  orange: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
};

const ICON_TEXT_COLORS: Record<string, string> = {
  emerald: 'text-emerald-400', blue: 'text-blue-400', amber: 'text-amber-400',
  purple: 'text-purple-400', indigo: 'text-indigo-400', red: 'text-red-400',
  cyan: 'text-cyan-400', slate: 'text-slate-400', teal: 'text-teal-400',
  violet: 'text-violet-400', lime: 'text-lime-400', sky: 'text-sky-400',
  pink: 'text-pink-400', zinc: 'text-zinc-400', fuchsia: 'text-fuchsia-400',
  rose: 'text-rose-400', orange: 'text-orange-400', yellow: 'text-yellow-400',
};

function PaletteIcon({ name, color }: { name: string; color: string }) {
  const Icon = resolveIcon(name);
  return <Icon className={`w-3.5 h-3.5 ${ICON_TEXT_COLORS[color] || 'text-gray-400'} flex-shrink-0`} />;
}

export function NodePalette() {
  const [search, setSearch] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['cat_triggers', 'cat_fpa', 'cat_operators']));
  const togglePalette = useWorkflowStore((s) => s.togglePalette);

  const categories = useMemo(() => buildPalette(CHIP_REGISTRY), []);

  const filtered = useMemo(() => {
    if (!search.trim()) return categories;
    const q = search.toLowerCase();
    return categories
      .map((cat) => ({
        ...cat,
        items: cat.items.filter(
          (item) =>
            item.label.toLowerCase().includes(q) ||
            item.description.toLowerCase().includes(q)
        ),
      }))
      .filter((cat) => cat.items.length > 0);
  }, [categories, search]);

  const toggleCategory = useCallback((id: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const onDragStart = useCallback((e: React.DragEvent, item: PaletteItem) => {
    e.dataTransfer.setData('application/workflow-node', JSON.stringify(item));
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  return (
    <div className="w-64 bg-card border-r border-border flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-3 border-b border-border flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">Nodes</span>
        <button onClick={togglePalette} className="p-1 hover:bg-accent rounded-lg text-muted-foreground">
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes..."
            className="w-full pl-8 pr-3 py-1.5 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-foreground/30"
          />
        </div>
      </div>

      {/* Categories */}
      <div className="flex-1 overflow-y-auto">
        {filtered.map((cat) => (
          <div key={cat.id}>
            <button
              onClick={() => toggleCategory(cat.id)}
              className="w-full px-3 py-2 flex items-center gap-2 hover:bg-accent/50 text-left"
            >
              {expandedCategories.has(cat.id) ? (
                <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
              )}
              <span className={`text-xs font-semibold uppercase tracking-wider text-${cat.color}-400`}>
                {cat.label}
              </span>
              <span className="text-[10px] text-muted-foreground ml-auto">{cat.items.length}</span>
            </button>

            {expandedCategories.has(cat.id) && (
              <div className="px-2 pb-2 space-y-0.5">
                {cat.items.map((item) => (
                  <div
                    key={item.id}
                    draggable
                    onDragStart={(e) => onDragStart(e, item)}
                    className={`
                      flex items-center gap-2 px-2.5 py-1.5 rounded-lg cursor-grab active:cursor-grabbing
                      border border-transparent hover:border-border hover:bg-accent
                      transition-colors duration-100 group
                    `}
                  >
                    <GripVertical className="w-3 h-3 text-border group-hover:text-muted-foreground flex-shrink-0" />
                    <PaletteIcon name={item.icon} color={item.color} />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-foreground/80 truncate">{item.label}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
