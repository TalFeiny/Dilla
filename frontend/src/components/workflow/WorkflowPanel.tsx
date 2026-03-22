'use client';

import { useMemo, useState } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { useWorkflowStore } from '@/lib/workflow/store';
import type { WorkflowNodeData } from '@/lib/workflow/types';

// ── P&L row options for targeting ────────────────────────────────────────────
const PNL_ROWS = [
  { id: 'revenue', label: 'Revenue', children: ['product', 'services', 'subscriptions', 'other'] },
  { id: 'cogs', label: 'COGS', children: ['materials', 'hosting', 'support', 'other'] },
  { id: 'opex_rd', label: 'OpEx — R&D', children: ['salaries', 'contractors', 'tools', 'other'] },
  { id: 'opex_sm', label: 'OpEx — S&M', children: ['salaries', 'ads', 'events', 'other'] },
  { id: 'opex_ga', label: 'OpEx — G&A', children: ['salaries', 'rent', 'legal', 'insurance', 'other'] },
  { id: 'gross_profit', label: 'Gross Profit', children: [] },
  { id: 'ebitda', label: 'EBITDA', children: [] },
] as const;

// ── Available levers/drivers ─────────────────────────────────────────────────
const AVAILABLE_LEVERS = [
  { key: 'revenue_growth', label: 'Revenue Growth', unit: '%', step: 1 },
  { key: 'gross_margin', label: 'Gross Margin', unit: '%', step: 1 },
  { key: 'burn_rate', label: 'Burn Rate', unit: '$', step: 1000 },
  { key: 'churn_rate', label: 'Churn Rate', unit: '%', step: 0.1 },
  { key: 'headcount_growth', label: 'Headcount Growth', unit: '%', step: 1 },
  { key: 'pricing_change', label: 'Pricing Change', unit: '%', step: 1 },
  { key: 'cac', label: 'CAC', unit: '$', step: 10 },
  { key: 'ltv', label: 'LTV', unit: '$', step: 100 },
  { key: 'avg_salary', label: 'Avg Salary', unit: '$', step: 1000 },
  { key: 'rd_pct', label: 'R&D % of Revenue', unit: '%', step: 1 },
  { key: 'sm_pct', label: 'S&M % of Revenue', unit: '%', step: 1 },
  { key: 'ga_pct', label: 'G&A % of Revenue', unit: '%', step: 1 },
] as const;

// ── Helper: format lever value with unit ─────────────────────────────────────
function formatLeverValue(value: number, unit: string): string {
  if (unit === '%') return `${value > 0 ? '+' : ''}${value}%`;
  if (unit === '$') {
    if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}k`;
    return `$${value}`;
  }
  return String(value);
}

// ── Helper: display a row path nicely ────────────────────────────────────────
function formatRowPath(path: string): string {
  const parts = path.split('/');
  const parent = PNL_ROWS.find((r) => r.id === parts[0]);
  if (!parent) return path;
  if (parts.length === 1) return parent.label;
  return `${parent.label} > ${parts[1].charAt(0).toUpperCase() + parts[1].slice(1)}`;
}

// ── Generate month options ───────────────────────────────────────────────────
function generateMonthOptions(): { value: string; label: string }[] {
  const months: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = -6; i <= 18; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const lbl = d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    months.push({ value: val, label: lbl });
  }
  return months;
}

const MONTH_OPTIONS = generateMonthOptions();

// ── Shared input class ───────────────────────────────────────────────────────
const INPUT_CLS = 'w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500';
const INPUT_MONO = `${INPUT_CLS} font-mono`;
const SECTION_LABEL = 'text-[10px] text-gray-500 uppercase tracking-wider font-semibold';

export function WorkflowPanel() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const setPanelOpen = useWorkflowStore((s) => s.setPanelOpen);

  const [rowPickerOpen, setRowPickerOpen] = useState(false);
  const [leverPickerOpen, setLeverPickerOpen] = useState(false);
  const [customRowInput, setCustomRowInput] = useState('');

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  if (!selectedNode) return null;

  const data = selectedNode.data as unknown as WorkflowNodeData;

  const handleParamChange = (key: string, value: any) => {
    updateNodeData(selectedNode.id, {
      params: { ...data.params, [key]: value },
    });
  };

  // ── Targeting helpers ────────────────────────────────────────────────────
  const targetRows = data.targetRows || [];
  const targetPeriods = data.targetPeriods || [];
  const driverOverrides = data.driverOverrides || {};

  const toggleTargetRow = (rowPath: string) => {
    const next = targetRows.includes(rowPath)
      ? targetRows.filter((r) => r !== rowPath)
      : [...targetRows, rowPath];
    updateNodeData(selectedNode.id, { targetRows: next.length > 0 ? next : undefined });
  };

  const addCustomRow = () => {
    const trimmed = customRowInput.trim().toLowerCase().replace(/\s+/g, '_');
    if (trimmed && !targetRows.includes(trimmed)) {
      updateNodeData(selectedNode.id, { targetRows: [...targetRows, trimmed] });
    }
    setCustomRowInput('');
  };

  const setLeverValue = (key: string, value: number) => {
    updateNodeData(selectedNode.id, {
      driverOverrides: { ...driverOverrides, [key]: value },
    });
  };

  const removeLever = (key: string) => {
    const next = { ...driverOverrides };
    delete next[key];
    updateNodeData(selectedNode.id, {
      driverOverrides: Object.keys(next).length > 0 ? next : undefined,
    });
  };

  const addLever = (key: string) => {
    const def = AVAILABLE_LEVERS.find((l) => l.key === key);
    setLeverValue(key, 0);
    setLeverPickerOpen(false);
  };

  const toggleAllPeriods = () => {
    updateNodeData(selectedNode.id, {
      targetPeriods: targetPeriods.length > 0 ? undefined : [],
    });
  };

  const setStartPeriod = (val: string) => {
    const end = targetPeriods.length >= 2 ? targetPeriods[targetPeriods.length - 1] : MONTH_OPTIONS[MONTH_OPTIONS.length - 1].value;
    const range = MONTH_OPTIONS.filter((m) => m.value >= val && m.value <= end).map((m) => m.value);
    updateNodeData(selectedNode.id, { targetPeriods: range });
  };

  const setEndPeriod = (val: string) => {
    const start = targetPeriods.length >= 1 ? targetPeriods[0] : MONTH_OPTIONS[0].value;
    const range = MONTH_OPTIONS.filter((m) => m.value >= start && m.value <= val).map((m) => m.value);
    updateNodeData(selectedNode.id, { targetPeriods: range });
  };

  const showTargeting = data.kind === 'tool' || data.kind === 'formula' || data.kind === 'funding';

  // Levers that haven't been added yet
  const availableLeversLeft = AVAILABLE_LEVERS.filter((l) => !(l.key in driverOverrides));

  return (
    <div className="w-80 bg-gray-950 border-l border-gray-800 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-gray-200">{data.label}</div>
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">{data.kind}</div>
        </div>
        <button
          onClick={() => setPanelOpen(false)}
          className="p-1 hover:bg-gray-800 rounded text-gray-500"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Parameters */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">

        {/* ── Chip Parameters (existing) ──────────────────────────────── */}
        {data.kind === 'tool' && data.chipDef?.params && data.chipDef.params.length > 0 && (
          <div className="space-y-2">
            <div className={SECTION_LABEL}>Parameters</div>
            {data.chipDef.params.map((param) => (
              <div key={param.key}>
                <label className="block text-xs text-gray-400 mb-1">{param.label}</label>
                {param.type === 'select' && param.options ? (
                  <select
                    value={data.params[param.key] ?? param.default}
                    onChange={(e) => handleParamChange(param.key, e.target.value)}
                    className={INPUT_CLS}
                  >
                    {param.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                ) : param.type === 'number' || param.type === 'months' || param.type === 'percent' || param.type === 'currency' ? (
                  <input
                    type="number"
                    value={data.params[param.key] ?? param.default}
                    onChange={(e) => handleParamChange(param.key, Number(e.target.value))}
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    className={INPUT_MONO}
                  />
                ) : (
                  <input
                    type="text"
                    value={data.params[param.key] ?? param.default ?? ''}
                    onChange={(e) => handleParamChange(param.key, e.target.value)}
                    className={INPUT_CLS}
                    placeholder={param.label}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── Operator Config (existing) ──────────────────────────────── */}
        {data.kind === 'operator' && (
          <div className="space-y-2">
            <div className={SECTION_LABEL}>Operator Config</div>
            {data.operatorType === 'loop' && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Iterate over</label>
                <select
                  value={data.params.loopOver || 'scenarios'}
                  onChange={(e) => handleParamChange('loopOver', e.target.value)}
                  className={INPUT_CLS}
                >
                  <option value="scenarios">Scenarios</option>
                  <option value="companies">Companies</option>
                  <option value="periods">Periods</option>
                </select>
              </div>
            )}
            {data.operatorType === 'conditional' && (
              <>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Metric</label>
                  <input
                    type="text"
                    value={data.params.metric || ''}
                    onChange={(e) => handleParamChange('metric', e.target.value)}
                    className={INPUT_CLS}
                    placeholder="e.g. revenue, runway"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Operator</label>
                  <select
                    value={data.params.op || '>'}
                    onChange={(e) => handleParamChange('op', e.target.value)}
                    className={INPUT_CLS}
                  >
                    <option value=">">Greater than</option>
                    <option value="<">Less than</option>
                    <option value=">=">Greater or equal</option>
                    <option value="<=">Less or equal</option>
                    <option value="==">Equals</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Threshold</label>
                  <input
                    type="number"
                    value={data.params.threshold ?? 0}
                    onChange={(e) => handleParamChange('threshold', Number(e.target.value))}
                    className={INPUT_MONO}
                  />
                </div>
              </>
            )}
            {(data.operatorType === 'event_business' || data.operatorType === 'event_macro') && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Event description</label>
                <textarea
                  value={data.params.event || ''}
                  onChange={(e) => handleParamChange('event', e.target.value)}
                  rows={3}
                  className={`${INPUT_CLS} resize-none`}
                  placeholder="Describe the event..."
                />
              </div>
            )}
            {data.operatorType === 'event_funding' && (
              <>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Type</label>
                  <select
                    value={data.params.type || 'equity'}
                    onChange={(e) => handleParamChange('type', e.target.value)}
                    className={INPUT_CLS}
                  >
                    <option value="equity">Equity</option>
                    <option value="debt">Debt</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Amount</label>
                  <input
                    type="number"
                    value={data.params.amount || 0}
                    onChange={(e) => handleParamChange('amount', Number(e.target.value))}
                    className={INPUT_MONO}
                  />
                </div>
              </>
            )}
            {data.operatorType === 'filter' && (
              <>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Field</label>
                  <input
                    type="text"
                    value={data.params.field || ''}
                    onChange={(e) => handleParamChange('field', e.target.value)}
                    className={INPUT_CLS}
                    placeholder="e.g. revenue"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Value</label>
                  <input
                    type="number"
                    value={data.params.value ?? 0}
                    onChange={(e) => handleParamChange('value', Number(e.target.value))}
                    className={INPUT_MONO}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Formula (existing) ──────────────────────────────────────── */}
        {data.kind === 'formula' && (
          <div className="space-y-2">
            <div className={SECTION_LABEL}>Expression</div>
            <textarea
              value={data.params.expression || ''}
              onChange={(e) => handleParamChange('expression', e.target.value)}
              rows={3}
              className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-gray-500 resize-none"
              placeholder="revenue * 0.3 - opex"
            />
          </div>
        )}

        {/* ── Driver (existing) ───────────────────────────────────────── */}
        {data.kind === 'driver' && (
          <div className="space-y-2">
            <div className={SECTION_LABEL}>Override Value</div>
            <input
              type="number"
              value={data.params.value ?? 0}
              onChange={(e) => handleParamChange('value', Number(e.target.value))}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-purple-300 font-mono focus:outline-none focus:border-gray-500"
            />
          </div>
        )}

        {/* ── Output Format (existing) ────────────────────────────────── */}
        {data.kind === 'output' && (
          <div className="space-y-2">
            <div className={SECTION_LABEL}>Output Format</div>
            <select
              value={data.outputFormat || 'memo-section'}
              onChange={(e) => updateNodeData(selectedNode.id, { outputFormat: e.target.value as import('@/lib/workflow/types').OutputFormat })}
              className={INPUT_CLS}
            >
              <option value="memo-section">Memo Section</option>
              <option value="deck-slide">Deck Slide</option>
              <option value="chart">Chart</option>
              <option value="grid">Grid Write</option>
              <option value="table">Table</option>
              <option value="narrative">Narrative</option>
              <option value="export">Export (PDF/Excel)</option>
            </select>
          </div>
        )}

        {/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            NEW: Granular Targeting Sections
            Shown for tool, formula, and funding nodes
           ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}

        {showTargeting && (
          <>
            {/* ── A. Row / Subcategory Targeting ───────────────────────── */}
            <div className="pt-3 border-t border-gray-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className={SECTION_LABEL}>Target Rows</div>
                <button
                  onClick={() => setRowPickerOpen(!rowPickerOpen)}
                  className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              </div>

              {/* Selected rows as pills */}
              {targetRows.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {targetRows.map((row) => (
                    <span
                      key={row}
                      className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 bg-blue-500/15 text-blue-300 rounded-full border border-blue-500/20"
                    >
                      {formatRowPath(row)}
                      <button onClick={() => toggleTargetRow(row)} className="hover:text-blue-100">
                        <X className="w-2.5 h-2.5" />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] text-gray-600 italic">All rows (no filter)</div>
              )}

              {/* Row picker dropdown */}
              {rowPickerOpen && (
                <div className="bg-gray-900 border border-gray-700 rounded p-2 space-y-1 max-h-48 overflow-y-auto">
                  {PNL_ROWS.map((row) => (
                    <div key={row.id}>
                      {/* Parent row */}
                      <label className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-gray-800 cursor-pointer text-xs text-gray-300">
                        <input
                          type="checkbox"
                          checked={targetRows.includes(row.id)}
                          onChange={() => toggleTargetRow(row.id)}
                          className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-0 w-3 h-3"
                        />
                        {row.label}
                      </label>
                      {/* Subcategory children */}
                      {row.children.length > 0 && targetRows.includes(row.id) && (
                        <div className="ml-5 space-y-0.5">
                          {row.children.map((child) => {
                            const path = `${row.id}/${child}`;
                            return (
                              <label
                                key={path}
                                className="flex items-center gap-2 px-1.5 py-0.5 rounded hover:bg-gray-800 cursor-pointer text-[11px] text-gray-400"
                              >
                                <input
                                  type="checkbox"
                                  checked={targetRows.includes(path)}
                                  onChange={() => toggleTargetRow(path)}
                                  className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-0 w-3 h-3"
                                />
                                {child.charAt(0).toUpperCase() + child.slice(1)}
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Custom subcategory input */}
                  <div className="pt-1.5 mt-1.5 border-t border-gray-700">
                    <div className="flex gap-1">
                      <input
                        type="text"
                        value={customRowInput}
                        onChange={(e) => setCustomRowInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && addCustomRow()}
                        placeholder="Custom path (e.g. revenue/saas)"
                        className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-[11px] text-gray-300 focus:outline-none focus:border-gray-500"
                      />
                      <button
                        onClick={addCustomRow}
                        className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-[11px] text-gray-300"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* ── B. Period Targeting ──────────────────────────────────── */}
            <div className="pt-3 border-t border-gray-800 space-y-2">
              <div className={SECTION_LABEL}>Period Range</div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={targetPeriods.length === 0}
                  onChange={toggleAllPeriods}
                  className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-0 w-3 h-3"
                />
                <span className="text-xs text-gray-400">All periods</span>
              </label>

              {targetPeriods.length > 0 && (
                <div className="flex gap-2">
                  <div className="flex-1">
                    <label className="block text-[10px] text-gray-500 mb-1">From</label>
                    <select
                      value={targetPeriods[0] || ''}
                      onChange={(e) => setStartPeriod(e.target.value)}
                      className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-[11px] text-gray-300 focus:outline-none focus:border-gray-500"
                    >
                      {MONTH_OPTIONS.map((m) => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-[10px] text-gray-500 mb-1">To</label>
                    <select
                      value={targetPeriods[targetPeriods.length - 1] || ''}
                      onChange={(e) => setEndPeriod(e.target.value)}
                      className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-[11px] text-gray-300 focus:outline-none focus:border-gray-500"
                    >
                      {MONTH_OPTIONS.map((m) => (
                        <option key={m.value} value={m.value}>{m.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* ── C. Lever / Driver Overrides ─────────────────────────── */}
            <div className="pt-3 border-t border-gray-800 space-y-2">
              <div className="flex items-center justify-between">
                <div className={SECTION_LABEL}>Levers</div>
                {availableLeversLeft.length > 0 && (
                  <div className="relative">
                    <button
                      onClick={() => setLeverPickerOpen(!leverPickerOpen)}
                      className="text-[10px] text-purple-400 hover:text-purple-300 flex items-center gap-0.5"
                    >
                      <Plus className="w-3 h-3" /> Add
                    </button>
                    {leverPickerOpen && (
                      <div className="absolute right-0 top-5 z-50 bg-gray-900 border border-gray-700 rounded shadow-xl py-1 w-48 max-h-48 overflow-y-auto">
                        {availableLeversLeft.map((lever) => (
                          <button
                            key={lever.key}
                            onClick={() => addLever(lever.key)}
                            className="w-full text-left px-3 py-1.5 text-[11px] text-gray-300 hover:bg-gray-800 flex items-center justify-between"
                          >
                            <span>{lever.label}</span>
                            <span className="text-gray-600 text-[10px]">{lever.unit}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {Object.keys(driverOverrides).length > 0 ? (
                <div className="space-y-1.5">
                  {Object.entries(driverOverrides).map(([key, value]) => {
                    const lever = AVAILABLE_LEVERS.find((l) => l.key === key);
                    return (
                      <div key={key} className="flex items-center gap-1.5 group">
                        <span className="text-[11px] text-gray-400 flex-1 truncate">
                          {lever?.label || key}
                        </span>
                        <input
                          type="number"
                          value={value}
                          onChange={(e) => setLeverValue(key, Number(e.target.value))}
                          step={lever?.step || 1}
                          className="w-20 bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-[11px] text-purple-300 font-mono text-right focus:outline-none focus:border-purple-500"
                        />
                        <span className="text-[10px] text-gray-500 w-4">{lever?.unit || ''}</span>
                        <button
                          onClick={() => removeLever(key)}
                          className="p-0.5 text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-[10px] text-gray-600 italic">No lever overrides</div>
              )}
            </div>
          </>
        )}

        {/* ── Tool Result Summary ─────────────────────────────────────── */}
        {data.status === 'done' && data.result && data.kind === 'tool' && (
          <div className="pt-3 border-t border-gray-800">
            <div className={`${SECTION_LABEL} mb-2`}>Result</div>

            {data.result.forecast && Array.isArray(data.result.forecast) && (
              <div className="space-y-2">
                <div className="text-xs text-emerald-400 font-medium">
                  {data.result.method?.replace('_', ' ').toUpperCase()} — {data.result.months || data.result.forecast.length} months
                </div>
                {data.result.explanation && (
                  <div className="text-xs text-gray-400 leading-relaxed">
                    {(data.result.explanation as string).slice(0, 200)}{(data.result.explanation as string).length > 200 ? '...' : ''}
                  </div>
                )}
                {(() => {
                  const last = data.result.forecast[data.result.forecast.length - 1];
                  if (!last) return null;
                  const fmt = (n: number) => n >= 1e6 ? `$${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n/1e3).toFixed(0)}K` : `$${n.toFixed(0)}`;
                  return (
                    <div className="grid grid-cols-2 gap-1 text-[10px]">
                      {last.revenue != null && <div className="text-gray-400">Revenue: <span className="text-gray-200 font-mono">{fmt(last.revenue)}</span></div>}
                      {last.ebitda != null && <div className="text-gray-400">EBITDA: <span className={`font-mono ${last.ebitda >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmt(last.ebitda)}</span></div>}
                      {last.cash_balance != null && <div className="text-gray-400">Cash: <span className="text-gray-200 font-mono">{fmt(last.cash_balance)}</span></div>}
                      {last.runway_months != null && <div className="text-gray-400">Runway: <span className={`font-mono ${last.runway_months > 12 ? 'text-emerald-400' : 'text-amber-400'}`}>{last.runway_months.toFixed(0)}mo</span></div>}
                    </div>
                  );
                })()}
                {data.result.grid_suggestions?.length > 0 && (
                  <div className="text-[10px] text-blue-400">{data.result.grid_suggestions.length} grid cells ready to update</div>
                )}
                {data.result.chart_data?.length > 0 && (
                  <div className="text-[10px] text-purple-400">{data.result.chart_data.length} charts generated</div>
                )}
              </div>
            )}

            {data.result.branch && (
              <div className="space-y-1">
                <div className="text-xs text-purple-400 font-medium">Branch: {data.result.branch.name}</div>
                {data.result.branch.assumptions && (
                  <div className="text-[10px] text-gray-400">
                    {Object.entries(data.result.branch.assumptions).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(', ')}
                  </div>
                )}
              </div>
            )}

            {data.result.pnl_rows && (
              <div className="text-xs text-emerald-400 font-medium">
                P&L: {data.result.pnl_rows.length} rows, {data.result.periods?.length || 0} periods
              </div>
            )}

            {data.result.variance && (
              <div className="text-xs text-amber-400 font-medium">
                Variance analysis: {typeof data.result.variance === 'object' ? Object.keys(data.result.variance).length : 0} categories
              </div>
            )}

            {!data.result.forecast && !data.result.branch && !data.result.pnl_rows && !data.result.variance && (
              <pre className="text-[10px] text-gray-500 bg-gray-900 rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {JSON.stringify(data.result, null, 2).slice(0, 500)}
              </pre>
            )}

            {data.result.persisted && (
              <div className="text-[10px] text-emerald-600 mt-1">Saved to DB</div>
            )}
          </div>
        )}

        {/* ── Output Node Result Viewer ────────────────────────────────── */}
        {data.status === 'done' && data.result && data.kind === 'output' && (
          <div className="pt-3 border-t border-gray-800">
            <div className={`${SECTION_LABEL} mb-2`}>Output</div>

            {data.outputFormat === 'chart' && data.result?.chart_config && (
              <div className="text-xs text-emerald-400 mb-1">
                Chart: {data.result.chart_config.chart_type || 'chart'} ready
              </div>
            )}

            {data.outputFormat === 'memo-section' && data.result?.sections && (
              <div className="space-y-1.5">
                {(data.result.sections as any[]).map((sec: any, i: number) => (
                  <div key={i} className="text-xs">
                    {sec.type === 'heading2' && (
                      <div className="font-semibold text-gray-200">{sec.content}</div>
                    )}
                    {sec.type === 'paragraph' && (
                      <div className="text-gray-400 leading-relaxed">{(sec.content as string).slice(0, 200)}{sec.content.length > 200 ? '...' : ''}</div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {data.outputFormat === 'grid' && (
              <div className="text-xs text-emerald-400">Grid update ready</div>
            )}

            {!['chart', 'memo-section', 'grid'].includes(data.outputFormat || '') && (
              <pre className="text-[10px] text-gray-500 bg-gray-900 rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap">
                {JSON.stringify(data.result, null, 2).slice(0, 500)}
              </pre>
            )}
          </div>
        )}

        {/* Error display */}
        {data.status === 'error' && data.error && (
          <div className="pt-3 border-t border-gray-800">
            <div className="text-[10px] text-red-400 uppercase tracking-wider font-semibold mb-1">Error</div>
            <div className="text-xs text-red-300 bg-red-950/30 rounded p-2">{data.error}</div>
          </div>
        )}

        {/* Node info */}
        <div className="pt-3 border-t border-gray-800">
          <div className={`${SECTION_LABEL} mb-2`}>Info</div>
          <div className="text-xs text-gray-500">ID: {selectedNode.id}</div>
          {data.chipDef?.description && (
            <div className="text-xs text-gray-400 mt-1">{data.chipDef.description}</div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div className="px-4 py-3 border-t border-gray-800">
        <button
          onClick={() => removeNode(selectedNode.id)}
          className="w-full px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 rounded border border-red-500/20 transition-colors"
        >
          Delete Node
        </button>
      </div>
    </div>
  );
}
