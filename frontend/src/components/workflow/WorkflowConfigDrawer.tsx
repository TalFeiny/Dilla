'use client';

import { useMemo, useCallback, useRef } from 'react';
import { useWorkflowStore } from '@/lib/workflow/store';
import type { WorkflowNodeData, OutputFormat } from '@/lib/workflow/types';
import { portTypeLabel, PORT_COLORS } from '@/lib/workflow/port-types';
import { getUpstreamFieldsFlat, type FieldOption } from '@/lib/workflow/upstream-fields';
import { resolveIcon } from './nodes/icon-resolver';
import { DriverNodeConfig } from './config/DriverNodeConfig';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';

// ── Color map for accent in header ──────────────────────────────────────────

const HEADER_COLORS: Record<string, string> = {
  emerald: 'text-emerald-400', blue: 'text-blue-400', amber: 'text-amber-400',
  purple: 'text-purple-400', indigo: 'text-indigo-400', red: 'text-red-400',
  cyan: 'text-cyan-400', slate: 'text-slate-400', teal: 'text-teal-400',
  violet: 'text-violet-400', lime: 'text-lime-400', sky: 'text-sky-400',
  pink: 'text-pink-400', zinc: 'text-zinc-400', fuchsia: 'text-fuchsia-400',
  rose: 'text-rose-400', orange: 'text-orange-400', yellow: 'text-yellow-400',
  gray: 'text-gray-400',
};

// ── Config Drawer ───────────────────────────────────────────────────────────

export function WorkflowConfigDrawer() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const edges = useWorkflowStore((s) => s.edges);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const isPanelOpen = useWorkflowStore((s) => s.isPanelOpen);
  const setPanelOpen = useWorkflowStore((s) => s.setPanelOpen);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const removeNode = useWorkflowStore((s) => s.removeNode);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId),
    [nodes, selectedNodeId]
  );

  const data = selectedNode ? (selectedNode.data as unknown as WorkflowNodeData) : null;

  // Compute port connection status for this node
  const portConnections = useMemo(() => {
    if (!selectedNode || !data) return { inputs: new Map<string, string>(), outputs: new Map<string, string[]>() };
    const inputs = new Map<string, string>();
    const outputs = new Map<string, string[]>();
    for (const edge of edges) {
      if (edge.target === selectedNode.id && edge.targetHandle) {
        const srcNode = nodes.find((n) => n.id === edge.source);
        inputs.set(edge.targetHandle as string, (srcNode?.data as any)?.label || edge.source);
      }
      if (edge.source === selectedNode.id && edge.sourceHandle) {
        const handle = edge.sourceHandle as string;
        const tgtNode = nodes.find((n) => n.id === edge.target);
        const existing = outputs.get(handle) || [];
        existing.push((tgtNode?.data as any)?.label || edge.target);
        outputs.set(handle, existing);
      }
    }
    return { inputs, outputs };
  }, [selectedNode, data, edges, nodes]);

  // Get available fields from upstream nodes (for field picker dropdowns)
  const upstreamFields = useMemo(() => {
    if (!selectedNode) return [];
    return getUpstreamFieldsFlat(selectedNode.id, nodes, edges);
  }, [selectedNode, nodes, edges]);

  const handleParamChange = (key: string, value: any) => {
    if (!selectedNode || !data) return;
    updateNodeData(selectedNode.id, {
      params: { ...data.params, [key]: value },
    });
  };

  const handleDelete = () => {
    if (!selectedNode) return;
    removeNode(selectedNode.id);
    setPanelOpen(false);
  };

  const Icon = data ? resolveIcon(data.icon) : null;
  const colorClass = data ? (HEADER_COLORS[data.color] || 'text-gray-400') : '';

  return (
    <Sheet open={isPanelOpen && !!data} onOpenChange={setPanelOpen}>
      <SheetContent
        side="right"
        className="w-[400px] sm:max-w-[400px] bg-gray-950 border-gray-800 p-0 flex flex-col"
      >
        {data && selectedNode && (
          <>
            {/* Header */}
            <SheetHeader className="px-6 pt-6 pb-4 border-b border-gray-800">
              <SheetTitle className="flex items-center gap-3 text-gray-200">
                {Icon && <Icon className={`w-5 h-5 ${colorClass}`} />}
                {data.label}
              </SheetTitle>
              <SheetDescription className="text-gray-500">
                {data.chipDef?.description || getKindDescription(data)}
              </SheetDescription>
            </SheetHeader>

            {/* Parameters */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

              {/* ── Instructions (LLM-based nodes only) ───────────── */}
              {(data.kind === 'tool' || data.kind === 'funding') && (
                <Field label="Instructions (optional)">
                  <textarea
                    value={data.params.instructions || ''}
                    onChange={(e) => handleParamChange('instructions', e.target.value)}
                    rows={2}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-blue-300 focus:outline-none focus:border-blue-500/50 resize-y"
                    placeholder={getInstructionPlaceholder(data)}
                  />
                </Field>
              )}

              {/* ── Data In / Out ──────────────────────────────────── */}
              {(data.inputPorts?.length || data.outputPorts?.length) ? (
                <div className="pt-2 pb-1 border-t border-gray-800">
                  <SectionLabel>Data Flow</SectionLabel>
                  <div className="space-y-2 mt-2">
                    {data.inputPorts?.map((port) => {
                      const connectedLabel = portConnections.inputs.get(port.id);
                      return (
                        <div key={port.id} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 w-6">IN</span>
                          <span
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-1 ring-gray-700"
                            style={{ backgroundColor: connectedLabel ? PORT_COLORS[port.dataType] : '#1f2937' }}
                          />
                          <span className="text-xs text-gray-300">{port.label}</span>
                          <span className="text-[10px] text-gray-600 px-1.5 py-0.5 bg-gray-800 rounded">{port.dataType}</span>
                          {connectedLabel ? (
                            <span className="ml-auto text-xs text-emerald-400 truncate max-w-[100px]">{connectedLabel}</span>
                          ) : port.required ? (
                            <span className="ml-auto text-[10px] text-red-400 px-1.5 py-0.5 bg-red-500/10 rounded">required</span>
                          ) : (
                            <span className="ml-auto text-[10px] text-gray-600">optional</span>
                          )}
                        </div>
                      );
                    })}
                    {data.outputPorts?.map((port) => {
                      const targets = portConnections.outputs.get(port.id);
                      return (
                        <div key={port.id} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 w-6">OUT</span>
                          <span
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0 ring-1 ring-gray-700"
                            style={{ backgroundColor: targets?.length ? PORT_COLORS[port.dataType] : '#1f2937' }}
                          />
                          <span className="text-xs text-gray-300">{port.label}</span>
                          <span className="text-[10px] text-gray-600 px-1.5 py-0.5 bg-gray-800 rounded">{port.dataType}</span>
                          {targets?.length ? (
                            <span className="ml-auto text-xs text-sky-400 truncate max-w-[100px]">{targets.join(', ')}</span>
                          ) : (
                            <span className="ml-auto text-[10px] text-gray-600">unconnected</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {/* ── Trigger config ─────────────────────────────────── */}
              {data.kind === 'trigger' && (
                <TriggerConfig data={data} nodeId={selectedNode.id} onParamChange={handleParamChange} updateNodeData={updateNodeData} />
              )}

              {/* ── Tool config ────────────────────────────────────── */}
              {data.kind === 'tool' && data.chipDef?.params && data.chipDef.params.length > 0 && (
                <>
                  <SectionLabel>Parameters</SectionLabel>
                  {data.chipDef.params.map((param) => (
                    <Field key={param.key} label={param.label}>
                      {param.type === 'select' && param.options ? (
                        <select
                          value={data.params[param.key] ?? param.default}
                          onChange={(e) => handleParamChange(param.key, e.target.value)}
                          className={selectClass}
                        >
                          {param.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
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
                          className={`${inputClass} font-mono`}
                        />
                      ) : (
                        <input
                          type="text"
                          value={data.params[param.key] ?? param.default ?? ''}
                          onChange={(e) => handleParamChange(param.key, e.target.value)}
                          className={inputClass}
                          placeholder={param.label}
                        />
                      )}
                    </Field>
                  ))}
                </>
              )}

              {/* ── Operator config ────────────────────────────────── */}
              {data.kind === 'operator' && (
                <>
                  <SectionLabel>Operator Config</SectionLabel>
                  {data.operatorType === 'loop' && (
                    <>
                      <Field label="Iterate over">
                        <select
                          value={data.params.loopOver || 'scenarios'}
                          onChange={(e) => handleParamChange('loopOver', e.target.value)}
                          className={selectClass}
                        >
                          <option value="scenarios">Scenarios</option>
                          <option value="companies">Companies</option>
                          <option value="periods">Periods</option>
                        </select>
                      </Field>
                      <Field label="Loop variable name">
                        <input
                          type="text"
                          value={data.params.variable || 'item'}
                          onChange={(e) => handleParamChange('variable', e.target.value)}
                          className={`${inputClass} font-mono`}
                          placeholder="item"
                        />
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'conditional' && (
                    <>
                      <FieldPicker
                        label="Check field"
                        value={data.params.metric || ''}
                        onChange={(v) => handleParamChange('metric', v)}
                        fields={upstreamFields}
                        placeholder="e.g. revenue, runway_months"
                      />
                      <Field label="Condition">
                        <select
                          value={data.params.op || '>'}
                          onChange={(e) => handleParamChange('op', e.target.value)}
                          className={selectClass}
                        >
                          <option value=">">is greater than</option>
                          <option value="<">is less than</option>
                          <option value=">=">is at least</option>
                          <option value="<=">is at most</option>
                          <option value="==">equals</option>
                          <option value="!=">does not equal</option>
                        </select>
                      </Field>
                      <Field label="Value">
                        <input
                          type="number"
                          value={data.params.threshold ?? 0}
                          onChange={(e) => handleParamChange('threshold', Number(e.target.value))}
                          className={`${inputClass} font-mono`}
                        />
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'switch' && (
                    <>
                      <FieldPicker
                        label="Switch on field"
                        value={data.params.field || ''}
                        onChange={(v) => handleParamChange('field', v)}
                        fields={upstreamFields}
                        placeholder="e.g. category, status"
                      />
                      <Field label="Cases (comma-separated values)">
                        <input
                          type="text"
                          value={Array.isArray(data.params.cases) ? data.params.cases.map((c: any) => c.value || c).join(', ') : ''}
                          onChange={(e) => handleParamChange('cases', e.target.value.split(',').map((v: string) => ({ value: v.trim(), label: v.trim() })).filter((c: any) => c.value))}
                          className={inputClass}
                          placeholder="e.g. high, medium, low"
                        />
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'filter' && (
                    <>
                      <FieldPicker
                        label="Filter on field"
                        value={data.params.field || ''}
                        onChange={(v) => handleParamChange('field', v)}
                        fields={upstreamFields}
                        placeholder="e.g. revenue, category"
                      />
                      <Field label="Operator">
                        <select
                          value={data.params.op || '>'}
                          onChange={(e) => handleParamChange('op', e.target.value)}
                          className={selectClass}
                        >
                          <option value=">">Greater than</option>
                          <option value="<">Less than</option>
                          <option value="==">Equals</option>
                          <option value=">=">Greater or equal</option>
                          <option value="<=">Less or equal</option>
                          <option value="contains">Contains</option>
                        </select>
                      </Field>
                      <Field label="Value">
                        <input
                          type="text"
                          value={data.params.value ?? ''}
                          onChange={(e) => {
                            const num = Number(e.target.value);
                            handleParamChange('value', isNaN(num) ? e.target.value : num);
                          }}
                          className={`${inputClass} font-mono`}
                          placeholder="e.g. 100000 or 'SaaS'"
                        />
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'aggregate' && (
                    <>
                      <Field label="Function">
                        <select
                          value={data.params.fn || 'sum'}
                          onChange={(e) => handleParamChange('fn', e.target.value)}
                          className={selectClass}
                        >
                          <option value="sum">Sum</option>
                          <option value="avg">Average</option>
                          <option value="median">Median</option>
                          <option value="min">Min</option>
                          <option value="max">Max</option>
                          <option value="count">Count</option>
                        </select>
                      </Field>
                      <FieldPicker
                        label="Field"
                        value={data.params.field || ''}
                        onChange={(v) => handleParamChange('field', v)}
                        fields={upstreamFields}
                        placeholder="e.g. revenue, ebitda"
                      />
                      <FieldPicker
                        label="Group by (optional)"
                        value={data.params.groupBy || ''}
                        onChange={(v) => handleParamChange('groupBy', v)}
                        fields={upstreamFields}
                        placeholder="e.g. category, month"
                      />
                    </>
                  )}
                  {data.operatorType === 'map' && (
                    <>
                      <Field label="Expression">
                        <textarea
                          value={data.params.expression || ''}
                          onChange={(e) => handleParamChange('expression', e.target.value)}
                          rows={3}
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-gray-500 resize-none"
                          placeholder="e.g. item.revenue * 1.1"
                        />
                      </Field>
                      <Field label="Output field name (optional)">
                        <input
                          type="text"
                          value={data.params.outputField || ''}
                          onChange={(e) => handleParamChange('outputField', e.target.value)}
                          className={`${inputClass} font-mono`}
                          placeholder="e.g. adjusted_revenue"
                        />
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'merge' && (
                    <>
                      <Field label="Strategy">
                        <select
                          value={data.params.strategy || 'concat'}
                          onChange={(e) => handleParamChange('strategy', e.target.value)}
                          className={selectClass}
                        >
                          <option value="concat">Concatenate</option>
                          <option value="zip">Zip (pair by index)</option>
                          <option value="join">Join on key</option>
                        </select>
                      </Field>
                      {data.params.strategy === 'join' && (
                        <Field label="Join key">
                          <input
                            type="text"
                            value={data.params.joinKey || ''}
                            onChange={(e) => handleParamChange('joinKey', e.target.value)}
                            className={`${inputClass} font-mono`}
                            placeholder="e.g. month, company_id"
                          />
                        </Field>
                      )}
                    </>
                  )}
                  {data.operatorType === 'transform' && (
                    <>
                      <Field label="Mapping expression">
                        <textarea
                          value={data.params.mapping || ''}
                          onChange={(e) => handleParamChange('mapping', e.target.value)}
                          rows={3}
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-gray-500 resize-none"
                          placeholder="Describe how to reshape the data..."
                        />
                      </Field>
                      <Field label="Output type">
                        <select
                          value={data.params.outputType || 'any'}
                          onChange={(e) => handleParamChange('outputType', e.target.value)}
                          className={selectClass}
                        >
                          <option value="any">Auto</option>
                          <option value="forecast">Forecast</option>
                          <option value="table">Table</option>
                          <option value="scenario">Scenario</option>
                          <option value="number">Number</option>
                        </select>
                      </Field>
                    </>
                  )}
                  {data.operatorType === 'prior' && (
                    <>
                      <FieldPicker
                        label="Parameter"
                        value={data.params.parameter || ''}
                        onChange={(v) => handleParamChange('parameter', v)}
                        fields={upstreamFields}
                        placeholder="e.g. revenue_growth, churn_rate"
                      />
                      <Field label="Distribution">
                        <select
                          value={data.params.distribution || 'normal'}
                          onChange={(e) => handleParamChange('distribution', e.target.value)}
                          className={selectClass}
                        >
                          <option value="normal">Normal</option>
                          <option value="lognormal">Log-Normal</option>
                          <option value="uniform">Uniform</option>
                        </select>
                      </Field>
                      <Field label="Low bound">
                        <input
                          type="number"
                          value={data.params.low ?? 0}
                          onChange={(e) => handleParamChange('low', Number(e.target.value))}
                          className={`${inputClass} font-mono`}
                        />
                      </Field>
                      <Field label="High bound">
                        <input
                          type="number"
                          value={data.params.high ?? 0}
                          onChange={(e) => handleParamChange('high', Number(e.target.value))}
                          className={`${inputClass} font-mono`}
                        />
                      </Field>
                    </>
                  )}
                  {(data.operatorType === 'event_business' || data.operatorType === 'event_macro') && (
                    <Field label={data.operatorType === 'event_macro' ? 'What happens?' : 'What happens?'}>
                      <textarea
                        value={data.params.event || ''}
                        onChange={(e) => handleParamChange('event', e.target.value)}
                        rows={4}
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500 resize-none"
                        placeholder={data.operatorType === 'event_macro'
                          ? 'e.g. Fed raises rates 75bps, tariffs on EU imports, recession hits Q3...'
                          : 'e.g. Key engineer leaves, launch product in APAC, lose biggest client...'}
                      />
                    </Field>
                  )}
                  {data.operatorType === 'event_funding' && (
                    <Field label="Describe the raise">
                      <textarea
                        value={data.params.event || ''}
                        onChange={(e) => handleParamChange('event', e.target.value)}
                        rows={3}
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500 resize-none"
                        placeholder="e.g. Series A $8M at $40M pre, bridge note $500K, venture debt $2M at 12%..."
                      />
                    </Field>
                  )}
                </>
              )}

              {/* ── Formula config ─────────────────────────────────── */}
              {data.kind === 'formula' && (
                <>
                  <SectionLabel>Expression</SectionLabel>
                  <textarea
                    value={data.params.expression || ''}
                    onChange={(e) => handleParamChange('expression', e.target.value)}
                    rows={4}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-gray-500 resize-none"
                    placeholder="revenue * 0.3 - opex"
                  />
                </>
              )}

              {/* ── Driver config (assumption-driven) ────────────── */}
              {data.kind === 'driver' && (
                <DriverNodeConfig nodeId={selectedNode.id} data={data} />
              )}

              {/* ── Output config ──────────────────────────────────── */}
              {data.kind === 'output' && (
                <>
                  <SectionLabel>Output Settings</SectionLabel>
                  <Field label="Title">
                    <input
                      type="text"
                      value={data.params.title || ''}
                      onChange={(e) => handleParamChange('title', e.target.value)}
                      className={inputClass}
                      placeholder="e.g. Revenue Forecast Summary"
                    />
                  </Field>
                  <Field label="Format">
                    <select
                      value={data.outputFormat || 'memo-section'}
                      onChange={(e) => updateNodeData(selectedNode.id, { outputFormat: e.target.value as OutputFormat })}
                      className={selectClass}
                    >
                      <option value="memo-section">Memo Section</option>
                      <option value="deck-slide">Deck Slide</option>
                      <option value="chart">Chart</option>
                      <option value="grid">Grid Write</option>
                      <option value="table">Table</option>
                      <option value="narrative">Narrative</option>
                      <option value="export">Export (PDF/Excel)</option>
                    </select>
                  </Field>
                  <Field label="Description (optional)">
                    <textarea
                      value={data.params.description || ''}
                      onChange={(e) => handleParamChange('description', e.target.value)}
                      rows={2}
                      className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500 resize-none"
                      placeholder="What should this output contain?"
                    />
                  </Field>
                </>
              )}

              {/* ── Funding config ─────────────────────────────────── */}
              {data.kind === 'funding' && data.chipDef?.params && data.chipDef.params.length > 0 && (
                <>
                  <SectionLabel>Funding Parameters</SectionLabel>
                  {data.chipDef.params.map((param) => (
                    <Field key={param.key} label={param.label}>
                      {param.type === 'select' && param.options ? (
                        <select
                          value={data.params[param.key] ?? param.default}
                          onChange={(e) => handleParamChange(param.key, e.target.value)}
                          className={selectClass}
                        >
                          {param.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="number"
                          value={data.params[param.key] ?? param.default}
                          onChange={(e) => handleParamChange(param.key, Number(e.target.value))}
                          min={param.min}
                          max={param.max}
                          step={param.step}
                          className={`${inputClass} font-mono`}
                        />
                      )}
                    </Field>
                  ))}
                </>
              )}

              {/* ── Result summary ─────────────────────────────────── */}
              {data.status === 'done' && data.result && (
                <div className="pt-4 border-t border-gray-800">
                  <SectionLabel>Result</SectionLabel>
                  <ResultSummary data={data} />
                </div>
              )}

              {/* ── Error display ──────────────────────────────────── */}
              {data.status === 'error' && data.error && (
                <div className="pt-4 border-t border-gray-800">
                  <div className="text-xs text-red-400 font-semibold uppercase tracking-wider mb-1">Error</div>
                  <div className="text-sm text-red-300 bg-red-950/30 rounded-lg p-3">{data.error}</div>
                </div>
              )}

              {/* ── Node info ──────────────────────────────────────── */}
              <div className="pt-4 border-t border-gray-800">
                <SectionLabel>Info</SectionLabel>
                <div className="text-xs text-gray-500">ID: {selectedNode.id}</div>
                <div className="text-xs text-gray-500 mt-1 capitalize">Kind: {data.kind}</div>
                {data.durationMs !== undefined && (
                  <div className="text-xs text-gray-500 mt-1">Duration: {(data.durationMs / 1000).toFixed(1)}s</div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-800">
              <button
                onClick={handleDelete}
                className="w-full px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg border border-red-500/20 transition-colors"
              >
                Delete Node
              </button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

// ── Helper components ───────────────────────────────────────────────────────

const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500';
const selectClass = 'w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-gray-500';

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold">{children}</div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function getInstructionPlaceholder(data: WorkflowNodeData): string {
  if (data.kind === 'funding') return 'e.g. Model a Series A at $40M pre-money...';
  if (data.chipDef?.description) return `e.g. ${data.chipDef.description}`;
  return 'Optional instructions for the AI when running this tool...';
}

// ── Field Picker — dropdown from upstream data, fallback to text input ───────

function FieldPicker({
  label,
  value,
  onChange,
  fields,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  fields: FieldOption[];
  placeholder: string;
}) {
  // If upstream fields are available, show a dropdown with them
  if (fields.length > 0) {
    return (
      <Field label={label}>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={selectClass}
        >
          <option value="">Select a field...</option>
          {fields.map((f) => (
            <option key={f.path} value={f.path}>
              {f.label} — {f.preview}
            </option>
          ))}
        </select>
        {/* Also allow typing a custom value */}
        {value && !fields.some((f) => f.path === value) && (
          <div className="mt-1 text-[10px] text-amber-500">Custom: {value}</div>
        )}
      </Field>
    );
  }

  // Fallback: text input when no upstream data available yet
  return (
    <Field label={label}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
        placeholder={placeholder}
      />
      <div className="mt-1 text-[10px] text-gray-600">Run upstream nodes to see available fields</div>
    </Field>
  );
}

// ── Trigger Config — handles all trigger types ───────────────────────────────

function TriggerConfig({
  data,
  nodeId,
  onParamChange,
  updateNodeData,
}: {
  data: WorkflowNodeData;
  nodeId: string;
  onParamChange: (key: string, value: any) => void;
  updateNodeData: (id: string, updates: Partial<WorkflowNodeData>) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const triggerType = data.triggerType || 'manual';

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      if (file.name.endsWith('.csv')) {
        // Parse CSV into rows
        const lines = text.split('\n').filter((l) => l.trim());
        const headers = lines[0]?.split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
        const rows = lines.slice(1).map((line) => {
          const vals = line.split(',').map((v) => v.trim().replace(/^"|"$/g, ''));
          const row: Record<string, string> = {};
          headers?.forEach((h, i) => { row[h] = vals[i] || ''; });
          return row;
        });
        onParamChange('fileName', file.name);
        onParamChange('headers', headers);
        onParamChange('rowCount', rows.length);
        // Store parsed data as the trigger's output
        updateNodeData(nodeId, {
          result: { table: rows, headers, row_count: rows.length },
          status: 'done',
          params: { ...data.params, fileName: file.name, headers, rowCount: rows.length },
        } as any);
      } else {
        // Non-CSV file — store metadata, actual processing happens on execution
        onParamChange('fileName', file.name);
        onParamChange('fileSize', file.size);
        onParamChange('fileType', file.type);
      }
    };
    reader.readAsText(file);
  }, [data.params, nodeId, onParamChange, updateNodeData]);

  return (
    <>
      <SectionLabel>Trigger Settings</SectionLabel>

      {triggerType === 'manual' && (
        <div className="text-xs text-gray-500">Click the Run button to start this workflow.</div>
      )}

      {triggerType === 'schedule' && (
        <>
          <Field label="Schedule (cron)">
            <input
              type="text"
              value={data.params.cron || ''}
              onChange={(e) => onParamChange('cron', e.target.value)}
              className={inputClass}
              placeholder="0 9 * * 1"
            />
          </Field>
          <div className="text-[10px] text-gray-600 space-y-0.5">
            <div>min hour day month weekday</div>
            <div>e.g. <span className="text-gray-400">0 9 * * 1</span> = Every Monday at 9am</div>
          </div>
        </>
      )}

      {triggerType === 'csv_upload' && (
        <>
          <Field label="Upload CSV">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.xlsx"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full px-3 py-3 border-2 border-dashed border-gray-700 rounded-lg text-sm text-gray-400 hover:border-emerald-500/50 hover:text-emerald-400 transition-colors"
            >
              {data.params.fileName ? (
                <span className="text-emerald-400">{data.params.fileName}</span>
              ) : (
                'Click to upload CSV or drop a file'
              )}
            </button>
          </Field>
          {data.params.headers && (
            <div className="space-y-1">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Columns detected</div>
              <div className="flex flex-wrap gap-1">
                {(data.params.headers as string[]).map((h: string) => (
                  <span key={h} className="text-[10px] px-1.5 py-0.5 bg-gray-800 text-gray-300 rounded">{h}</span>
                ))}
              </div>
              <div className="text-[10px] text-gray-600">{data.params.rowCount} rows</div>
            </div>
          )}
        </>
      )}

      {triggerType === 'cell_input' && (
        <>
          <Field label="Source page">
            <select
              value={data.params.sourcePage || 'pnl'}
              onChange={(e) => onParamChange('sourcePage', e.target.value)}
              className={selectClass}
            >
              <option value="pnl">P&L</option>
              <option value="legal">Legal</option>
            </select>
          </Field>
          <Field label="Row / metric">
            <input
              type="text"
              value={data.params.sourceRow || ''}
              onChange={(e) => onParamChange('sourceRow', e.target.value)}
              className={inputClass}
              placeholder="e.g. revenue, opex, ebitda"
            />
          </Field>
          <Field label="Period (optional)">
            <input
              type="text"
              value={data.params.sourcePeriod || ''}
              onChange={(e) => onParamChange('sourcePeriod', e.target.value)}
              className={inputClass}
              placeholder="e.g. 2025-03 or leave blank for all"
            />
          </Field>
        </>
      )}

      {triggerType === 'document_upload' && (
        <>
          <Field label="Upload document">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.xlsx,.txt"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full px-3 py-3 border-2 border-dashed border-gray-700 rounded-lg text-sm text-gray-400 hover:border-blue-500/50 hover:text-blue-400 transition-colors"
            >
              {data.params.fileName ? (
                <span className="text-blue-400">{data.params.fileName}</span>
              ) : (
                'Click to upload PDF, DOCX, or Excel'
              )}
            </button>
          </Field>
          <Field label="Document type">
            <select
              value={data.params.documentType || 'financial_statement'}
              onChange={(e) => onParamChange('documentType', e.target.value)}
              className={selectClass}
            >
              <option value="financial_statement">Financial Statement</option>
              <option value="pitch_deck">Pitch Deck</option>
              <option value="term_sheet">Term Sheet</option>
              <option value="due_diligence">Due Diligence Report</option>
              <option value="contract">Contract / Agreement</option>
              <option value="investment_memo">Investment Memo</option>
              <option value="other">Other</option>
            </select>
          </Field>
          {data.params.fileName && (
            <div className="text-[10px] text-gray-600">
              {data.params.fileSize ? `${(data.params.fileSize / 1024).toFixed(0)} KB` : ''}
              {data.params.fileType ? ` · ${data.params.fileType}` : ''}
            </div>
          )}
        </>
      )}
    </>
  );
}

function getKindDescription(data: WorkflowNodeData): string {
  switch (data.kind) {
    case 'trigger': return 'Entry point that starts the workflow execution.';
    case 'tool': return 'Executes a backend analysis or computation tool.';
    case 'funding': return 'Models an equity or debt funding event.';
    case 'driver': return 'Overrides a single assumption for downstream nodes.';
    case 'operator': return 'Controls execution flow — branching, looping, or data transformation.';
    case 'formula': return 'Evaluates an inline mathematical expression.';
    case 'output': return 'Routes results to an output format (chart, memo, grid, etc.).';
    default: return '';
  }
}

function ResultSummary({ data }: { data: WorkflowNodeData }) {
  const result = data.result;
  if (!result) return null;

  const fmt = (n: number) => n >= 1e6 ? `$${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n/1e3).toFixed(0)}K` : `$${n.toFixed(0)}`;

  // Forecast result
  if (result.forecast && Array.isArray(result.forecast)) {
    const last = result.forecast[result.forecast.length - 1];
    return (
      <div className="space-y-2 text-sm">
        <div className="text-emerald-400 font-medium">
          {result.method?.replace('_', ' ').toUpperCase()} — {result.months || result.forecast.length} months
        </div>
        {last && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            {last.revenue != null && <div className="text-gray-400">Revenue: <span className="text-gray-200 font-mono">{fmt(last.revenue)}</span></div>}
            {last.ebitda != null && <div className="text-gray-400">EBITDA: <span className={`font-mono ${last.ebitda >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{fmt(last.ebitda)}</span></div>}
            {last.cash_balance != null && <div className="text-gray-400">Cash: <span className="text-gray-200 font-mono">{fmt(last.cash_balance)}</span></div>}
            {last.runway_months != null && <div className="text-gray-400">Runway: <span className={`font-mono ${last.runway_months > 12 ? 'text-emerald-400' : 'text-amber-400'}`}>{last.runway_months.toFixed(0)}mo</span></div>}
          </div>
        )}
      </div>
    );
  }

  // Branch result
  if (result.branch) {
    return (
      <div className="text-sm text-purple-400 font-medium">Branch: {result.branch.name}</div>
    );
  }

  // P&L result
  if (result.pnl_rows) {
    return (
      <div className="text-sm text-emerald-400 font-medium">
        P&L: {result.pnl_rows.length} rows, {result.periods?.length || 0} periods
      </div>
    );
  }

  // Fallback
  return (
    <pre className="text-xs text-gray-500 bg-gray-900 rounded-lg p-3 max-h-40 overflow-y-auto whitespace-pre-wrap">
      {JSON.stringify(result, null, 2).slice(0, 500)}
    </pre>
  );
}
