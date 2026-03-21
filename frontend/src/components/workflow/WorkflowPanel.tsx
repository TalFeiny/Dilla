'use client';

import { useMemo } from 'react';
import { X } from 'lucide-react';
import { useWorkflowStore } from '@/lib/workflow/store';
import type { WorkflowNodeData } from '@/lib/workflow/types';

export function WorkflowPanel() {
  const nodes = useWorkflowStore((s) => s.nodes);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const updateNodeData = useWorkflowStore((s) => s.updateNodeData);
  const removeNode = useWorkflowStore((s) => s.removeNode);
  const setPanelOpen = useWorkflowStore((s) => s.setPanelOpen);

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

  return (
    <div className="w-72 bg-gray-950 border-l border-gray-800 flex flex-col h-full">
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
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {data.kind === 'tool' && data.chipDef?.params && data.chipDef.params.length > 0 && (
          <>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Parameters</div>
            {data.chipDef.params.map((param) => (
              <div key={param.key}>
                <label className="block text-xs text-gray-400 mb-1">{param.label}</label>
                {param.type === 'select' && param.options ? (
                  <select
                    value={data.params[param.key] ?? param.default}
                    onChange={(e) => handleParamChange(param.key, e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono focus:outline-none focus:border-gray-500"
                  />
                ) : (
                  <input
                    type="text"
                    value={data.params[param.key] ?? param.default ?? ''}
                    onChange={(e) => handleParamChange(param.key, e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
                    placeholder={param.label}
                  />
                )}
              </div>
            ))}
          </>
        )}

        {data.kind === 'operator' && (
          <>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Operator Config</div>
            {data.operatorType === 'loop' && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Iterate over</label>
                <select
                  value={data.params.loopOver || 'scenarios'}
                  onChange={(e) => handleParamChange('loopOver', e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
                    placeholder="e.g. revenue, runway"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Operator</label>
                  <select
                    value={data.params.op || '>'}
                    onChange={(e) => handleParamChange('op', e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono focus:outline-none focus:border-gray-500"
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
                  className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500 resize-none"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono focus:outline-none focus:border-gray-500"
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
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
                    placeholder="e.g. revenue"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Value</label>
                  <input
                    type="number"
                    value={data.params.value ?? 0}
                    onChange={(e) => handleParamChange('value', Number(e.target.value))}
                    className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono focus:outline-none focus:border-gray-500"
                  />
                </div>
              </>
            )}
          </>
        )}

        {data.kind === 'formula' && (
          <>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Expression</div>
            <textarea
              value={data.params.expression || ''}
              onChange={(e) => handleParamChange('expression', e.target.value)}
              rows={3}
              className="w-full bg-gray-950 border border-gray-700 rounded px-2 py-1.5 text-sm text-lime-300 font-mono focus:outline-none focus:border-gray-500 resize-none"
              placeholder="revenue * 0.3 - opex"
            />
          </>
        )}

        {data.kind === 'driver' && (
          <>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Override Value</div>
            <input
              type="number"
              value={data.params.value ?? 0}
              onChange={(e) => handleParamChange('value', Number(e.target.value))}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-purple-300 font-mono focus:outline-none focus:border-gray-500"
            />
          </>
        )}

        {data.kind === 'output' && (
          <>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">Output Format</div>
            <select
              value={data.outputFormat || 'memo-section'}
              onChange={(e) => updateNodeData(selectedNode.id, { outputFormat: e.target.value as import('@/lib/workflow/types').OutputFormat })}
              className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
            >
              <option value="memo-section">Memo Section</option>
              <option value="deck-slide">Deck Slide</option>
              <option value="chart">Chart</option>
              <option value="grid">Grid Write</option>
              <option value="table">Table</option>
              <option value="narrative">Narrative</option>
              <option value="export">Export (PDF/Excel)</option>
            </select>
          </>
        )}

        {/* ── Result Detail Viewer ─────────────────────────────── */}
        {data.status === 'done' && data.result && (
          <div className="pt-3 border-t border-gray-800">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-2">Result</div>

            {/* Chart result */}
            {data.outputFormat === 'chart' && data.result?.chart_config && (
              <div className="text-xs text-emerald-400 mb-1">
                Chart: {data.result.chart_config.chart_type || 'chart'} ready
                <div className="mt-1 text-[10px] text-gray-500">
                  Click node to open in ChartViewport
                </div>
              </div>
            )}

            {/* Memo sections */}
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
                    {sec.type === 'chart' && (
                      <div className="text-emerald-400">[Chart section]</div>
                    )}
                    {sec.type === 'table' && (
                      <div className="text-blue-400">[Table section]</div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Table result */}
            {data.outputFormat === 'table' && data.result?.columns && data.result?.rows && (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="border-b border-gray-800">
                      {(data.result.columns as string[]).slice(0, 4).map((col: string) => (
                        <th key={col} className="text-left text-gray-500 py-1 pr-2 font-medium">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(data.result.rows as any[]).slice(0, 5).map((row: any, i: number) => (
                      <tr key={i} className="border-b border-gray-800/50">
                        {(data.result.columns as string[]).slice(0, 4).map((col: string) => (
                          <td key={col} className="text-gray-300 py-1 pr-2 font-mono">
                            {typeof row[col] === 'number' ? row[col].toLocaleString() : String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.result.rows.length > 5 && (
                  <div className="text-[10px] text-gray-500 mt-1">
                    +{data.result.rows.length - 5} more rows
                  </div>
                )}
              </div>
            )}

            {/* Narrative result */}
            {data.outputFormat === 'narrative' && data.result?.text && (
              <div className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                {data.result.text}
              </div>
            )}

            {/* Deck slides */}
            {data.outputFormat === 'deck-slide' && data.result?.slides && (
              <div className="space-y-2">
                {(data.result.slides as any[]).map((slide: any, i: number) => (
                  <div key={i} className="bg-gray-900 rounded p-2 border border-gray-800">
                    <div className="text-xs font-medium text-gray-200">{slide.title}</div>
                    {slide.bullets && (
                      <ul className="mt-1 space-y-0.5">
                        {(slide.bullets as string[]).slice(0, 4).map((b: string, j: number) => (
                          <li key={j} className="text-[10px] text-gray-400">- {b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Grid result */}
            {data.outputFormat === 'grid' && (
              <div className="text-xs text-emerald-400">
                {data.result?.columns_to_create
                  ? `${Object.keys(data.result.columns_to_create).length} columns to create`
                  : data.result?.value !== undefined
                    ? `Value: ${data.result.value}`
                    : 'Grid update ready'}
              </div>
            )}

            {/* Export result */}
            {data.outputFormat === 'export' && (
              <div className="text-xs text-blue-400">
                {data.result?.export_type?.toUpperCase() || 'PDF'} export ready
              </div>
            )}

            {/* Fallback: raw JSON for unhandled formats */}
            {!['chart', 'memo-section', 'table', 'narrative', 'deck-slide', 'grid', 'export'].includes(data.outputFormat || '') && (
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
          <div className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-2">Info</div>
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
