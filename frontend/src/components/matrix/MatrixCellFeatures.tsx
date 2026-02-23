'use client';

/**
 * Matrix Cell Features
 * 
 * In-cell and modal features for matrix cells:
 * - Valuation: Dialog with valuation method selector
 * - Documents: Sheet with upload and document list
 * - Charts: Dialog with chart preview
 * - Analytics: Sheet with PWERM/scenarios
 * - Citations: Inline expansion within cell (no popover)
 */

import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Calculator,
  FileText,
  BarChart3,
  TrendingUp,
  Upload,
  ExternalLink,
  Sparkles,
  FileSpreadsheet,
  Info,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { executeAction, type ActionExecutionResponse } from '@/lib/matrix/cell-action-registry';
import { buildActionInputs } from '@/lib/matrix/workflow-executor';

type MatrixDataLike = { rows: { id: string; companyId?: string; cells: Record<string, { value?: unknown }> }[]; columns: { id: string; name?: string }[]; metadata?: { fundId?: string } } | undefined;

interface ValuationCellProps {
  value: any;
  companyId?: string;
  companyName?: string;
  fundId?: string;
  rowId?: string;
  columnId?: string;
  /** When provided with row, inputs are built from cell values (same as dropdown) so CFO overrides apply. */
  matrixData?: MatrixDataLike;
  row?: { id: string; companyId?: string; cells?: Record<string, { value?: unknown }> };
  metadata?: {
    method?: string;
    explanation?: string;
    citations?: { id?: string; source?: string; url?: string; title?: string }[];
  };
  onUpdate: (value: any, method: string) => Promise<void>;
  onCellActionResult?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void | Promise<void>;
}

export function ValuationCell({ 
  value, 
  companyId, 
  companyName, 
  fundId,
  rowId,
  columnId,
  matrixData,
  row,
  metadata, 
  onUpdate,
  onCellActionResult,
}: ValuationCellProps) {
  const [showCitations, setShowCitations] = useState(false);
  const [method, setMethod] = useState<string>('auto');
  const [isOpen, setIsOpen] = useState(false);
  const [isCalculating, setIsCalculating] = useState(false);

  const handleCalculate = async () => {
    setIsCalculating(true);
    try {
      // Use executeAction if onCellActionResult is provided, otherwise fall back to direct API
      if (onCellActionResult && rowId && columnId) {
        const actionId = method === 'pwerm' ? 'valuation_engine.pwerm' : 'valuation_engine.auto';
        const inputs = matrixData && row
          ? { ...buildActionInputs(actionId, row, columnId, matrixData), method }
          : { company_id: companyId, fund_id: fundId, method };
        const response = await executeAction({
          action_id: actionId,
          row_id: rowId,
          column_id: columnId,
          inputs,
          mode: 'portfolio',
          fund_id: fundId,
          company_id: companyId,
        });
        
        if (response.success) {
          await onCellActionResult(rowId, columnId, response);
          // Also call onUpdate for backward compatibility
          await onUpdate(response.value, method);
        }
      } else {
        // Fallback to direct API call
        const { runValuationService } = await import('@/lib/matrix/matrix-api-service');
        const result = await runValuationService({
          companyId: companyId || '',
          method: method as any,
        });
        await onUpdate(result.value || result, method);
      }
      setIsOpen(false);
    } catch (error) {
      console.error('Valuation calculation failed:', error);
    } finally {
      setIsCalculating(false);
    }
  };

  const hasExplanation = metadata?.explanation || metadata?.method;
  const citations = metadata?.citations || [];
  const hasCitations = citations.length > 0;

  const CitationBadge = () => {
    if (!hasCitations) return null;

    return (
      <Badge
        variant="outline"
        className="h-5 px-1.5 text-xs cursor-pointer hover:bg-accent flex-shrink-0"
        onClick={(e) => {
          e.stopPropagation();
          setShowCitations(!showCitations);
        }}
      >
        {citations.length}
      </Badge>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <TooltipProvider>
          <div className="w-full flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "flex-1 justify-start text-left font-normal h-auto py-2",
                  !value && "text-muted-foreground"
                )}
              >
                <Calculator className="h-4 w-4 mr-2" />
                {value ? `$${Number(value).toLocaleString()}` : 'Calculate Valuation'}
              </Button>
              {hasExplanation && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3 w-3 text-muted-foreground hover:text-primary cursor-help flex-shrink-0" />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <div className="space-y-1">
                      {metadata?.method && (
                        <div className="font-semibold">{metadata.method}</div>
                      )}
                      {metadata?.explanation && (
                        <div className="text-xs">{metadata.explanation}</div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
              )}
              <CitationBadge />
            </div>
            
            {/* Inline Citations - expands within cell */}
            {showCitations && hasCitations && (
              <div 
                className="p-2 rounded-md border border-slate-200 bg-slate-50 text-xs"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium text-sm">Citations</h4>
                    <button
                      onClick={() => setShowCitations(false)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  {hasExplanation && (
                    <div className="text-xs text-muted-foreground pb-2 border-b">
                      {metadata?.method && (
                        <div className="font-semibold mb-1">{metadata.method}</div>
                      )}
                      {metadata?.explanation && (
                        <div>{metadata.explanation}</div>
                      )}
                    </div>
                  )}
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {citations.map((citation, idx) => (
                      <div key={citation.id || idx} className="text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">
                            {citation.source || citation.title || 'Source'}
                          </span>
                          {citation.url && (
                            <a
                              href={citation.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline ml-2"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </TooltipProvider>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Valuation Calculator</DialogTitle>
          <DialogDescription>
            Calculate valuation for {companyName || 'this company'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Valuation Method</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto (Recommended)</SelectItem>
                <SelectItem value="dcf">DCF (Discounted Cash Flow)</SelectItem>
                <SelectItem value="comparables">Comparables</SelectItem>
                <SelectItem value="precedent">Precedent Transactions</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={handleCalculate}
            disabled={isCalculating || !companyId}
            className="w-full"
          >
            {isCalculating ? 'Calculating...' : 'Calculate Valuation'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface DocumentsCellProps {
  companyId?: string;
  fundId?: string;
  documentCount?: number;
  documents?: Array<{ id: string; name: string; url?: string; preview_url?: string }>;
  onUpload?: (file: File) => Promise<{ document_id: string }>;
  onCellActionResult?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void | Promise<void>;
  rowId?: string;
  columnId?: string;
  onViewDocument?: (documentId: string) => void;
  onSuggestChanges?: (documentId: string, extractedData: any) => void;
}

export function DocumentsCell({ 
  companyId, 
  fundId, 
  documentCount = 0,
  documents = [],
  onUpload,
  onCellActionResult,
  rowId,
  columnId,
  onViewDocument,
  onSuggestChanges,
}: DocumentsCellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      xhrRef.current?.abort();
    };
  }, []);
  const [documentType, setDocumentType] = useState<string>('monthly_update');

  const handleFileUpload = async (file: File) => {
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      // Upload with progress tracking
      const formData = new FormData();
      formData.append('file', file);
      formData.append('document_type', documentType);
      if (companyId) formData.append('company_id', companyId);
      if (fundId) formData.append('fund_id', fundId);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      // Track upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percentComplete = (e.loaded / e.total) * 100;
          if (mountedRef.current) setUploadProgress(percentComplete);
        }
      });

      const uploadPromise = new Promise<{ document_id: string }>((resolve, reject) => {
        xhr.addEventListener('load', async () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const result = JSON.parse(xhr.responseText);
              const documentId = result?.document?.id ?? result?.id ?? result?.document_id;
              if (mountedRef.current) setUploadProgress(100);

              // After upload, trigger document extraction.
              // The backend now persists extracted metrics as pending_suggestions,
              // so the badge pipeline (DocumentSuggestionBadge) picks them up automatically.
              if (onCellActionResult && rowId && columnId && documentId) {
                try {
                  const response = await executeAction({
                    action_id: 'document.extract',
                    row_id: rowId,
                    column_id: columnId,
                    inputs: {
                      document_id: String(documentId),
                      extraction_type: 'structured',
                    },
                    mode: 'portfolio',
                    fund_id: fundId,
                    company_id: companyId,
                  });

                  if (mountedRef.current && response.success) {
                    await onCellActionResult(rowId, columnId, response);
                    // Notify parent to refresh suggestions
                    if (onSuggestChanges) {
                      onSuggestChanges(String(documentId), response.metadata?.raw_output || response.value);
                    }
                    setIsOpen(false);
                  }
                } catch (extractError) {
                  console.error('Document extraction failed:', extractError);
                  reject(extractError instanceof Error ? extractError : new Error('Document extraction failed'));
                  return;
                }
              }

              // NOTE: Do NOT call onUpload(file) here. The XHR above already uploaded
              // the file to /api/documents. Calling onUpload would trigger uploadDocumentInCell()
              // in MatrixFieldCard, which would POST the same file again, creating a duplicate.
              // The onCellFeatureAction callback in onUpload is also unnecessary — extraction
              // is already handled above via executeAction('document.extract').

              resolve({ document_id: documentId });
            } catch (parseError) {
              reject(new Error('Failed to parse upload response'));
            }
          } else {
            reject(new Error(`Upload failed: ${xhr.statusText}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Network error during upload'));
        });
      });

      xhr.open('POST', '/api/documents');
      xhr.send(formData);

      await uploadPromise;
    } catch (error) {
      console.error('Document upload failed:', error);
      throw error;
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files?.length) return;
    for (let i = 0; i < files.length; i++) {
      await handleFileUpload(files[i]);
    }
    e.target.value = '';
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      await handleFileUpload(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  return (
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-left font-normal h-auto py-2"
          >
            <FileText className="h-4 w-4 mr-2" />
            {documentCount > 0 ? `${documentCount} document${documentCount > 1 ? 's' : ''}` : 'Upload Document'}
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-[400px] sm:w-[540px]">
          <SheetHeader>
            <SheetTitle>Documents</SheetTitle>
            <SheetDescription>
              Upload and manage documents for this company
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Upload Document</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm">Document type</Label>
                    <Select value={documentType} onValueChange={setDocumentType}>
                      <SelectTrigger className="w-[180px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="monthly_update">Monthly Update</SelectItem>
                        <SelectItem value="board_deck">Board Deck</SelectItem>
                        <SelectItem value="pitch_deck">Pitch Deck</SelectItem>
                        <SelectItem value="investment_memo">Investment Memo</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    className={cn(
                      "flex items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer",
                      isDragging ? "border-primary bg-accent" : "hover:bg-accent",
                      isUploading && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    <label
                      htmlFor="document-upload"
                      className="flex flex-col items-center justify-center w-full h-full cursor-pointer"
                    >
                      <div className="flex flex-col items-center justify-center pt-5 pb-6">
                        <Upload className={cn("w-10 h-10 mb-3", isDragging ? "text-primary" : "text-muted-foreground")} />
                        <p className="mb-2 text-sm text-muted-foreground">
                          <span className="font-semibold">Click to upload</span> or drag and drop
                        </p>
                        <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX</p>
                      </div>
                      <input
                        id="document-upload"
                        type="file"
                        className="hidden"
                        onChange={handleFileInput}
                        disabled={isUploading}
                        accept=".pdf,.docx,.xlsx,.xls"
                        multiple
                      />
                    </label>
                  </div>
                  {isUploading && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Uploading...</span>
                        <span className="text-muted-foreground">{Math.round(uploadProgress)}%</span>
                      </div>
                      <div className="w-full bg-secondary rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Document List - simple links (DocumentAnalysisCollapsible removed due to bugs) */}
            {documents.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Documents ({documents.length})</CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Click to open full analysis
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <a
                        key={doc.id}
                        href={`/documents/${doc.id}/analysis`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between p-2 border rounded-md hover:bg-accent/50 gap-2 group"
                      >
                        <span className="flex items-center gap-2 min-w-0 truncate">
                          <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                          <span className="truncate">{doc.name}</span>
                        </span>
                        <ExternalLink className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground group-hover:text-foreground" />
                      </a>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </SheetContent>
      </Sheet>
  );
}

interface ChartsCellProps {
  chartData?: any;
  chartType?: string;
  chartConfig?: any;
  rowId?: string;
  columnId?: string;
  companyId?: string;
  fundId?: string;
  onGenerate: (prompt: string) => Promise<void>;
  onCellActionResult?: (rowId: string, columnId: string, response: ActionExecutionResponse) => void | Promise<void>;
}

export function ChartsCell({ 
  chartData, 
  chartType, 
  chartConfig,
  rowId,
  columnId,
  companyId,
  fundId,
  onGenerate,
  onCellActionResult,
}: ChartsCellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    
    setIsGenerating(true);
    try {
      // Use executeAction if onCellActionResult is provided, otherwise fall back to onGenerate
      if (onCellActionResult && rowId && columnId) {
        const response = await executeAction({
          action_id: 'chart_intelligence.generate',
          row_id: rowId,
          column_id: columnId,
          inputs: {
            context: prompt,
            chart_type: 'auto',
            company_id: companyId,
            fund_id: fundId,
          },
          mode: 'portfolio',
          fund_id: fundId,
          company_id: companyId,
        });
        
        if (response.success) {
          await onCellActionResult(rowId, columnId, response);
        }
      } else {
        // Fallback to onGenerate callback
        await onGenerate(prompt);
      }
      setIsOpen(false);
      setPrompt('');
    } catch (error) {
      console.error('Chart generation failed:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-left font-normal h-auto py-2"
        >
          <BarChart3 className="h-4 w-4 mr-2" />
          {chartData || chartConfig ? 'View Chart' : 'Generate Chart'}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Chart Generator</DialogTitle>
          <DialogDescription>
            {chartConfig ? chartConfig.title || 'Generated Chart' : 'Generate a chart from your data'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {chartData || chartConfig ? (
            <div className="h-64 bg-muted rounded-lg flex items-center justify-center">
              {chartConfig ? (
                <div className="text-center space-y-2">
                  <p className="text-sm font-medium">{chartConfig.title || 'Chart'}</p>
                  <p className="text-xs text-muted-foreground">Type: {chartConfig.type || 'auto'}</p>
                  {chartConfig.description && (
                    <p className="text-xs text-muted-foreground">{chartConfig.description}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Chart preview</p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Chart Description</Label>
              <Input
                placeholder="e.g., Revenue growth over time"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={isGenerating}
              />
              <Button onClick={handleGenerate} className="w-full" disabled={isGenerating || !prompt.trim()}>
                <Sparkles className="h-4 w-4 mr-2" />
                {isGenerating ? 'Generating...' : 'Generate Chart'}
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface AnalyticsCellProps {
  companyId?: string;
  onRunAnalysis: (type: 'pwerm' | 'scenario' | 'comparison') => Promise<void>;
}

export function AnalyticsCell({ companyId, onRunAnalysis }: AnalyticsCellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [analysisType, setAnalysisType] = useState<'pwerm' | 'scenario' | 'comparison'>('pwerm');

  const handleRun = async () => {
    await onRunAnalysis(analysisType);
    setIsOpen(false);
  };

  return (
    <Sheet open={isOpen} onOpenChange={setIsOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-left font-normal h-auto py-2"
        >
          <TrendingUp className="h-4 w-4 mr-2" />
          Run Analysis
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[400px] sm:w-[540px]">
        <SheetHeader>
          <SheetTitle>Analytics</SheetTitle>
          <SheetDescription>
            Run PWERM, scenario analysis, or deal comparison
          </SheetDescription>
        </SheetHeader>
        <div className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label>Analysis Type</Label>
            <Select value={analysisType} onValueChange={(v) => setAnalysisType(v as any)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pwerm">PWERM Analysis</SelectItem>
                <SelectItem value="scenario">Scenario Analysis</SelectItem>
                <SelectItem value="comparison">Deal Comparison</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleRun} className="w-full" disabled={!companyId}>
            Run Analysis
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Cap Table Evolution Display: renders inline summary + expandable chart */
interface CapTableEvolutionCellProps {
  evolution: Array<{ round: string; dilution?: number; our_ownership?: number; founders_pct?: number; esop_pct?: number; other_investors_pct?: number }>;
  companyName?: string;
  onOpenChart?: (chartType: string, chartData: any) => void;
}

export function CapTableEvolutionCell({ evolution, companyName, onOpenChart }: CapTableEvolutionCellProps) {
  if (!evolution || evolution.length === 0) return <span className="text-muted-foreground text-xs">No data</span>;

  const first = evolution[0];
  const last = evolution[evolution.length - 1];
  const startPct = ((first.our_ownership ?? 0) * 100).toFixed(1);
  const endPct = ((last.our_ownership ?? 0) * 100).toFixed(1);
  const summary = `${startPct}% → ${endPct}% over ${evolution.length} rounds`;

  return (
    <div className="flex flex-col gap-1 w-full">
      <span className="text-xs font-medium">{summary}</span>
      {onOpenChart && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 text-xs px-1"
          onClick={() => onOpenChart('cap_table_waterfall', evolution)}
        >
          <BarChart3 className="w-3 h-3 mr-1" />
          View evolution
        </Button>
      )}
    </div>
  );
}

interface CitationsCellProps {
  citations: Array<{ id: string; source: string; url?: string }>;
}

export function CitationsCell({ citations }: CitationsCellProps) {
  const [showCitations, setShowCitations] = useState(false);
  
  if (citations.length === 0) return null;

  return (
    <div className="w-full flex flex-col gap-1">
      <Button
        variant="ghost"
        size="sm"
        className="w-full justify-start text-left font-normal h-auto py-1"
        onClick={() => setShowCitations(!showCitations)}
      >
        <Badge variant="secondary" className="mr-2">
          {citations.length}
        </Badge>
        Sources
      </Button>
      
      {/* Inline Citations - expands within cell */}
      {showCitations && (
        <div 
          className="p-2 rounded-md border border-slate-200 bg-slate-50 text-xs"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-sm">Citations</h4>
              <button
                onClick={() => setShowCitations(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {citations.map((citation) => (
                <div key={citation.id} className="text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">{citation.source}</span>
                    {citation.url && (
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline ml-2"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
