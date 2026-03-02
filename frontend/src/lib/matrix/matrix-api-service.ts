/**
 * Matrix API Service Layer
 * 
 * Clear separation of:
 * - Human CRUD: Direct user actions → Next.js routes → Supabase
 * - Agentic: AI-initiated actions → unified-brain → orchestrator → services
 * - Service Operations: Shared backend capabilities used by both
 */

import { MatrixData, MatrixColumn, MatrixRow, MatrixCell } from '@/components/matrix/UnifiedMatrix';
import { supabaseService } from '@/lib/supabase';

export type MatrixMode = 'portfolio' | 'query' | 'custom' | 'lp';
export type DataSource = 'manual' | 'agent' | 'document' | 'api' | 'formula';

// ============================================================================
// Human CRUD Operations (Direct user actions)
// ============================================================================

export interface CellEditRequest {
  rowId?: string;
  columnId: string;
  oldValue?: any;
  newValue: any;
  companyId?: string;
  fundId?: string;
  userId?: string;
  /** When update is from a cell action (e.g. valuation, PWERM). */
  data_source?: 'manual' | 'service' | 'document' | 'api' | 'formula';
  /** Service explanation, citations, etc. for audit and Citations panel. */
  metadata?: Record<string, unknown>;
  /** Link cell value to a source document (for document extraction flow). */
  sourceDocumentId?: string | number;
}

export interface AddCompanyRequest {
  name: string;
  fundId?: string;
  initialData?: Record<string, any>;
}

export interface AddColumnRequest {
  name: string;
  type: MatrixColumn['type'];
  service?: string; // Service to wire to (valuation, documents, charts, etc.)
  formula?: string;
  /** Optional stable id for workflows; if omitted, API generates col-{ts}-{random} */
  columnId?: string;
}

export interface DocumentUploadRequest {
  file: File;
  companyId?: string;
  fundId?: string;
  documentType?: string;
}

/**
 * Human CRUD: Update a matrix cell
 * Direct call to Next.js route → Supabase
 */
/**
 * Wrapper for matrix cell updates. Use this instead of raw fetch to /api/matrix/cells.
 */
export async function updateMatrixCell(request: CellEditRequest): Promise<void> {
  const companyId = request.companyId ?? request.rowId;
  const response = await fetch('/api/matrix/cells', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_id: companyId,
      column_id: request.columnId,
      old_value: request.oldValue,
      new_value: request.newValue,
      fund_id: request.fundId,
      user_id: request.userId,
      data_source: request.data_source,
      metadata: request.metadata,
      ...(request.sourceDocumentId != null ? { source_document_id: request.sourceDocumentId } : {}),
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to update cell');
  }
}

/**
 * Parse currency value from various formats (M/K/B notation, formatted strings)
 */
function parseCurrencyValue(value: string | number): number {
  if (typeof value === 'number') return value;
  if (!value) return 0;
  
  // Remove currency symbols and whitespace
  let cleaned = value.toString().trim().replace(/[$€£¥,\s]/g, '');
  
  // Handle suffixes
  const upper = cleaned.toUpperCase();
  let multiplier = 1;
  
  if (upper.endsWith('B')) {
    multiplier = 1_000_000_000;
    cleaned = cleaned.slice(0, -1);
  } else if (upper.endsWith('M')) {
    multiplier = 1_000_000;
    cleaned = cleaned.slice(0, -1);
  } else if (upper.endsWith('K')) {
    multiplier = 1_000;
    cleaned = cleaned.slice(0, -1);
  }
  
  const num = parseFloat(cleaned);
  if (isNaN(num)) return 0;
  
  return num * multiplier;
}

/**
 * Human CRUD: Add a company to the matrix
 * Works in both portfolio mode (with fundId) and sourcing mode (without fundId)
 */
export async function addCompanyToMatrix(request: AddCompanyRequest & {
  sector?: string;
  stage?: string;
  investmentAmount?: number | string;
  ownershipPercentage?: number;
  investmentDate?: string;
  currentArr?: number | string;
  valuation?: number | string;
}): Promise<MatrixRow> {
  // Parse currency values if provided as strings
  const parsedInvestmentAmount = request.investmentAmount 
    ? (typeof request.investmentAmount === 'string' ? parseCurrencyValue(request.investmentAmount) : request.investmentAmount)
    : (request.initialData?.investmentAmount || request.initialData?.total_invested_usd || 0);
  
  const parsedArr = request.currentArr
    ? (typeof request.currentArr === 'string' ? parseCurrencyValue(request.currentArr) : request.currentArr)
    : (request.initialData?.currentArr || request.initialData?.current_arr_usd || 0);

  if (request.fundId) {
    // Portfolio mode: use portfolio endpoint (requires investmentAmount)
    if (!parsedInvestmentAmount || parsedInvestmentAmount <= 0) {
      throw new Error('Investment amount is required for portfolio companies');
    }

    const response = await fetch(`/api/portfolio/${request.fundId}/companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: request.name,
        sector: request.sector || request.initialData?.sector,
        stage: request.stage || request.initialData?.stage,
        investmentAmount: parsedInvestmentAmount,
        ownershipPercentage: request.ownershipPercentage || request.initialData?.ownershipPercentage || request.initialData?.ownership_percentage || 0,
        investmentDate: request.investmentDate || request.initialData?.investmentDate || request.initialData?.first_investment_date || new Date().toISOString().split('T')[0],
        currentArr: parsedArr,
        valuation: request.valuation || request.initialData?.valuation || 0,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      const errorMessage = error.message || error.details || error.error || 'Failed to add company';
      console.error('Error adding company:', {
        status: response.status,
        error,
        request: {
          name: request.name,
          fundId: request.fundId,
          investmentAmount: parsedInvestmentAmount,
        }
      });
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return {
      id: data.id,
      companyId: data.id,
      companyName: data.name,
      cells: {},
    };
  } else {
    // Sourcing mode: use general companies endpoint (no investmentAmount required)
    const response = await fetch('/api/companies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: request.name,
        sector: request.sector || request.initialData?.sector,
        funnel_status: request.stage || request.initialData?.stage || 'prospect',
        current_arr_usd: parsedArr || undefined,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      const errorMessage = error.message || error.details || error.error || 'Failed to add company';
      console.error('Error adding company:', {
        status: response.status,
        error,
        request: {
          name: request.name,
        }
      });
      throw new Error(errorMessage);
    }

    const data = await response.json();
    return {
      id: data.id,
      companyId: data.id,
      companyName: data.name,
      cells: {},
    };
  }
}

/**
 * Shared helper: Create a real company for the matrix
 * Used by both Add Company and CSV import flows
 * Always creates a real company (no temp rows)
 */
export async function createCompanyForMatrix(params: {
  name: string;
  fundId?: string;
  mode: MatrixMode;
  companyFields?: Record<string, any>;
}): Promise<{ id: string; companyId: string; companyName: string }> {
  const { name, fundId, mode, companyFields = {} } = params;

  // Portfolio mode: use portfolio endpoint with default investmentAmount: 1 if missing
  if (mode === 'portfolio' && fundId) {
    const investmentAmount = companyFields.investmentAmount || companyFields.invested || 1;
    
    const result = await addCompanyToMatrix({
      name,
      fundId,
      investmentAmount,
      sector: companyFields.sector || '',
      stage: companyFields.stage || '',
      ownershipPercentage: companyFields.ownershipPercentage || companyFields.ownership || 0,
      investmentDate: companyFields.investmentDate || new Date().toISOString().split('T')[0],
      currentArr: companyFields.currentArr || companyFields.arr || 0,
      valuation: companyFields.valuation || 0,
    });

    return {
      id: result.id,
      companyId: result.companyId,
      companyName: result.companyName,
    };
  }

  // Custom / query / LP mode: use general companies endpoint
  const result = await addCompanyToMatrix({
    name,
    sector: companyFields.sector,
    stage: companyFields.stage,
    currentArr: companyFields.currentArr || companyFields.arr,
  });

  return {
    id: result.id,
    companyId: result.companyId,
    companyName: result.companyName,
  };
}

/**
 * Human CRUD: Upload document in cell
 * Direct call to documents API → Supabase
 */
export async function uploadDocumentInCell(request: DocumentUploadRequest): Promise<{ documentId: string; status: string }> {
  const formData = new FormData();
  formData.append('file', request.file);
  if (request.companyId) formData.append('company_id', request.companyId);
  if (request.fundId) formData.append('fund_id', request.fundId);
  if (request.documentType) formData.append('document_type', request.documentType);

  const response = await fetch('/api/documents', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to upload document');
  }

  const data = await response.json();
  return {
    documentId: data.document?.id ?? data.id,
    status: data.document?.status ?? data.status ?? 'processing',
  };
}

/**
 * Human CRUD: Add a custom column to the matrix
 * 
 * Persists to backend via /api/matrix/columns ONLY for:
 * - Portfolio mode (fundId provided)
 * - Saved matrix views (matrixId provided)
 * 
 * Query/custom mode columns are ephemeral and not persisted.
 */
export async function addMatrixColumn(
  request: AddColumnRequest & {
    matrixId?: string;
    fundId?: string;
    createdBy?: 'human' | 'agent';
  }
): Promise<MatrixColumn> {
  const generatedId = `col-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const columnId = (request.columnId?.trim?.()) || generatedId;

  // Only persist if fundId or matrixId provided (portfolio mode or saved view)
  // Otherwise return ephemeral column (query/custom mode)
  if (!request.fundId && !request.matrixId) {
    return {
      id: columnId,
      name: request.name,
      type: request.type,
      formula: request.formula,
      editable: true,
    };
  }

  const response = await fetch('/api/matrix/columns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      matrixId: request.matrixId,
      fundId: request.fundId,
      columnId,
      name: request.name,
      type: request.type,
      service: request.service
        ? { name: request.service, type: 'service' as const }
        : undefined,
      formula: request.formula,
      createdBy: request.createdBy || 'human',
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const msg =
      typeof error?.error === 'string'
        ? error.error
        : error?.details ?? 'Failed to add column';
    throw new Error(msg);
  }

  const data = await response.json();
  const row = data?.column;
  if (!row) throw new Error('Add column API returned no column');

  return {
    id: row.column_id ?? row.id ?? columnId,
    name: row.name ?? request.name,
    type: (row.type as MatrixColumn['type']) ?? request.type,
    formula: row.formula ?? request.formula,
    editable: true,
  };
}

// ============================================================================
// Agentic Operations (AI-initiated actions)
// ============================================================================

export interface AgenticQueryRequest {
  query: string;
  mode: MatrixMode;
  fundId?: string;
  context?: Record<string, any>;
}

export interface AgenticValuationRequest {
  companyId: string;
  method?: string;
  context?: Record<string, any>;
}

/**
 * Agentic: Natural language matrix query
 * Goes through unified-brain → orchestrator → MatrixQueryOrchestrator
 */
export async function queryMatrix(request: AgenticQueryRequest): Promise<MatrixData> {
  const sessionId = `matrix-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  
  const response = await fetch('/api/agent/unified-brain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: request.query,
      outputFormat: 'matrix',
      sessionId,
      context: {
        mode: request.mode,
        fundId: request.fundId,
        requireStructuredData: true,
        generateFormulas: true,
        ...request.context,
      },
      stream: false,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Query failed');
  }

  const data = await response.json();
  
  if (!data.success) {
    throw new Error(data.error || 'Query failed');
  }

  // Treat result as the matrix payload when present (unified-brain returns { result: { format, columns, rows, ... } })
  const payload = data.result ?? data;

  // Transform to MatrixData format
  if (payload.columns && payload.rows) {
    const transformedRows = payload.rows.map((row: any, idx: number) => {
      const cells: Record<string, MatrixCell> = {};
      const rowData = row.cells || row;
      
      Object.keys(rowData).forEach(key => {
        const cellData = rowData[key];
        if (cellData && typeof cellData === 'object' && !Array.isArray(cellData) && 'value' in cellData) {
          cells[key] = cellData;
        } else {
          cells[key] = { value: cellData, source: 'agent' };
        }
      });
      
      return {
        id: row.id || `row-${idx}`,
        cells,
        ...row,
      };
    });
    
    return {
      columns: payload.columns,
      rows: transformedRows,
      formulas: payload.formulas || {},
      metadata: {
        ...payload.metadata,
        query: request.query,
        mode: request.mode,
        lastUpdated: new Date().toISOString(),
        charts: payload.charts || [], // Include charts from unified MCP orchestrator
      },
    };
  }

  throw new Error('Invalid matrix data format');
}

/**
 * Agentic: Run valuation via agent
 * Goes through unified-brain → orchestrator → valuation engine
 */
export async function runValuationAgentic(request: AgenticValuationRequest): Promise<any> {
  const response = await fetch('/api/agent/unified-brain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: `Run valuation for company ${request.companyId} using ${request.method || 'auto'} method`,
      outputFormat: 'structured',
      context: {
        companyId: request.companyId,
        valuationMethod: request.method,
        ...request.context,
      },
      stream: false,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Valuation failed');
  }

  return await response.json();
}

// ============================================================================
// Service Operations (Shared backend capabilities)
// ============================================================================

export interface ValuationServiceRequest {
  companyId: string;
  method: 'dcf' | 'comparables' | 'precedent' | 'auto';
  context?: Record<string, any>;
}

export interface NAVServiceRequest {
  fundId: string;
  date?: string;
}

export interface DocumentProcessRequest {
  documentId: string;
  /** Storage path of the file (required for backend-agnostic processing) */
  filePath?: string;
  documentType?: string;
  companyId?: string;
  fundId?: string;
}

/**
 * Service: Run valuation engine
 * Human-triggered: uses thin valuation API (direct backend call)
 * Agentic: uses unified-brain → orchestrator path
 */
export async function runValuationService(request: ValuationServiceRequest): Promise<any> {
  // Human-triggered: use thin valuation API (direct backend call)
  const response = await fetch('/api/valuation/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      companyId: request.companyId,
      method: request.method,
      context: request.context,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Valuation failed');
  }

  return await response.json();
}

/**
 * Check for stored valuation method in matrix_edits.
 * Exported for use by valuation UI, NAV calculator, etc.
 */
export async function getStoredValuationMethod(
  companyId: string,
  columnId: string = 'valuation'
): Promise<string | null> {
  if (!supabaseService) return null;
  if (typeof companyId !== 'string' || !companyId.trim()) return null;

  try {
    const { data, error } = await supabaseService
      .from('matrix_edits')
      .select('metadata')
      .eq('company_id', companyId)
      .eq('column_id', columnId)
      .order('edited_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      console.warn('Error fetching stored valuation method:', error.message);
      return null;
    }
    if (!data?.metadata || typeof data.metadata !== 'object') return null;

    const metadata = data.metadata as { valuationMethod?: string; method?: string };
    const method = metadata.valuationMethod ?? metadata.method;
    return typeof method === 'string' && method.trim() ? method : null;
  } catch (err) {
    console.warn('Error checking stored valuation method:', err);
    return null;
  }
}

/**
 * Service: Calculate NAV for portfolio
 * Uses human-edited valuation OR service valuation (checks matrix_edits first)
 * Respects user-selected valuation method stored in matrix_edits
 */
export async function calculateNAV(request: NAVServiceRequest & { companyId?: string }): Promise<any> {
  // If companyId provided, calculate NAV for that company
  if (request.companyId) {
    // Check for manual valuation edit first
    const manualValuation = await checkManualValuation(request.companyId, 'valuation');
    
    // Check for stored valuation method preference
    const storedMethod = await getStoredValuationMethod(request.companyId, 'valuation');
    const valuationMethod = storedMethod || 'auto';
    
    let valuation: number;
    if (manualValuation !== null) {
      // Use manual valuation
      valuation = typeof manualValuation === 'number' ? manualValuation : parseFloat(manualValuation) || 0;
    } else {
      // Fall back to service valuation with user-selected method
      try {
        const method = ['dcf', 'comparables', 'precedent', 'auto'].includes(valuationMethod)
          ? (valuationMethod as 'dcf' | 'comparables' | 'precedent' | 'auto')
          : 'auto';
        const valuationResult = await runValuationService({
          companyId: request.companyId,
          method,
        });
        const v = valuationResult?.valuation ?? valuationResult?.value;
        valuation = typeof v === 'number' && Number.isFinite(v) ? v : 0;
      } catch (err) {
        console.warn('Valuation service failed, using fallback:', err);
        valuation = 0;
      }
    }

    // Get ownership percentage (would need to fetch from company)
    // For now, return the valuation (NAV = valuation * ownership will be calculated elsewhere)
    return { 
      valuation, 
      manual: manualValuation !== null,
      method: valuationMethod 
    };
  }

  // Portfolio-level NAV time series
  const response = await fetch(`/api/portfolio/${request.fundId}/nav-timeseries${request.date ? `?date=${request.date}` : ''}`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'NAV calculation failed');
  }

  return await response.json();
}

/**
 * Service: Process document
 * Shared service used by both human uploads and agentic flows
 */
export async function processDocument(request: DocumentProcessRequest): Promise<any> {
  const response = await fetch('/api/documents/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      documentId: request.documentId,
      filePath: request.filePath,
      documentType: request.documentType,
      company_id: request.companyId,
      fund_id: request.fundId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Document processing failed');
  }

  return await response.json();
}

/**
 * Service: Run PWERM analysis for a company.
 * Sends rowInputs (matrix row values) so backend uses them as inputs; DB company is merged/overridden.
 */
export async function runPWERMAnalysis(request: {
  companyId: string;
  fundId: string;
  rowInputs?: Record<string, unknown>;
}): Promise<{ success: boolean; pwermResults?: unknown; fair_value?: number; error?: string }> {
  const response = await fetch(`/api/portfolio/${request.fundId}/companies/${request.companyId}/pwerm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inputs: request.rowInputs ?? {}, rowInputs: request.rowInputs ?? {} }),
  });

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(result.error || 'PWERM analysis failed');
  }

  await logServiceOperation({
    companyId: request.companyId,
    fundId: request.fundId,
    columnId: 'pwerm',
    value: result.pwermResults,
    serviceName: 'pwerm_calculator',
    metadata: { method: 'pwerm_analysis' },
  }).catch(() => {});

  return result;
}

/**
 * Service: Run scenario analysis
 */
export async function runScenarioAnalysis(request: {
  portfolioId: string;
  companies?: string[];
  scenarios?: string[];
  numScenarios?: number;
  includeDownside?: boolean;
  includeUpside?: boolean;
  timeHorizon?: number;
}): Promise<any> {
  const response = await fetch('/api/scenarios/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      portfolioId: request.portfolioId,
      selectedScenarios: request.scenarios || [],
      numScenarios: request.numScenarios || 12,
      includeDownside: request.includeDownside !== false,
      includeUpside: request.includeUpside !== false,
      timeHorizon: request.timeHorizon || 5,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Scenario analysis failed');
  }

  const result = await response.json();
  
  // Log to audit trail for each company if provided
  if (request.companies && Array.isArray(request.companies)) {
    for (const companyId of request.companies) {
      await logServiceOperation({
        companyId,
        fundId: request.portfolioId,
        columnId: 'scenario_analysis',
        value: result.result,
        serviceName: 'scenario_analyzer',
        metadata: { 
          numScenarios: request.numScenarios,
          timeHorizon: request.timeHorizon,
        },
      });
    }
  }

  return result;
}

/**
 * Service: Run deal comparison
 */
export async function runDealComparison(request: {
  companyIds: string[];
  metrics?: string[];
  fundId?: string;
}): Promise<any> {
  const response = await fetch('/api/agent/unified-brain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: `Compare these companies: ${request.companyIds.join(', ')}. Analyze ${request.metrics?.join(', ') || 'key metrics'}.`,
      outputFormat: 'analysis',
      context: {
        companyIds: request.companyIds,
        metrics: request.metrics,
        fundId: request.fundId,
        analysisType: 'deal_comparison',
      },
      }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Deal comparison failed');
  }

  const result = await response.json();
  
  // Log to audit trail for each company
  for (const companyId of request.companyIds) {
    await logServiceOperation({
      companyId,
      fundId: request.fundId,
      columnId: 'deal_comparison',
      value: result,
      serviceName: 'deal_comparer',
      metadata: { 
        comparedCompanies: request.companyIds,
        metrics: request.metrics,
      },
    });
  }

  return result;
}

/**
 * Service: Run financial analysis
 */
export async function runFinancialAnalysis(request: {
  companyId: string;
  analysisType: 'comprehensive' | 'valuation' | 'growth' | 'risk';
  fundId?: string;
}): Promise<any> {
  const response = await fetch('/api/agent/unified-brain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: `Run ${request.analysisType} financial analysis for company ${request.companyId}`,
      outputFormat: 'analysis',
      context: {
        companyId: request.companyId,
        fundId: request.fundId,
        analysisType: request.analysisType,
      },
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Financial analysis failed');
  }

  const result = await response.json();
  
  // Log to audit trail
  await logServiceOperation({
    companyId: request.companyId,
    fundId: request.fundId,
    columnId: 'financial_analysis',
    value: result,
    serviceName: 'financial_analyzer',
    metadata: { analysisType: request.analysisType },
  });

  return result;
}

/**
 * Check for manual valuation edit in matrix_edits
 */
export async function checkManualValuation(
  companyId: string,
  columnId: string = 'valuation'
): Promise<any | null> {
  if (!supabaseService) return null;

  try {
    const { data, error } = await supabaseService
      .from('matrix_edits')
      .select('new_value, edited_at')
      .eq('company_id', companyId)
      .eq('column_id', columnId)
      .eq('data_source', 'manual')
      .order('edited_at', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error || !data) return null;
    return data.new_value;
  } catch (err) {
    console.warn('Error checking manual valuation:', err);
    return null;
  }
}

/**
 * Log service operation to matrix_edits audit trail
 */
async function logServiceOperation(request: {
  companyId: string;
  fundId?: string;
  columnId: string;
  value: any;
  serviceName: string;
  metadata?: Record<string, any>;
}): Promise<void> {
  if (!supabaseService) return;

  try {
    await supabaseService
      .from('matrix_edits')
      .insert({
        company_id: request.companyId,
        column_id: request.columnId,
        old_value: null,
        new_value: request.value,
        edited_by: 'service',
        edited_at: new Date().toISOString(),
        data_source: 'service',
        fund_id: request.fundId || null,
        metadata: {
          service: request.serviceName,
          ...request.metadata,
        },
      });
  } catch (err) {
    console.warn('Error logging service operation:', err);
    // Don't throw - audit logging is best effort
  }
}

// ============================================================================
// Field-Service Mapping
// ============================================================================

export interface FieldServiceMapping {
  fieldId: string;
  serviceName: string;
  serviceType: 'crud' | 'agentic' | 'service';
  apiEndpoint?: string;
  config?: Record<string, any>;
}

/**
 * Field-Service Map: Defines which backend service each matrix field wires to
 */
export const FIELD_SERVICE_MAP: Record<string, FieldServiceMapping> = {
  company: {
    fieldId: 'company',
    serviceName: 'portfolio',
    serviceType: 'crud',
    apiEndpoint: '/api/portfolio',
  },
  valuation: {
    fieldId: 'valuation',
    serviceName: 'valuation_engine',
    serviceType: 'service',
    config: { methods: ['dcf', 'comparables', 'precedent'] },
  },
  nav: {
    fieldId: 'nav',
    serviceName: 'valuation_engine',
    serviceType: 'service',
    apiEndpoint: '/api/portfolio/{fundId}/nav-timeseries',
  },
  documents: {
    fieldId: 'documents',
    serviceName: 'document_query_service',
    serviceType: 'crud',
    apiEndpoint: '/api/documents',
  },
  charts: {
    fieldId: 'charts',
    serviceName: 'chart_renderer',
    serviceType: 'service',
    config: { renderInCell: true },
  },
  analytics: {
    fieldId: 'analytics',
    serviceName: 'pwerm_calculator',
    serviceType: 'service',
    apiEndpoint: '/api/pwerm',
  },
  citations: {
    fieldId: 'citations',
    serviceName: 'citation_manager',
    serviceType: 'agentic',
  },
  // Cap table services
  cap_table: {
    fieldId: 'cap_table',
    serviceName: 'pre_post_cap_table',
    serviceType: 'service',
    apiEndpoint: '/api/cell-actions/actions/cap_table.calculate/execute',
  },
  ownership: {
    fieldId: 'ownership',
    serviceName: 'advanced_cap_table',
    serviceType: 'service',
    apiEndpoint: '/api/cell-actions/actions/cap_table.ownership/execute',
  },
};

/**
 * Get service mapping for a field
 */
export function getFieldService(fieldId: string): FieldServiceMapping | undefined {
  return FIELD_SERVICE_MAP[fieldId];
}

/**
 * Register a custom field-service mapping
 */
export function registerFieldService(mapping: FieldServiceMapping): void {
  FIELD_SERVICE_MAP[mapping.fieldId] = mapping;
}

/**
 * Fetch LPs from limited_partners table for matrix LP mode.
 * Returns MatrixData shaped for AGGridMatrix.
 */
export async function fetchLPsForMatrix(fundId?: string): Promise<import('@/components/matrix/UnifiedMatrix').MatrixData> {
  const { formatCurrency } = await import('@/lib/matrix/cell-formatters');

  // Try limited_partners first (primary), then lps as fallback
  let data: any[] | null = null;
  let error: any = null;

  if (supabaseService) {
    let query = supabaseService
      .from('limited_partners')
      .select('id, name, lp_type, status, commitment_usd, called_usd, distributed_usd, vintage_year, co_invest_rights, contact_name, investment_capacity_usd, fund_id')
      .order('name', { ascending: true });
    if (fundId) {
      query = query.or(`fund_id.eq.${fundId},fund_id.is.null`);
    }
    const result = await query;
    data = result.data;
    error = result.error;

    // Fallback to lps table
    if (error && error.message?.includes('does not exist')) {
      const fallback = await supabaseService
        .from('lps')
        .select('id, name, type, status, net_worth_usd, industry')
        .order('name', { ascending: true });
      data = fallback.data;
      error = fallback.error;
    }
  }

  if (error || !data) {
    console.error('[fetchLPsForMatrix] Error:', error);
    return { columns: [], rows: [], metadata: { dataSource: 'lp', lastUpdated: new Date().toISOString() } };
  }

  const columns: import('@/components/matrix/UnifiedMatrix').MatrixColumn[] = [
    { id: 'lpName', name: 'LP Name', type: 'text', width: 180, editable: true },
    { id: 'lpType', name: 'Type', type: 'text', width: 120, editable: true },
    { id: 'status', name: 'Status', type: 'text', width: 100, editable: true },
    { id: 'commitment', name: 'Commitment', type: 'currency', width: 140, editable: true },
    { id: 'called', name: 'Called', type: 'currency', width: 130, editable: true },
    { id: 'distributed', name: 'Distributed', type: 'currency', width: 140, editable: true },
    { id: 'unfunded', name: 'Unfunded', type: 'currency', width: 130, editable: false },
    { id: 'dpi', name: 'DPI', type: 'number', width: 80, editable: false },
    { id: 'coInvest', name: 'Co-Invest', type: 'boolean', width: 90, editable: true },
    { id: 'vintageYear', name: 'Vintage', type: 'number', width: 90, editable: true },
    { id: 'contactName', name: 'Contact', type: 'text', width: 140, editable: true },
    { id: 'capacity', name: 'Capacity', type: 'currency', width: 130, editable: true },
  ];

  const rows = data.map((lp: any) => {
    const commitment = lp.commitment_usd ?? 0;
    const called = lp.called_usd ?? 0;
    const distributed = lp.distributed_usd ?? 0;
    const unfunded = commitment - called;
    const dpi = called > 0 ? distributed / called : 0;

    return {
      id: String(lp.id),
      companyId: String(lp.id),
      companyName: lp.name,
      cells: {
        lpName: { value: lp.name, source: 'api' as const },
        lpType: { value: lp.lp_type ?? lp.type ?? '', source: 'api' as const },
        status: { value: lp.status ?? 'active', source: 'api' as const },
        commitment: { value: commitment, displayValue: formatCurrency(commitment), source: 'api' as const },
        called: { value: called, displayValue: formatCurrency(called), source: 'api' as const },
        distributed: { value: distributed, displayValue: formatCurrency(distributed), source: 'api' as const },
        unfunded: { value: unfunded, displayValue: formatCurrency(unfunded), source: 'api' as const },
        dpi: { value: Math.round(dpi * 100) / 100, displayValue: dpi.toFixed(2) + 'x', source: 'api' as const },
        coInvest: { value: lp.co_invest_rights ?? false, source: 'api' as const },
        vintageYear: { value: lp.vintage_year ?? '', source: 'api' as const },
        contactName: { value: lp.contact_name ?? '', source: 'api' as const },
        capacity: { value: lp.investment_capacity_usd ?? 0, displayValue: formatCurrency(lp.investment_capacity_usd ?? 0), source: 'api' as const },
      },
    };
  });

  return {
    columns,
    rows,
    metadata: { dataSource: 'lp', lastUpdated: new Date().toISOString(), fundId },
  };
}
