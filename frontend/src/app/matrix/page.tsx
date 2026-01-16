'use client';

import React, { useState, useEffect } from 'react';
import UnifiedFeedback from '@/components/UnifiedFeedback';
import SaveCompaniesToDatabase from '@/components/SaveCompaniesToDatabase';
import CitationDisplay from '@/components/CitationDisplay';
import AgentChartGenerator from '@/components/AgentChartGenerator';
import { 
  Table,
  Calculator,
  Database,
  Search,
  Download,
  Upload,
  RefreshCw,
  Plus,
  Filter,
  TrendingUp,
  DollarSign,
  Users,
  Building,
  Activity,
  BarChart3,
  Sparkles,
  Grid3x3,
  FileSpreadsheet,
  Brain
} from 'lucide-react';

interface MatrixColumn {
  id: string;
  name: string;
  type: 'text' | 'number' | 'currency' | 'percentage' | 'formula';
  width?: number;
  formula?: string;
}

interface MatrixRow {
  [key: string]: any;
}

interface MatrixData {
  columns: MatrixColumn[];
  rows: MatrixRow[];
  formulas?: Record<string, string>;
  metadata?: {
    lastUpdated?: string;
    dataSource?: string;
    confidence?: number;
  };
}

export default function MatrixPage() {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [matrixData, setMatrixData] = useState<MatrixData | null>(null);
  const [selectedCells, setSelectedCells] = useState<Set<string>>(new Set());
  const [formulaBar, setFormulaBar] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'data' | 'formulas'>('data');
  const [progressMessage, setProgressMessage] = useState<string>('');
  const [executionSteps, setExecutionSteps] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  const [citations, setCitations] = useState<any[]>([]);
  const [charts, setCharts] = useState<any[]>([]);
  const [showCharts, setShowCharts] = useState(false);

  // Sample queries for quick start
  const sampleQueries = [
    'Compare @Stripe @Square @Adyen financial metrics',
    'Show SaaS companies with >$100M ARR',
    'Calculate LTV/CAC for B2B fintech companies',
    'Create valuation matrix for Series B companies',
    'Analyze burn rates and runway for portfolio'
  ];

  const handleQuery = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setProgressMessage('🔍 Initializing analysis...');
    setExecutionSteps([]);
    setLastPrompt(query);
    
    // Generate session ID for this query
    const newSessionId = `matrix-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setSessionId(newSessionId);

    try {
      // Use unified-brain for real-time matrix generation
      const response = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: query,
          outputFormat: 'matrix',
          sessionId: newSessionId,
          context: {
            requireStructuredData: true,
            generateFormulas: true
          },
          stream: false  // Disable streaming
        })
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      // Handle JSON response
      const data = await response.json();
      
      if (data.success) {
        console.log('Received matrix data:', data);
        let matrixResult = data;
        
        // Handle unified format where format: 'matrix' is present
        if (data.format === 'matrix') {
          console.log('Processing unified matrix format');
          matrixResult = data;
        }
        
        // Extract citations and charts from the result
        if (data.citations) {
          setCitations(data.citations);
        }
        if (data.charts) {
          setCharts(data.charts);
        }
        setProgressMessage('✅ Matrix generation complete');
        setExecutionSteps(prev => [...prev, '✅ Analysis complete']);
        
        // Process the matrix data
        if (matrixResult.matrix) {
          const data = matrixResult;
          
          console.log('Processing matrix data:', data);
          
          // Check if this is a fallback response (when JSON parsing failed)
          if (data.content && data.format === 'matrix') {
            console.log('Received fallback response, raw content:', data.content);
            setError(`Matrix generation failed: ${data.error || 'Invalid JSON format'}`);
            // Try to show the raw content for debugging
            console.error('Raw AI response was:', data.content);
          } else if (data.columns && data.rows) {
            // dynamic-data-v2 returns properly formatted matrix data
            console.log('Found columns:', data.columns);
            console.log('Found rows:', data.rows);
        
            // Safely transform rows with type guards
            const transformedRows = data.rows.map((row: any) => {
              const flatRow: any = {};
              
              // Handle both old format (direct values) and new format (cells object)
              const rowData = row.cells || row;
              
              Object.keys(rowData).forEach(key => {
                const cellData = rowData[key];
                
                // Type guard: Check if this is an object with value property
                if (cellData && typeof cellData === 'object' && !Array.isArray(cellData)) {
                  // New format with {value, source, href} or {value, displayValue}
                  if ('value' in cellData) {
                    flatRow[key] = cellData.value;
                    // Store metadata for citations if available
                    if (cellData.source) {
                      flatRow[`${key}_source`] = cellData.source;
                    }
                    if (cellData.href) {
                      flatRow[`${key}_href`] = cellData.href;
                    }
                    if (cellData.displayValue) {
                      flatRow[`${key}_display`] = cellData.displayValue;
                    }
                  } else {
                    // Unknown object format, store as-is
                    flatRow[key] = cellData;
                  }
                } else {
                  // Direct value (old format) or primitive
                  flatRow[key] = cellData;
                }
              });
              return flatRow;
            });
            
            setMatrixData({
              columns: data.columns,
              rows: transformedRows,
              formulas: data.formulas || {},
              metadata: data.metadata || {}
            });
            setProgressMessage('');
            setError(null);
            
            // Show feedback after successful generation
            setTimeout(() => {
              setShowFeedback(true);
            }, 1000);
          } else {
            setError('Invalid matrix data format received');
          }
        } else {
          setError('No matrix data received from server');
        }
      } else {
        setError(data.error || 'Request failed');
      }
    } catch (err) {
      console.error('Matrix query error:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch matrix data');
    } finally {
      setIsLoading(false);
    }
  };

  const renderSparkline = (data: number[], color = '#3B82F6') => {
    if (!data || data.length === 0) return null;
    
    const width = 60;
    const height = 20;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    
    const points = data.map((value, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    }).join(' ');
    
    return (
      <svg width={width} height={height} className="inline-block ml-2">
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
        />
      </svg>
    );
  };

  const formatCellValue = (value: any, type: string) => {
    if (value === null || value === undefined) return '-';
    
    switch (type) {
      case 'currency':
        return typeof value === 'number' 
          ? `$${value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
          : value;
      case 'percentage':
        return typeof value === 'number' 
          ? `${(value * 100).toFixed(1)}%`
          : value;
      case 'number':
        return typeof value === 'number' 
          ? value.toLocaleString('en-US')
          : value;
      default:
        return value;
    }
  };

  const exportToCSV = () => {
    if (!matrixData) return;

    const headers = matrixData.columns.map(col => col.name).join(',');
    const rows = matrixData.rows.map(row => 
      matrixData.columns.map(col => row[col.id]).join(',')
    );
    
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `matrix-export-${Date.now()}.csv`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 shadow-sm border-b dark:border-gray-700">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center space-x-3">
              <Grid3x3 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Financial Matrix
              </h1>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Excel-style analysis with formulas
              </span>
            </div>
            
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode(viewMode === 'data' ? 'formulas' : 'data')}
                className="px-3 py-1 text-sm rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600"
              >
                {viewMode === 'data' ? 'Show Formulas' : 'Show Values'}
              </button>
              
              {matrixData && (
                <>
                  <button
                    onClick={exportToCSV}
                    className="flex items-center space-x-2 px-3 py-1 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700"
                  >
                    <Download className="w-4 h-4" />
                    <span>Export CSV</span>
                  </button>
                  <SaveCompaniesToDatabase 
                    companies={matrixData.rows}
                    onSaveComplete={(count) => console.log(`Saved ${count} companies`)}
                  />
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Query Bar */}
      <div className="bg-white dark:bg-gray-800 border-b dark:border-gray-700">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center space-x-4">
            <div className="flex-1 relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
                placeholder="Enter matrix query (e.g., 'Compare @Stripe @Square financial metrics')"
                className="w-full px-4 py-2 pl-10 pr-4 border dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
              <Search className="absolute left-3 top-2.5 w-5 h-5 text-gray-400" />
            </div>
            
            <button
              onClick={handleQuery}
              disabled={isLoading || !query.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>Generate Matrix</span>
                </>
              )}
            </button>
          </div>

          {/* Formula Bar */}
          {matrixData && (
            <div className="mt-4 flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">fx</span>
              <input
                type="text"
                value={formulaBar}
                onChange={(e) => setFormulaBar(e.target.value)}
                placeholder="=SUM(B2:B10) or =NPV(0.1, C2:C6)"
                className="flex-1 px-3 py-1 border dark:border-gray-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-gray-700 dark:text-white text-sm font-mono"
              />
            </div>
          )}

          {/* Sample Queries */}
          {!matrixData && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Try:</span>
              {sampleQueries.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(sample)}
                  className="text-sm px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"
                >
                  {sample}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Progress Section */}
      {isLoading && progressMessage && (
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <div className="flex items-center space-x-3 mb-3">
              <RefreshCw className="w-5 h-5 text-blue-600 dark:text-blue-400 animate-spin" />
              <p className="text-blue-800 dark:text-blue-200 font-medium">{progressMessage}</p>
            </div>
            {executionSteps.length > 0 && (
              <div className="space-y-1 pl-8">
                {executionSteps.slice(-5).map((step, idx) => (
                  <div key={idx} className="text-sm text-blue-700 dark:text-blue-300 flex items-start space-x-2">
                    <span className="text-blue-500">•</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && !isLoading && (
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        </div>
      )}

      {/* Matrix Table */}
      {matrixData && (
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider w-12">
                      #
                    </th>
                    {matrixData.columns.map((col) => (
                      <th
                        key={col.id}
                        className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                        style={{ minWidth: col.width || 150 }}
                      >
                        <div className="flex items-center space-x-1">
                          {col.type === 'currency' && <DollarSign className="w-3 h-3" />}
                          {col.type === 'percentage' && <TrendingUp className="w-3 h-3" />}
                          {col.type === 'formula' && <Calculator className="w-3 h-3" />}
                          <span>{col.name}</span>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {matrixData.rows.map((row, rowIdx) => {
                    const isAnalysis = row.metric && typeof row.metric === 'string' && row.metric.includes('ANALYSIS:');
                    return (
                    <tr
                      key={rowIdx}
                      className={isAnalysis ? 
                        "bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30" : 
                        "hover:bg-gray-50 dark:hover:bg-gray-700"}
                    >
                      <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                        {rowIdx + 1}
                      </td>
                      {matrixData.columns.map((col) => (
                        <td
                          key={`${rowIdx}-${col.id}`}
                          className="px-4 py-3 text-sm text-gray-900 dark:text-white"
                          onClick={() => {
                            const cellId = `${rowIdx}-${col.id}`;
                            setSelectedCells(new Set([cellId]));
                            if (col.formula) {
                              setFormulaBar(col.formula);
                            }
                          }}
                        >
                          {viewMode === 'formulas' && col.formula ? (
                            <span className="font-mono text-xs text-blue-600 dark:text-blue-400">
                              {col.formula}
                            </span>
                          ) : (
                            <div className="flex flex-col">
                              {/* Check if this cell has sparkline data */}
                              {row[col.id] && typeof row[col.id] === 'object' && row[col.id].sparkline ? (
                                <div className="flex items-center">
                                  <span className={col.type === 'number' || col.type === 'currency' || col.type === 'percentage' ? 'font-mono' : ''}>
                                    {formatCellValue(row[col.id].displayValue || row[col.id].value, col.type)}
                                  </span>
                                  {renderSparkline(row[col.id].sparkline)}
                                </div>
                              ) : row[`${col.id}_href`] ? (
                                <a 
                                  href={row[`${col.id}_href`]} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-blue-600 dark:text-blue-400 hover:underline"
                                >
                                  <span className={col.type === 'number' || col.type === 'currency' || col.type === 'percentage' ? 'font-mono' : ''}>
                                    {formatCellValue(row[col.id], col.type)}
                                  </span>
                                </a>
                              ) : (
                                <span className={col.type === 'number' || col.type === 'currency' || col.type === 'percentage' ? 'font-mono' : ''}>
                                  {formatCellValue(row[col.id], col.type)}
                                  {/* Add citation superscript if this cell has a citation */}
                                  {row[`${col.id}_citation`] && (
                                    <sup className="ml-1 text-blue-600 dark:text-blue-400 cursor-pointer hover:underline"
                                         onClick={() => {
                                           const citationElement = document.getElementById('citations-section');
                                           if (citationElement) {
                                             citationElement.scrollIntoView({ behavior: 'smooth' });
                                           }
                                         }}>
                                      [{row[`${col.id}_citation`]}]
                                    </sup>
                                  )}
                                </span>
                              )}
                              {row[`${col.id}_source`] && (
                                <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                  {row[`${col.id}_source`]}
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                      ))}
                    </tr>
                  );})}
                </tbody>
              </table>
            </div>

            {/* Metadata Footer */}
            {matrixData.metadata && (
              <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-t dark:border-gray-700">
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <div className="flex items-center space-x-4">
                    {matrixData.metadata.lastUpdated && (
                      <span>Updated: {matrixData.metadata.lastUpdated}</span>
                    )}
                    {matrixData.metadata.dataSource && (
                      <span>Source: {matrixData.metadata.dataSource}</span>
                    )}
                    {matrixData.metadata.confidence && (
                      <span>Confidence: {matrixData.metadata.confidence}%</span>
                    )}
                  </div>
                  <div>
                    {matrixData.rows.length} rows × {matrixData.columns.length} columns
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Citations Section */}
      {citations && citations.length > 0 && (
        <div id="citations-section" className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <CitationDisplay citations={citations} />
        </div>
      )}

      {/* Charts Section */}
      {charts && charts.length > 0 && (
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center">
                <BarChart3 className="w-5 h-5 mr-2" />
                Visual Analytics
              </h3>
              <button
                onClick={() => setShowCharts(!showCharts)}
                className="text-sm text-blue-600 hover:text-blue-700"
              >
                {showCharts ? 'Hide Charts' : 'Show Charts'}
              </button>
            </div>
            
            {showCharts && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {charts.map((chart, index) => (
                  <div key={index} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                    <AgentChartGenerator
                      prompt={`Chart ${index + 1}: ${chart.title || chart.type}`}
                      chartData={chart}
                      autoGenerate={true}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Feedback Component */}
      {showFeedback && matrixData && (
        <UnifiedFeedback
          sessionId={sessionId}
          prompt={lastPrompt}
          response={matrixData}
          outputFormat="matrix"
          onClose={() => setShowFeedback(false)}
        />
      )}

      {/* Empty State */}
      {!matrixData && !isLoading && (
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center">
            <FileSpreadsheet className="w-16 h-16 mx-auto text-gray-400 dark:text-gray-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No Matrix Data Yet
            </h3>
            <p className="text-gray-500 dark:text-gray-400 mb-6">
              Enter a query above to generate financial matrices with formulas and calculations
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border dark:border-gray-700">
                <Calculator className="w-8 h-8 text-blue-600 dark:text-blue-400 mb-2" />
                <h4 className="font-medium text-gray-900 dark:text-white">Excel Formulas</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  NPV, IRR, SUM, AVERAGE
                </p>
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border dark:border-gray-700">
                <Database className="w-8 h-8 text-green-600 dark:text-green-400 mb-2" />
                <h4 className="font-medium text-gray-900 dark:text-white">Real Data</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Live company metrics
                </p>
              </div>
              
              <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border dark:border-gray-700">
                <Brain className="w-8 h-8 text-primary dark:text-purple-400 mb-2" />
                <h4 className="font-medium text-gray-900 dark:text-white">AI Analysis</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Smart comparisons
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}