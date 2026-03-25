'use client';

import { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { useWorkflowStore } from '@/lib/workflow/store';
import {
  buildExpressionVariables,
  filterVariables,
  groupVariables,
  type ExpressionVariable,
} from '@/lib/workflow/expressions';

// ── ExpressionInput ──────────────────────────────────────────────────────────
//
// A textarea that supports {{ variable }} references with autocomplete.
// Typing "{{" triggers a dropdown picker with all available variables
// grouped by source (Company Data, Upstream Nodes, Loop Variables, Built-in).

interface ExpressionInputProps {
  /** Current expression value */
  value: string;
  /** Called when expression changes */
  onChange: (v: string) => void;
  /** Node ID — used to resolve upstream variables */
  nodeId: string;
  /** Number of rows */
  rows?: number;
  /** Placeholder text */
  placeholder?: string;
  /** Label above the input */
  label?: string;
}

export function ExpressionInput({
  value,
  onChange,
  nodeId,
  rows = 3,
  placeholder = 'e.g. {{ row.revenue }} * 1.1 - {{ row.opex }}',
  label,
}: ExpressionInputProps) {
  const [showPicker, setShowPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [cursorPos, setCursorPos] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Pull store data for variable resolution
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const companyData = useWorkflowStore((s) => s.companyData);
  const companyId = useWorkflowStore((s) => s.companyId);
  const companyName = useWorkflowStore((s) => s.companyName);

  // Build available variables
  const allVars = useMemo(
    () => buildExpressionVariables(nodeId, nodes, edges, companyData, companyId, companyName),
    [nodeId, nodes, edges, companyData, companyId, companyName]
  );

  const filteredVars = useMemo(
    () => filterVariables(allVars, search),
    [allVars, search]
  );

  const grouped = useMemo(
    () => groupVariables(filteredVars),
    [filteredVars]
  );

  // Detect {{ typing to open picker
  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newVal = e.target.value;
      const pos = e.target.selectionStart || 0;
      onChange(newVal);
      setCursorPos(pos);

      // Check if the user just typed "{{"
      const before = newVal.slice(0, pos);
      const lastOpen = before.lastIndexOf('{{');
      const lastClose = before.lastIndexOf('}}');

      if (lastOpen > lastClose) {
        // We're inside a {{ ... }} — show picker
        const partial = before.slice(lastOpen + 2).trim();
        setSearch(partial);
        setShowPicker(true);
      } else {
        setShowPicker(false);
        setSearch('');
      }
    },
    [onChange]
  );

  // Insert a variable at cursor position
  const insertVariable = useCallback(
    (v: ExpressionVariable) => {
      const before = value.slice(0, cursorPos);
      const after = value.slice(cursorPos);

      // Find the opening {{ before cursor
      const lastOpen = before.lastIndexOf('{{');
      const prefix = before.slice(0, lastOpen);
      const insertion = `{{ ${v.path} }}`;

      // If there's a closing }} after cursor, skip past it
      const afterTrim = after.trimStart();
      const skipClose = afterTrim.startsWith('}}') ? after.indexOf('}}') + 2 : 0;
      const suffix = after.slice(skipClose);

      const newVal = prefix + insertion + suffix;
      onChange(newVal);
      setShowPicker(false);
      setSearch('');

      // Re-focus textarea
      setTimeout(() => {
        if (textareaRef.current) {
          const newPos = (prefix + insertion).length;
          textareaRef.current.focus();
          textareaRef.current.setSelectionRange(newPos, newPos);
        }
      }, 0);
    },
    [value, cursorPos, onChange]
  );

  // Close picker on outside click
  useEffect(() => {
    if (!showPicker) return;
    const handler = (e: MouseEvent) => {
      if (
        pickerRef.current &&
        !pickerRef.current.contains(e.target as Node) &&
        textareaRef.current &&
        !textareaRef.current.contains(e.target as Node)
      ) {
        setShowPicker(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showPicker]);

  // Render variable pills in a preview line
  const preview = useMemo(() => {
    if (!value) return null;
    const parts = value.split(/(\{\{[^}]+\}\})/g);
    const hasVars = parts.some((p) => p.startsWith('{{'));
    if (!hasVars) return null;

    return parts.map((part, i) => {
      if (part.startsWith('{{') && part.endsWith('}}')) {
        const path = part.slice(2, -2).trim();
        const matched = allVars.find((v) => v.path === path);
        return (
          <span
            key={i}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-blue-500/15 text-blue-300 rounded text-[10px] font-mono border border-blue-500/20"
            title={matched ? `${matched.label}: ${matched.preview}` : path}
          >
            {path}
            {matched && (
              <span className="text-blue-400/60">{matched.preview}</span>
            )}
          </span>
        );
      }
      if (!part.trim()) return null;
      return (
        <span key={i} className="text-[10px] text-gray-500 font-mono">
          {part.trim()}
        </span>
      );
    });
  }, [value, allVars]);

  return (
    <div className="relative">
      {label && (
        <label className="block text-xs text-gray-400 mb-1.5">{label}</label>
      )}

      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        rows={rows}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-blue-500/50 resize-none"
        placeholder={placeholder}
      />

      {/* Variable preview pills */}
      {preview && (
        <div className="mt-1 flex flex-wrap gap-1 items-center">
          {preview}
        </div>
      )}

      {/* Hint */}
      <div className="mt-1 text-[10px] text-gray-600">
        Type <span className="text-gray-400 font-mono">{'{{'}</span> to insert a variable
      </div>

      {/* Autocomplete picker */}
      {showPicker && (
        <div
          ref={pickerRef}
          className="absolute z-50 left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl max-h-64 overflow-y-auto"
        >
          {/* Search filter */}
          <div className="px-3 py-2 border-b border-gray-800">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-gray-800 border-none rounded px-2 py-1 text-xs text-gray-200 focus:outline-none placeholder-gray-600"
              placeholder="Filter variables..."
              autoFocus
            />
          </div>

          {filteredVars.length === 0 ? (
            <div className="px-3 py-4 text-xs text-gray-500 text-center">
              No variables found
            </div>
          ) : (
            Array.from(grouped.entries()).map(([group, vars]) => (
              <div key={group}>
                <div className="px-3 py-1.5 text-[10px] text-gray-500 uppercase tracking-wider bg-gray-800/50 sticky top-0">
                  {group}
                </div>
                {vars.map((v) => (
                  <button
                    key={v.path}
                    onClick={() => insertVariable(v)}
                    className="w-full px-3 py-1.5 flex items-center gap-2 hover:bg-gray-800 text-left transition-colors"
                  >
                    <span className="text-xs text-blue-300 font-mono flex-1 truncate">{v.path}</span>
                    <span className="text-[10px] text-gray-500 truncate max-w-[80px]">{v.preview}</span>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
