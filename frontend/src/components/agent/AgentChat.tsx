'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';
import {
  ArrowUp,
  User,
  Sparkles,
  Search,
  TrendingUp,
  BarChart3,
  Calculator,
  FileSearch,
  Activity,
  Loader2,
  Copy,
  RotateCcw,
  Zap,
  Target,
  DollarSign,
  GitBranch,
  Globe,
  Upload,
  Check,
  X,
  Download,
  FileText as FileTextIcon,
  Maximize2,
  AlertTriangle,
  Lightbulb,
  PlayCircle,
  Trash2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import AgentFeedback from './AgentFeedback';
import { CompanyAnalysisCard } from './CompanyAnalysisCard';
import type { CompanyAnalysisData } from './CompanyAnalysisCard';
import { MatrixSnippet, type MatrixSnippetData } from './MatrixSnippet';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import dynamic from 'next/dynamic';
import { buildGridSnapshot } from '@/lib/portfolio-context-compressor';
import { SkeletonChart } from '@/components/ui/skeleton';
import type { MatrixData } from '@/components/matrix/UnifiedMatrix';
import { contextManager } from '@/lib/agent-context-manager';
import { FormatHandlerFactory } from '@/lib/format-handlers/factory';
import { parseMarkdownToSections } from '@/lib/format-handlers/docs-handler';
import { formatSuggestionValue } from '@/lib/matrix/cell-formatters';

// Dynamically import TableauLevelCharts to avoid SSR issues
const TableauLevelCharts = dynamic(() => import('@/components/charts/TableauLevelCharts'), { 
  ssr: false,
  loading: () => <SkeletonChart className="min-h-[256px]" />
});

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolsUsed?: string[];
  confidence?: number;
  processing?: boolean;
  charts?: Array<{
    type: string;
    title?: string;
    data: any;
  }>;
  analysisData?: any;
  capTables?: any[];
  citations?: any[];
  matrixSnippets?: MatrixSnippetData[];
  companies?: any[];
  explanation?: {
    steps?: { action: string; result?: string }[];
    method?: string;
    reasoning?: string;
  };
  gridCommands?: Array<{ action: 'edit' | 'run' | 'add_document'; rowId?: string; columnId?: string; value?: unknown; actionId?: string; source_service?: string; reasoning?: string; confidence?: number; metadata?: Record<string, unknown>; auto_apply?: boolean }>;
  toolsFailed?: string[];
  /** Deck format: slides for inline preview */
  deckSlides?: Array<{ id?: string; title?: string; content?: any; order?: number }>;
  /** Docs format: sections for memo rendering */
  docsSections?: Array<{ title?: string; content?: string; level?: number }>;
  /** Enriched charts from format handler (positioned within docs) */
  docsCharts?: Array<{ type: string; title?: string; data: any }>;
  /** Chart positions for interleaving with sections */
  docsChartPositions?: Array<{ afterParagraph: number; inline: boolean }>;
  /** Agent loop plan steps (ephemeral progress indicators) */
  planSteps?: Array<{ id: string; label: string; status: 'pending' | 'running' | 'done' | 'failed'; tool?: string }>;
  /** Whether this message awaits user plan approval before executing */
  awaitingApproval?: boolean;
  /** Non-cell suggestions: action items, warnings, insights from agent */
  agentSuggestions?: Array<{ type: 'warning' | 'action_item' | 'insight'; title: string; description: string; priority?: string }>;
  /** Inline todos emitted by the agent — session state, checkable in chat */
  todoItems?: Array<{ id: string; title: string; description?: string; priority?: string; company?: string; due?: string; done: boolean }>;
  /** Inline memo sections from enrichment/diligence — rendered in chat, not in doc viewer */
  memoSections?: Array<{ type: string; content?: string; items?: string[]; chart?: any }>;
}

export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

export interface MatrixContext {
  rowIds: string[];
  companyNames: string[];
  columns: { id: string; name: string }[];
  fundId?: string;
  summaryMetrics?: Record<string, unknown>;
  /** Per-row cell values for grid-aware analysis (Phase 1) */
  gridSnapshot?: { rows: Array<{ rowId: string; companyName: string; cells: Record<string, unknown> }>; columns: Array<{ id: string; name: string }> };
}

import type { DocumentSuggestion } from '@/components/matrix/DocumentSuggestions';

interface AgentChatProps {
  sessionId?: string;
  onMessageSent?: (message: string) => void;
  matrixData?: MatrixData | null;
  fundId?: string;
  mode?: 'portfolio' | 'query' | 'custom' | 'lp';
  onCellEdit?: (rowId: string, columnId: string, value: unknown, options?: { data_source?: string; metadata?: Record<string, unknown> }) => Promise<void>;
  onRunService?: (actionId: string, rowId: string, columnId: string) => Promise<void>;
  onToolCallLog?: (entry: Omit<{ action_id: string; row_id: string; column_id: string; status: 'running' | 'success' | 'error'; error?: string; companyName?: string }, 'id' | 'at'>) => void;
  availableActions?: Array<{ action_id: string; name?: string }>;
  onExportRequest?: (format: ExportFormat, payload?: { matrixData?: MatrixData; messageContent?: string }) => void;
  onRequestChart?: (chartType: 'nav' | 'dpi_sankey') => Promise<Array<{ type: string; title?: string; data: any }>>;
  onUploadDocument?: (files: File[], opts: { companyId?: string; fundId?: string }) => Promise<void>;
  onPlanStepsUpdate?: (steps: Array<{ id: string; label: string; status: 'pending' | 'running' | 'done' | 'failed'; detail?: string }>) => void;
  /** When provided, grid commands (from backend or intent) go through this callback instead of executing directly. Enables accept/reject flow. */
  onGridCommandsFromBackend?: (commands: Array<{ action: 'edit' | 'run' | 'add_document'; rowId?: string; columnId?: string; value?: unknown; actionId?: string; source_service?: string; reasoning?: string; confidence?: number; metadata?: Record<string, unknown> }>) => Promise<void>;
  /** Document/service suggestions for inline accept/reject in chat (Cursor-style) */
  suggestions?: DocumentSuggestion[];
  suggestionsLoading?: boolean;
  suggestionsError?: string | null;
  refreshSuggestions?: () => Promise<void>;
  onSuggestionAccept?: (suggestionId: string, payload?: { rowId: string; columnId: string; suggestedValue: unknown; sourceDocumentId?: string | number }) => void | Promise<void>;
  onSuggestionReject?: (suggestionId: string) => void;
  onRetrySuggestion?: (suggestion: DocumentSuggestion) => Promise<void>;
  /** Live tool runs (running/success/error) — shown inline in chat like Cursor */
  toolCallEntries?: Array<{ action_id: string; row_id: string; column_id: string; status: 'running' | 'success' | 'error'; error?: string; companyName?: string }>;
  /** Optional: highlight target cell in grid when suggestion is hovered/focused */
  onHighlightCell?: (rowId: string, columnId: string) => void;
  /** Callback when agent response contains memo_updates (sections to append/replace) */
  onMemoUpdates?: (updates: { action: string; sections: Array<{ type: string; content?: string; chart?: unknown; items?: string[]; table?: unknown }> }) => void;
  /** Current memo sections for sending as context */
  memoSections?: Array<{ type: string; content?: string }>;
  /** Emit rich analysis content to the bottom panel instead of crammed into sidebar */
  onAnalysisReady?: (analysis: {
    sections: Array<{ title?: string; content?: string; level?: number }>;
    charts: Array<{ type: string; title?: string; data: any }>;
    companies?: any[];
    capTables?: any[];
  }) => void;
}

const TOOL_ICONS: Record<string, React.ElementType> = {
  'web_search': Search,
  'discover_new_companies': Globe,
  'screen_investment_opportunity': FileSearch,
  'monitor_transactions': Activity,
  'track_exit_activity': GitBranch,
  'search_companies': Search,
  'calculate_expected_return': Calculator,
  'calculate_public_comps_valuation': BarChart3,
  'analyze_market_comparables': TrendingUp,
  'calculate_hype_vs_value': Zap,
  'run_pwerm_analysis': Target,
  'get_portfolio_metrics': DollarSign,
  'predict_exit_timing': Activity,
};

/** Build compressed matrix context for backend (< 5KB) with optional gridSnapshot for cell values */
function buildMatrixContext(matrixData: MatrixData | null | undefined, fundId?: string): MatrixContext | undefined {
  if (!matrixData?.rows?.length) return undefined;
  const gridSnapshot = buildGridSnapshot(matrixData);
  return {
    rowIds: matrixData.rows.slice(0, 50).map((r) => r.id),
    companyNames: matrixData.rows.slice(0, 50).map((r) => r.companyName || r.id),
    columns: (matrixData.columns || []).slice(0, 30).map((c) => ({ id: c.id, name: c.name || c.id })),
    fundId,
    gridSnapshot,
    summaryMetrics: matrixData.rows.length > 0
      ? {
          rowCount: matrixData.rows.length,
          columnCount: matrixData.columns?.length ?? 0,
        }
      : undefined,
  };
}

/** Parse output format from user intent: deck, docs (memo), or analysis */
function parseOutputFormatIntent(input: string): 'analysis' | 'deck' | 'docs' {
  const lower = input.toLowerCase();
  if (/\b(deck|slides|presentation|pitch deck)\b/.test(lower)) return 'deck';
  if (/\b(memo|investment memo|dd report|due diligence|docs?)\b/.test(lower)) return 'docs';
  return 'analysis';
}

/** Parse chart intent: "show portfolio NAV", "show DPI sankey" */
function parseChartIntent(input: string): 'nav' | 'dpi_sankey' | null {
  const lower = input.toLowerCase();
  if (/\b(nav|portfolio nav|nav chart|net asset)\b/.test(lower)) return 'nav';
  if (/\b(dpi|sankey|dpi flow|follow.?on)\b/.test(lower)) return 'dpi_sankey';
  return null;
}

/** Resolve company hint (e.g. "Acme", "@Acme", "Mercury") to a matrix row. */
function findRowByCompanyHint(matrixData: MatrixData, companyHint: string) {
  const clean = companyHint.replace(/^@\s*/, '').trim().toLowerCase();
  return matrixData.rows.find(
    (r) =>
      (r.companyName || '').toLowerCase().includes(clean) ||
      r.id === companyHint ||
      (r.id || '').toLowerCase() === clean
  );
}

/** Parse intent for grid actions: "run valuation", "value @X", "run pwerm for @X", "extract document for @X" */
function parseGridIntent(
  input: string,
  matrixData: MatrixData | null
): Array<{ action: 'edit' | 'run'; rowId?: string; columnId?: string; value?: unknown; actionId?: string }> | null {
  if (!matrixData?.rows?.length) return null;
  const cmds: Array<{ action: 'edit' | 'run'; rowId?: string; columnId?: string; value?: unknown; actionId?: string }> = [];
  const lower = input.toLowerCase();

  // Multi-company / fund-wide intents ("value all", "fill in everything", "value the fund")
  // → Let the backend handle via plan mode (multistep with parallel execution engine).
  // Do NOT intercept here — the backend creates plan steps, user approves, then grid_commands flow back.
  const isMultiCompanyIntent = /\b(?:value\s+(?:all|the\s+fund|every(?:thing)?|entire\s+(?:fund|portfolio))|fill\s+in\s+every(?:thing)?|run\s+(?:valuation|pwerm|dcf)\s+(?:on|for)\s+(?:all|every(?:thing)?|the\s+(?:fund|portfolio)))\b/.test(lower);
  if (isMultiCompanyIntent) {
    return null; // Pass through to backend for plan mode
  }

  // "value @X" / "value X" (valuation intent)
  const valueMatch = input.match(/\bvalue\s+@?([A-Za-z0-9_\s]+?)(?:\s|$|\.|,)/i) || lower.match(/\bvalue\s+@?([a-z0-9_\s]+)/);
  if (valueMatch) {
    const companyHint = valueMatch[1].trim().replace(/^@\s*/, '');
    const row = findRowByCompanyHint(matrixData, companyHint);
    if (row) {
      const colId = matrixData.columns.find((c) => /valuation|arr/i.test(c.id))?.id ?? 'valuation';
      cmds.push({ action: 'run', rowId: row.id, columnId: colId, actionId: 'valuation_engine.auto' });
    }
  }

  // "run valuation" / "run valuation for @X" / "run pwerm for @X" / "run dcf for X"
  const runMatch =
    lower.match(/run\s+(pwerm|valuation|dcf)\s+(?:on|for)?\s*@?([A-Za-z0-9_\s]+)?/i) ||
    lower.match(/(?:run|execute)\s+([a-z_.]+)\s+(?:on|for)\s*@?([A-Za-z0-9_\s]+)/i);
  if (runMatch) {
    const actionName = (runMatch[1] || '').toLowerCase();
    const companyHint = (runMatch[2] || '').trim().replace(/^@\s*/, '');
    const row = companyHint ? findRowByCompanyHint(matrixData, companyHint) : matrixData.rows[0];
    if (row) {
      const actionId = actionName.includes('.')
        ? actionName
        : actionName === 'pwerm'
          ? 'valuation_engine.pwerm'
          : actionName === 'valuation'
            ? 'valuation_engine.auto'
            : `valuation_engine.${actionName}`;
      const colId = matrixData.columns.find((c) => /valuation|arr/i.test(c.id))?.id ?? 'valuation';
      cmds.push({ action: 'run', rowId: row.id, columnId: colId, actionId });
    }
  }

  // "extract document for @X" / "extract document for X"
  const extractMatch = lower.match(/extract\s+document\s+(?:for|on)?\s*@?([A-Za-z0-9_\s]+)?/i);
  if (extractMatch) {
    const companyHint = (extractMatch[1] || '').trim().replace(/^@\s*/, '');
    const row = companyHint ? findRowByCompanyHint(matrixData, companyHint) : matrixData.rows[0];
    if (row) {
      const colId = matrixData.columns.find((c) => /document|citation/i.test(c.id))?.id ?? 'documents';
      cmds.push({ action: 'run', rowId: row.id, columnId: colId, actionId: 'document.extract' });
    }
  }

  // Edit valuation/ARR for X to $Y
  const editMatch = input.match(/edit\s+(valuation|arr|value)\s+(?:for|of)\s+@?([A-Za-z0-9\s]+)\s+to\s+([\$0-9.,MmBbKk%]+)/i) ||
    input.match(/set\s+(valuation|arr)\s+(?:for|of)\s+@?([A-Za-z0-9\s]+)\s+to\s+([\$0-9.,MmBbKk%]+)/i);
  if (editMatch) {
    const fieldHint = (editMatch[1] || '').toLowerCase();
    const companyHint = (editMatch[2] || '').trim().replace(/^@\s*/, '');
    const rawVal = editMatch[3];
    const row = findRowByCompanyHint(matrixData, companyHint);
    if (row) {
      const colId = fieldHint === 'arr'
        ? (matrixData.columns.find((c) => /^arr$/i.test(c.id))?.id ?? 'arr')
        : (matrixData.columns.find((c) => /valuation/i.test(c.id))?.id ?? 'valuation');
      let num: number;
      const cleaned = rawVal.replace(/[$,%\s]/g, '');
      if (/[Mm]$/.test(cleaned)) num = parseFloat(cleaned) * 1e6;
      else if (/[Bb]$/.test(cleaned)) num = parseFloat(cleaned) * 1e9;
      else if (/[Kk]$/.test(cleaned)) num = parseFloat(cleaned) * 1e3;
      else num = parseFloat(cleaned) || 0;
      if (rawVal.includes('%')) num = num / 100;
      cmds.push({ action: 'edit', rowId: row.id, columnId: colId, value: num });
    }
  }

  // Dedupe by (action, rowId, actionId or columnId) so "value @X" + "run valuation for X" don't double-run
  const seen = new Set<string>();
  const deduped = cmds.filter((c) => {
    const key = c.action === 'run' ? `${c.rowId}:run:${c.actionId}` : `${c.rowId}:edit:${c.columnId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return deduped.length > 0 ? deduped : null;
}

export default function AgentChat({ 
  sessionId = 'default', 
  onMessageSent, 
  matrixData, 
  fundId,
  mode = 'portfolio',
  onCellEdit,
  onRunService,
  onToolCallLog,
  availableActions = [],
  onExportRequest,
  onRequestChart,
  onUploadDocument,
  onPlanStepsUpdate,
  onGridCommandsFromBackend,
  suggestions = [],
  suggestionsLoading = false,
  suggestionsError = null,
  refreshSuggestions = async () => {},
  onSuggestionAccept,
  onSuggestionReject,
  onRetrySuggestion,
  toolCallEntries = [],
  onHighlightCell,
  onMemoUpdates,
  memoSections,
  onAnalysisReady,
}: AgentChatProps) {
  // --- Conversation Tabs ---
  interface ChatTab {
    id: string;
    label: string;
    messages: Message[];
    sessionId: string;
  }

  const storageKey = `agent-tabs-${fundId || 'global'}`;

  const [tabs, setTabs] = useState<ChatTab[]>(() => {
    if (typeof window === 'undefined') return [{ id: '1', label: 'Chat', messages: [], sessionId }];
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved) as ChatTab[];
        if (parsed.length > 0) return parsed.map(t => ({ ...t, messages: t.messages.map(m => ({ ...m, timestamp: new Date(m.timestamp) })) }));
      }
    } catch {}
    return [{ id: '1', label: 'Chat', messages: [], sessionId }];
  });
  const [activeTabId, setActiveTabId] = useState<string>(tabs[0]?.id || '1');

  // Persist tabs to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(tabs));
    } catch {}
  }, [tabs, storageKey]);

  // Derived: active tab
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0];

  const [messages, setMessages] = useState<Message[]>(activeTab?.messages || []);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [suggestionsCollapsed, setSuggestionsCollapsed] = useState(false);
  const [documentViewerOpen, setDocumentViewerOpen] = useState(false);
  const [documentViewerMessage, setDocumentViewerMessage] = useState<Message | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [pendingApprovedPlan, setPendingApprovedPlan] = useState(false);
  const approvedPlanStepsRef = useRef<any[]>([]);
  const workingMemoryRef = useRef<Array<{ tool: string; summary: string }>>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);
  const [droppedContext, setDroppedContext] = useState<{ type: string; content: string } | null>(null);
  const [dragOverInput, setDragOverInput] = useState(false);

  // Sync messages to active tab
  useEffect(() => {
    setTabs(prev => prev.map(t => t.id === activeTabId ? { ...t, messages } : t));
  }, [messages, activeTabId]);

  // Switch tab handler
  const switchTab = (tabId: string) => {
    // Save current messages
    setTabs(prev => prev.map(t => t.id === activeTabId ? { ...t, messages } : t));
    setActiveTabId(tabId);
    const target = tabs.find(t => t.id === tabId);
    setMessages(target?.messages || []);
  };

  const addTab = () => {
    const newId = String(Date.now());
    const newSessionId = `${sessionId}-${newId}`;
    const newTab: ChatTab = { id: newId, label: 'New Chat', messages: [], sessionId: newSessionId };
    setTabs(prev => [...prev.map(t => t.id === activeTabId ? { ...t, messages } : t), newTab]);
    setActiveTabId(newId);
    setMessages([]);
  };

  const closeTab = (tabId: string) => {
    if (tabs.length <= 1) return; // Keep at least one tab
    const remaining = tabs.filter(t => t.id !== tabId);
    setTabs(remaining);
    if (activeTabId === tabId) {
      const next = remaining[remaining.length - 1];
      setActiveTabId(next.id);
      setMessages(next.messages);
    }
  };

  const deleteMessage = (messageId: string) => {
    setMessages(prev => prev.filter(m => m.id !== messageId));
  };

  const clearChat = () => {
    setMessages([]);
  };

  // Auto-label tab from first company mention
  useEffect(() => {
    if (messages.length === 1 && messages[0].role === 'user') {
      const firstMsg = messages[0].content;
      const companyMatch = firstMsg.match(/@(\w+)/);
      if (companyMatch) {
        setTabs(prev => prev.map(t => t.id === activeTabId ? { ...t, label: companyMatch[1] } : t));
      }
    }
  }, [messages, activeTabId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, toolCallEntries.length, suggestions.length]);

  /** Collapse the multiple possible response shapes into one canonical object. */
  const normalizeResponse = (data: any) => {
    const result = data.result || data;
    return {
      result,
      planSteps: result.plan_steps ?? result.steps ?? data.plan_steps ?? data.steps,
      memoUpdates: result.memo_updates ?? data.memo_updates,
      format: result.format ?? data.format ?? 'analysis',
      companies: result.companies || data.companies || [],
      charts: result.charts || data.charts || [],
      citations: result.citations || data.citations || [],
      slides: result.slides ?? result.deck?.slides,
      suggestions: result.suggestions ?? data.suggestions,
      explanation: result.explanation ?? data.explanation,
      awaitingApproval: result.awaiting_approval ?? data.awaiting_approval ?? false,
      warnings: result.warnings ?? data.warnings ?? [],
      gridCommands: data.result?.grid_commands ?? data.grid_commands ?? [],
      memoArtifacts: result.memo_artifacts ?? data.memo_artifacts ?? null,
      memoType: result.memo_type ?? data.memo_type ?? null,
      isResumable: result.is_resumable ?? data.is_resumable ?? false,
      todos: result.todos ?? result.todo_items ?? data.todos ?? [],
    };
  };

  // Extract company name from message content
  const extractCompanyFromMessage = (content: string): string | undefined => {
    // Look for company names in common patterns
    const patterns = [
      /(?:for|about|analyzing|CIM for|profile of)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/,
      /^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:is|has|was)/,
      /company:\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)/i
    ];
    
    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }
    
    return undefined;
  };
  
  // Determine the type of response for RL feedback
  const determineResponseType = (message: Message): string => {
    const content = message.content.toLowerCase();
    const tools = message.toolsUsed || [];
    
    if (tools.includes('generate_company_cim') || content.includes('cim')) {
      return 'CIM';
    }
    if (tools.includes('calculate_expected_return') || content.includes('return')) {
      return 'Valuation';
    }
    if (tools.includes('web_search') || content.includes('search')) {
      return 'Search';
    }
    if (content.includes('market') || content.includes('competitive')) {
      return 'Market Analysis';
    }
    if (content.includes('financial') || content.includes('revenue')) {
      return 'Financial Analysis';
    }
    
    return 'General';
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // Prepend dropped context to the message if present
    const contextPrefix = droppedContext
      ? `[CONTEXT FROM MEMO]\n${droppedContext.content}\n\n[USER QUERY]\n`
      : '';
    const fullContent = contextPrefix + input;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: fullContent,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setDroppedContext(null);
    setIsLoading(true);
    onMessageSent?.(fullContent);

    const gridCommandsFromIntent = parseGridIntent(input, matrixData ?? null);
    const outputFormat = parseOutputFormatIntent(input);
    const chartIntent = parseChartIntent(input);

    // Add a placeholder assistant message
    const placeholderId = crypto.randomUUID();
    setMessages(prev => [...prev, {
      id: placeholderId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      processing: true,
    }]);

    try {
      let data: any;

      // --- Context Management: prevent context rot ---
      const currentSessionId = activeTab?.sessionId || sessionId;
      const contextMessages: Array<{role: 'user' | 'assistant' | 'system'; content: string; timestamp: Date; tools?: string[]}> = messages.map(m => ({
        role: m.role as 'user' | 'assistant' | 'system',
        content: m.content,
        timestamp: m.timestamp,
        tools: m.toolsUsed,
      }));
      let managedMessages = contextMessages;
      let contextSummary = '';
      try {
        const ctxResult = await contextManager.manageContext(contextMessages, currentSessionId);
        managedMessages = ctxResult.processedMessages;
        contextSummary = ctxResult.contextSummary;
      } catch (ctxError) {
        console.warn('Context manager failed, using raw messages:', ctxError);
      }

      // Always use unified-brain route (proxies to backend). Send grid when available so the agent can read it and resolve @mentions to rowIds for grid-run-* and grid_commands.
      const matrixContext = matrixData && (matrixData.rows?.length > 0 || matrixData.columns?.length > 0)
        ? buildMatrixContext(matrixData, fundId)
        : undefined;

      // Extract @mentions — supports multi-word names like @Safe Intelligence, @QC Design
      const companiesFromAtMentions = (input.match(/@([\w][\w\s]*[\w]|[\w]+)/g) || []).map((m) => m.slice(1).trim());

      // Also match against known grid company names (without requiring @ prefix)
      const companiesFromGrid: string[] = [];
      if (matrixContext?.companyNames) {
        const atSet = new Set(companiesFromAtMentions.map((n) => n.toLowerCase()));
        for (const name of matrixContext.companyNames) {
          if (!name || name.length < 3 || atSet.has(name.toLowerCase())) continue;
          const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          if (new RegExp(`\\b${escaped}\\b`, 'i').test(input)) {
            companiesFromGrid.push(name);
          }
        }
      }

      const companiesFromMentions = [...new Set([...companiesFromAtMentions, ...companiesFromGrid])];

      // Build agent_context for backend sync — recent analyses & conversation summary
      const recentAssistantMessages = messages
        .filter((m) => m.role === 'assistant' && m.content.length > 50)
        .slice(-3)
        .map((m) => m.content.slice(0, 500));
      const conversationSummary = messages.length > 6
        ? `${messages.length} messages. Topics: ${messages.slice(-6).map((m) => m.content.slice(0, 60)).join(' | ')}`
        : undefined;

      const isApprovedPlan = pendingApprovedPlan;
      const planStepsToSend = isApprovedPlan ? approvedPlanStepsRef.current : [];
      if (isApprovedPlan) {
        setPendingApprovedPlan(false);
        approvedPlanStepsRef.current = [];
      }

      const now = new Date();
      const requestBody = {
        prompt: input,
        // Send as hint — backend determines final format from prompt + tool results
        output_format: outputFormat,
        output_format_hint: outputFormat,
        sessionId: currentSessionId,
        context: {
          messageHistory: managedMessages.slice(-10).map((m) => ({ role: m.role, content: m.content })),
          contextSummary,
          company: companiesFromMentions[0], // Backward compat: single company
          companies: companiesFromMentions,  // Phase 1: all @mentions
          matrixContext,
          fundId,
          // Pass plan steps back so backend can execute the approved plan
          plan_steps: planStepsToSend.length > 0 ? planStepsToSend : undefined,
          // Datetime context for time-aware analysis
          datetime: {
            iso: now.toISOString(),
            date: now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
            time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            quarter: `Q${Math.ceil((now.getMonth() + 1) / 3)} ${now.getFullYear()}`,
          },
        },
        agent_context: {
          recent_analyses: recentAssistantMessages,
          active_company: companiesFromMentions[0] || null,
          fund_id: fundId || null,
          conversation_summary: conversationSummary,
          memo_section_count: memoSections?.length || 0,
          memo_title: memoSections?.[0]?.content || '',
          working_memory: workingMemoryRef.current,
          current_datetime: now.toISOString(),
        },
        approved_plan: isApprovedPlan || undefined,
        stream: true,
      };

      // Abort any in-flight request before starting a new one
      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      const res = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
        signal: abortController.signal,
      });

      if (!res.ok) {
        let errText = '';
        try { errText = await res.text(); } catch { /* ignore */ }
        const backendHint = (res.status === 503 || errText.includes('backend'))
          ? ' Ensure the backend is running: cd backend && python -m uvicorn app.main:app --port 8000'
          : '';
        throw new Error((errText || `Request failed: ${res.status}`) + backendHint);
      }

      // Handle NDJSON streaming: read progress events and final complete event
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('ndjson') && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // keep incomplete last line in buffer
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);
              if (event.type === 'progress' && onPlanStepsUpdate && event.plan_steps) {
                const steps = event.plan_steps.map((s: any, i: number) => ({
                  id: s.id ?? `step-${i}`,
                  label: s.label ?? s.action ?? `Step ${i + 1}`,
                  status: (s.status ?? 'running') as 'pending' | 'running' | 'done' | 'failed',
                  detail: s.detail,
                }));
                onPlanStepsUpdate(steps);
              } else if (event.type === 'memo_section' && event.section && onMemoUpdates) {
                // Stream memo sections to MemoEditor in real-time
                onMemoUpdates({ action: 'append', sections: [event.section] });
              } else if (event.type === 'chart_data' && event.chart) {
                // Accumulate streamed charts for final message
                if (!data) data = { success: true, result: {} };
                if (!data.result) data.result = {};
                if (!data.result.charts) data.result.charts = [];
                data.result.charts.push(event.chart);
                // Also stream charts to memo in real-time
                if (onMemoUpdates) {
                  onMemoUpdates({ action: 'append', sections: [{ type: 'chart', chart: event.chart }] });
                }
              } else if (event.type === 'complete') {
                data = event;
              } else if (event.type === 'error') {
                throw new Error(event.error || 'Backend stream error');
              }
            } catch (parseErr) {
              if (parseErr instanceof SyntaxError) continue; // skip malformed lines
              throw parseErr;
            }
          }
        }
        // Process any remaining buffer
        if (buffer.trim()) {
          try {
            const event = JSON.parse(buffer);
            if (event.type === 'complete') data = event;
          } catch { /* ignore trailing fragment */ }
        }
      } else {
        // Fallback: non-streaming JSON response
        let resBody: any;
        try {
          resBody = await res.json();
        } catch {
          throw new Error(`Backend returned invalid response (HTTP ${res.status})`);
        }
        data = resBody;
      }

      if (!data) {
        throw new Error('No response received from backend');
      }
      if (!data.success && data.error) {
        throw new Error(data.error || 'Failed to process request');
      }

      // Execute grid commands from intent or from response
      const commandsToRun = gridCommandsFromIntent ?? data.result?.grid_commands ?? data.grid_commands ?? [];
      let gridErrorSummary = '';
      const gridEditCount = commandsToRun.filter((c: any) => c.action === 'edit').length;
      const gridRunCount = commandsToRun.filter((c: any) => c.action === 'run').length;
      if (commandsToRun.length > 0) {
        if (onGridCommandsFromBackend) {
          // Route through wrapper for accept/reject flow when suggestBeforeApply is on
          await onGridCommandsFromBackend(commandsToRun);
        } else {
          // Execute grid commands by group order to support workflow chaining.
          // Group 0 = edits (parallel batches), Group 1+ = run services (sequential groups).
          const cmdErrors: string[] = [];
          const groupMap = new Map<number, typeof commandsToRun>();
          for (const cmd of commandsToRun) {
            const g = (cmd as any).group ?? (cmd.action === 'run' ? 1 : 0);
            if (!groupMap.has(g)) groupMap.set(g, []);
            groupMap.get(g)!.push(cmd);
          }
          for (const groupNum of [...groupMap.keys()].sort((a, b) => a - b)) {
            const groupCmds = groupMap.get(groupNum)!;
            for (const cmd of groupCmds) {
              try {
                if (cmd.action === 'run' && cmd.rowId && cmd.columnId && cmd.actionId && onRunService) {
                  await onRunService(cmd.actionId, cmd.rowId, cmd.columnId);
                } else if (cmd.action === 'edit' && cmd.rowId && cmd.columnId && cmd.value !== undefined && onCellEdit) {
                  await onCellEdit(cmd.rowId, cmd.columnId, cmd.value, { data_source: 'agent', metadata: { fromChat: true } });
                }
              } catch (cmdError) {
                const msg = `${cmd.action} ${cmd.columnId}: ${cmdError instanceof Error ? cmdError.message : 'failed'}`;
                cmdErrors.push(msg);
                console.error('Grid command failed:', msg);
              }
            }
          }
          if (cmdErrors.length > 0) {
            gridErrorSummary = `\n\n**${cmdErrors.length} grid update(s) failed:**\n${cmdErrors.map(e => `- ${e}`).join('\n')}`;
          }
        }
      }

      // Normalize backend response into a single canonical shape
      const norm = normalizeResponse(data);
      const result = norm.result;

      // Plan steps from backend (Plan tab)
      const rawSteps = norm.planSteps;
      if (rawSteps && Array.isArray(rawSteps) && onPlanStepsUpdate) {
        const steps = rawSteps.map((s: any, i: number) => ({
          id: s.id ?? `step-${i}`,
          label: s.label ?? s.action ?? s.title ?? `Step ${i + 1}`,
          status: (s.status ?? 'pending') as 'pending' | 'running' | 'done' | 'failed',
          detail: s.detail ?? s.result,
        }));
        onPlanStepsUpdate(steps);
      }

      // Forward memo_updates from agent response to parent
      if (norm.memoUpdates?.sections?.length && onMemoUpdates) {
        onMemoUpdates(norm.memoUpdates);
      }

      // Store resumable memo artifacts (plan memos) for cross-session context
      if (norm.memoArtifacts?.length) {
        try {
          const existing = JSON.parse(localStorage.getItem('dilla_memo_artifacts') || '[]');
          const updated = [...existing, ...norm.memoArtifacts].slice(-20); // Keep last 20
          localStorage.setItem('dilla_memo_artifacts', JSON.stringify(updated));
        } catch (e) {
          console.warn('[AgentChat] Failed to store memo artifacts:', e);
        }
      }

      // Extract plan steps for inline rendering in message
      const messagePlanSteps = rawSteps && Array.isArray(rawSteps)
        ? rawSteps.map((s: any, i: number) => ({
            id: s.id ?? `step-${i}`,
            label: s.label ?? s.action ?? s.title ?? `Step ${i + 1}`,
            status: (s.status ?? 'done') as 'pending' | 'running' | 'done' | 'failed',
            tool: s.tool,
          }))
        : undefined;
      const isAwaitingApproval = norm.awaitingApproval;

      // Extract non-cell suggestions (action items, warnings, insights)
      const agentSuggestions = norm.suggestions;

      // Extract inline todos from response (emitted by emit_todo tool)
      const rawTodos: Array<{ title: string; description?: string; priority?: string; company?: string; due?: string }> =
        result.todos ?? result.todo_items ?? data.todos ?? [];
      const todoItems = rawTodos.length > 0
        ? rawTodos.map((t: any, i: number) => ({
            id: `todo-${Date.now()}-${i}`,
            title: t.title || '',
            description: t.description,
            priority: t.priority,
            company: t.company,
            due: t.due,
            done: false,
          }))
        : undefined;

      // Extract inline memo sections from agent response (enrichment/diligence memos)
      // These render in-chat, not in a document viewer
      const responseMemoSections: Array<{ type: string; content?: string; items?: string[]; chart?: any }> | undefined =
        norm.memoUpdates?.sections?.length ? norm.memoUpdates.sections : undefined;

      // Chart from chat intent: fetch and merge
      let chartCharts: Array<{ type: string; title?: string; data: any }> = [];
      if (chartIntent && onRequestChart && fundId) {
        try {
          chartCharts = await onRequestChart(chartIntent);
        } catch (e) {
          console.warn('Chart fetch failed:', e);
        }
      }

      // Deck/docs format extraction
      const responseFormat = norm.format;
      const deckSlides = responseFormat === 'deck'
        ? (norm.slides ?? [])
        : undefined;

      // Use FormatHandlerFactory to enrich docs responses
      let docsSections: Array<{ title?: string; content?: string; level?: number }> | undefined;
      let docsCharts: Array<{ type: string; title?: string; data: any }> | undefined;
      let docsChartPositions: Array<{ afterParagraph: number; inline: boolean }> | undefined;

      const formatHandler = FormatHandlerFactory.getHandler(responseFormat);
      const hasDocContent = responseFormat === 'docs' || responseFormat === 'document' || responseFormat === 'analysis';
      // Run docs enrichment for doc formats, but also when grid commands co-exist with sections
      const shouldEnrichDocs = formatHandler && (hasDocContent || (commandsToRun.length > 0 && (result.sections?.length || result.memo?.sections?.length)));
      if (shouldEnrichDocs) {
        try {
          const handlerResult = await formatHandler.format({
            text: JSON.stringify(result),
            contextData: '',
            companiesData: [],
            financialAnalyses: result.financialAnalyses || [],
            charts: result.charts || data.charts || [],
            citations: result.citations || data.citations || [],
            requestAnalysis: {},
            skillResults: result.skill_results || {},
            extractedCompanies: (result.companies || []).map((c: any) => c.company || c.name || ''),
            mentionedCompanies: [],
          });
          if (handlerResult.success && handlerResult.result?.sections?.length) {
            docsSections = handlerResult.result.sections;
            docsCharts = handlerResult.result.charts || [];
            docsChartPositions = handlerResult.result.chartPositions || [];
          }
        } catch (e) {
          console.warn('[FormatHandler] Enrichment failed, falling back:', e);
        }
      }

      // Fallback: extract docs sections directly if handler didn't produce them
      if (!docsSections?.length) {
        const rawSections = result.sections ?? result.memo?.sections ?? result.docs?.sections;
        if (Array.isArray(rawSections) && rawSections.length > 0) {
          docsSections = rawSections;
        }
      }

      // Extract the agent synthesis early so it is available for fallback parsing
      const synthesis = result.content || result.summary || result.synthesis || '';

      // Last resort: parse synthesis markdown into sections for memo when content is substantial
      if (!docsSections?.length && typeof synthesis === 'string' && synthesis.length > 200) {
        const parsed = parseMarkdownToSections(synthesis);
        if (parsed.length > 1) {
          docsSections = parsed.map(s => ({
            title: s.title || (s.type?.startsWith('heading') ? s.content : undefined),
            content: s.type === 'paragraph' || s.type === 'list' ? (s.content || s.items?.join('\n')) : s.content,
            level: s.level ?? 2,
          }));
        }
      }

      // --- Composite content generation ---
      // Chat is NOT the primary output. The memo is. Chat gets a brief summary.
      // Rich content (sections, charts, analysis) routes to memo/document viewer.
      let content = '';
      let capTables: any[] = [];
      let citations: any[] = [];

      const companies = norm.companies;
      const allCitations = norm.citations;

      // Extract cap tables from companies (used by memo/viewer, not chat)
      if (companies && companies.length > 0) {
        companies.forEach((company: any) => {
          const companyName = company.company || company.name || '';
          if (company.cap_table) {
            capTables.push({ company: companyName, capTable: company.cap_table });
          }
        });
      }

      // Store citations for structured rendering (not dumped in chat text)
      if (allCitations && allCitations.length > 0) {
        citations = allCitations;
      }

      // Determine if this response has rich content that belongs in memo, not chat
      const hasRichContent = (docsSections?.length ?? 0) > 0
        || (norm.charts?.length ?? 0) > 0
        || (companies?.length ?? 0) > 0
        || (deckSlides?.length ?? 0) > 0
        || (typeof synthesis === 'string' && synthesis.length > 300);

      // 1. Use synthesis (extracted above) as chat content
      if (typeof synthesis === 'string' && synthesis.trim().length > 10) {
        content = synthesis;
      }

      // 2. If we have rich content, truncate chat to a brief pointer
      if (hasRichContent && content.length > 600) {
        // Keep first ~3 sentences as a chat summary
        const sentences = content.match(/[^.!?]+[.!?]+/g) || [content];
        content = sentences.slice(0, 3).join(' ').trim();
      }

      // 3. Deck format: brief summary only
      if (deckSlides?.length) {
        content = content
          ? `${content.slice(0, 300)}\n\n**Deck ready** — ${deckSlides.length} slides generated.`
          : `**Investment deck generated** — ${deckSlides.length} slides. Click to preview.`;
      }

      // 4. Docs/memo format: brief pointer to the memo
      if (docsSections?.length && !content) {
        const title = docsSections[0]?.title || 'Analysis';
        content = `**${title}** — written to memo. Click "View Document" to read.`;
      } else if (docsSections?.length && content) {
        // Ensure chat doesn't repeat what's in the memo
        content = content.slice(0, 400);
      }

      // 5. Company analysis: brief summary, not a data dump
      if (companies?.length && !content) {
        const names = companies.map((c: any) => c.company || c.name).filter(Boolean);
        content = `Analysis of ${names.join(', ')} complete. See memo for details.`;
      }

      // 6. Fallback for truly empty responses — keep it brief
      if (!content) {
        const fallbackFields = [
          result.analysis?.executive_summary,
          typeof (data.analysis || data.synthesis || result.text) === 'string' ? (data.analysis || data.synthesis || result.text) : null,
          result.summary,
          result.analysis_text,
          typeof result.explanation === 'string' ? result.explanation : result.explanation?.reasoning,
          result.portfolio_summary || result.fund_summary,
          result.insight || result.response || result.answer || result.message,
        ].filter((v): v is string => typeof v === 'string' && v.trim().length > 10);

        if (fallbackFields.length > 0) {
          // Take the first meaningful field, cap at ~500 chars
          content = fallbackFields[0].slice(0, 500);
        } else {
          content = 'Analysis complete.';
        }
      }

      // Auto-generate memo_updates from rich response data when backend didn't explicitly provide them
      // This ensures analysis always flows to the memo, not just chat
      if (!norm.memoUpdates?.sections?.length && hasRichContent && onMemoUpdates) {
        const autoSections: Array<{ type: string; content?: string; chart?: unknown; items?: string[] }> = [];

        // Add text sections from docs or synthesis (use MemoEditor-compatible types)
        if (docsSections?.length) {
          for (const sec of docsSections) {
            if (sec.title) {
              autoSections.push({ type: 'heading2', content: sec.title });
            }
            if (sec.content) {
              autoSections.push({ type: 'paragraph', content: sec.content });
            }
          }
        } else if (typeof synthesis === 'string' && synthesis.length > 100) {
          autoSections.push({ type: 'paragraph', content: synthesis });
        }

        // Add charts as memo sections
        if (norm.charts?.length) {
          for (const chart of norm.charts) {
            autoSections.push({ type: 'chart', chart });
          }
        }

        // Add citations
        if (allCitations?.length) {
          const citationText = allCitations
            .filter((c: any) => c.url)
            .map((c: any, i: number) => `${i + 1}. [${c.source || c.title || 'Source'}](${c.url})`)
            .join('\n');
          if (citationText) {
            autoSections.push({ type: 'heading3', content: 'Sources' });
            autoSections.push({ type: 'paragraph', content: citationText });
          }
        }

        if (autoSections.length > 0) {
          onMemoUpdates({ action: 'append', sections: autoSections });
        }
      }
      
      const toolsUsed = data.tool_calls?.map((tc: any) => tc.tool) || 
                        data.metadata?.tools_used || 
                        (result.metadata ? result.metadata.entities?.actions || [] : []);
      
      // Charts: ALWAYS route to memo/document viewer, never inline in chat sidebar.
      // Charts in a narrow sidebar are unreadable and drag the page.
      const allCharts = [...norm.charts, ...chartCharts];
      let charts: typeof allCharts = []; // Never render charts inline in chat
      if (allCharts.length > 0) {
        if (!docsCharts) docsCharts = [];
        docsCharts.push(...allCharts.map(c => ({ type: c.type, title: c.title, data: c.data })));
        // Ensure we have at least a minimal section so the document viewer opens
        if (!docsSections?.length) {
          docsSections = [{ title: 'Analysis', content: content || 'See charts below.', level: 1 }];
        }
        // Add a note in chat that charts are in the memo
        if (!content.includes('chart') && !content.includes('memo')) {
          content += `\n\n${allCharts.length} chart${allCharts.length > 1 ? 's' : ''} added to memo.`;
        }
      }

      // Explanation block from backend
      const explanation = norm.explanation;

      // Matrix snippets when we have companies and matrixData
      const matrixSnippets: MatrixSnippetData[] = [];
      if (matrixData && companies.length > 0) {
        const companiesToShow = companies;
        const names = companiesToShow.map((c: any) => c.company || c.name || '').filter(Boolean);
        const matchingRows = names.length
          ? matrixData.rows.filter((r) => names.some((n: string) => (r.companyName || '').toLowerCase().includes((n || '').toLowerCase())))
          : matrixData.rows.slice(0, 5);
        if (matchingRows.length > 0) {
          matrixSnippets.push({
            rowIds: matchingRows.map((r) => r.id),
            columnIds: ['company', 'valuation', 'arr', 'sector'].filter((id) => matrixData.columns.some((c) => c.id === id)),
            title: 'Grid snippet',
          });
        }
      }

      // Append grid suggestion summary and errors to visible content
      if (gridEditCount > 0 || gridRunCount > 0) {
        const parts: string[] = [];
        if (gridEditCount > 0) parts.push(`${gridEditCount} value${gridEditCount > 1 ? 's' : ''}`);
        if (gridRunCount > 0) parts.push(`${gridRunCount} service${gridRunCount > 1 ? 's' : ''}`);
        content += `\n\n---\n**Grid updated:** ${parts.join(' + ')} added as suggestions for review.`;
      }
      if (gridErrorSummary) {
        content += gridErrorSummary;
      }
      const backendWarnings: string[] = norm.warnings;
      if (backendWarnings.length > 0) {
        content += `\n\n**Warnings:**\n${backendWarnings.map((w: string) => `- ${w}`).join('\n')}`;
      }

      // Capture working memory for session continuity
      const wm = result.working_memory ?? data.working_memory;
      if (Array.isArray(wm) && wm.length > 0) {
        workingMemoryRef.current = wm.slice(-20); // keep last 20 entries to bound size
      }

      // Update the placeholder message with the actual response
      setMessages(prev => prev.map(msg =>
        msg.id === placeholderId
          ? {
              ...msg,
              content,
              toolsUsed,
              charts,
              capTables,
              citations,
              explanation,
              gridCommands: commandsToRun.length > 0 ? commandsToRun : undefined,
              matrixSnippets: matrixSnippets.length > 0 ? matrixSnippets : undefined,
              analysisData: data.results || data,
              companies: companies,
              deckSlides: deckSlides?.length ? deckSlides : undefined,
              docsSections: docsSections?.length ? docsSections : undefined,
              docsCharts: docsCharts?.length ? docsCharts : undefined,
              docsChartPositions: docsChartPositions?.length ? docsChartPositions : undefined,
              planSteps: messagePlanSteps?.length ? messagePlanSteps : undefined,
              awaitingApproval: isAwaitingApproval || undefined,
              agentSuggestions: agentSuggestions?.length ? agentSuggestions : undefined,
              todoItems: todoItems?.length ? todoItems : undefined,
              memoSections: responseMemoSections?.length ? responseMemoSections : undefined,
              processing: false,
            }
          : msg
      ));

      // Emit rich analysis to bottom panel when we have docs content
      if (onAnalysisReady && docsSections?.length) {
        onAnalysisReady({
          sections: docsSections,
          charts: docsCharts || charts || [],
          companies: companies,
          capTables: capTables,
        });
      }

      // AUTO-OPEN document viewer when docs/memo sections arrive
      if (docsSections?.length) {
        // Small delay to ensure message is rendered before opening viewer
        setTimeout(() => {
          setMessages(prev => {
            const updated = prev.find(m => m.id === placeholderId);
            if (updated) {
              openDocumentViewer(updated);
            }
            return prev;
          });
        }, 300);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      // Update placeholder with error message
      setMessages(prev => prev.map(msg => 
        msg.id === placeholderId 
          ? {
              ...msg,
              content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`,
              processing: false,
            }
          : msg
      ));
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    e.target.value = '';
    if (!files.length || !onUploadDocument) return;
    setUploading(true);
    try {
      let companyId: string | undefined;
      const rowsWithCompany = matrixData?.rows.filter((r) => r.companyId) ?? [];
      if (rowsWithCompany.length === 1) {
        companyId = rowsWithCompany[0].companyId;
      } else if (rowsWithCompany.length > 1) {
        companyId = rowsWithCompany[0].companyId;
      }
      await onUploadDocument(files, { companyId, fundId });
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  /** Open document in A4 viewer popover */
  const openDocumentViewer = (message: Message) => {
    setDocumentViewerMessage(message);
    setDocumentViewerOpen(true);
  };

  /** Export document as PDF via memo export endpoint */
  const handlePdfExport = async (message: Message) => {
    if (!message.docsSections?.length) return;
    setExportingPdf(true);
    try {
      const res = await fetch('/api/memos/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections: message.docsSections,
          charts: message.docsCharts || message.charts || [],
          title: message.docsSections[0]?.title || 'Investment Memo',
          companies: message.companies?.map((c: any) => c.company || c.name) || [],
        }),
      });
      if (!res.ok) {
        const errText = await res.text().catch(() => 'Unknown error');
        throw new Error(`PDF export failed: ${errText}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(message.docsSections[0]?.title || 'memo').replace(/\s+/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setExportingPdf(false);
    }
  };

  /** Inline suggestion card with tooltips: full cell label, reasoning, sourceService */
  const renderSuggestionCard = (s: DocumentSuggestion) => {
    const row = matrixData?.rows?.find((r) => r.id === s.rowId);
    const col = matrixData?.columns?.find((c) => c.id === s.columnId);
    const cellLabel = [row?.companyName ?? row?.id ?? s.rowId, col?.name ?? s.columnId].filter(Boolean).join(' · ') || `${s.rowId} · ${s.columnId}`;
    const currentStr = formatSuggestionValue(s.currentValue, s.columnId);
    const suggestedStr = formatSuggestionValue(s.suggestedValue, s.columnId);
    const hasReasoning = s.reasoning?.trim().length > 0;
    return (
      <div
        key={s.id}
        className="flex flex-col gap-1 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-2.5 py-2 min-w-0 text-[11px]"
        onMouseEnter={() => onHighlightCell?.(s.rowId, s.columnId)}
        onMouseLeave={() => onHighlightCell?.('', '')}
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="shrink-0 text-foreground font-medium truncate max-w-full" title={cellLabel}>
                {cellLabel}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[240px]">
              <p className="font-medium">{cellLabel}</p>
              {hasReasoning && <p className="text-muted-foreground mt-1 text-xs">{s.reasoning}</p>}
            </TooltipContent>
          </Tooltip>
          {s.source === 'service' && s.sourceService && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge variant="outline" className="text-[10px] px-1 py-0 capitalize shrink-0">
                  {s.sourceService.replace(/[._]/g, ' ')}
                </Badge>
              </TooltipTrigger>
              <TooltipContent>Source: {s.sourceService}</TooltipContent>
            </Tooltip>
          )}
        </div>
        <div className="flex items-center gap-1.5 min-w-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="truncate text-muted-foreground max-w-[100px]">{currentStr}</span>
            </TooltipTrigger>
            <TooltipContent>Current: {currentStr}</TooltipContent>
          </Tooltip>
          <span className="shrink-0 text-muted-foreground">→</span>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="truncate font-medium max-w-[100px]">{suggestedStr}</span>
            </TooltipTrigger>
            <TooltipContent>Suggested: {suggestedStr}</TooltipContent>
          </Tooltip>
          <div className="flex items-center gap-0.5 shrink-0 ml-auto">
            {hasReasoning && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-muted-foreground cursor-help px-0.5" aria-label="Reasoning">ⓘ</span>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-[260px]">
                  <p className="text-xs">{s.reasoning}</p>
                </TooltipContent>
              </Tooltip>
            )}
            {s.source === 'service' && onRetrySuggestion && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" onClick={() => onRetrySuggestion(s)} className="p-0.5 rounded hover:bg-muted" aria-label="Retry">
                    <RotateCcw className="h-3 w-3" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Retry</TooltipContent>
              </Tooltip>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" onClick={() => onSuggestionReject?.(s.id)} className="p-0.5 rounded hover:bg-destructive/20 text-muted-foreground hover:text-destructive" aria-label="Reject">
                  <X className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Reject</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={async () => {
                    if (!onSuggestionAccept) return;
                    try {
                      await Promise.resolve(onSuggestionAccept(s.id, { rowId: s.rowId, columnId: s.columnId, suggestedValue: s.suggestedValue, sourceDocumentId: s.sourceDocumentId }));
                    } catch (err) {
                      console.warn('Suggestion accept failed:', err);
                    }
                  }}
                  className="p-0.5 rounded hover:bg-primary/20 text-muted-foreground hover:text-primary"
                  aria-label="Accept"
                >
                  <Check className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Accept</TooltipContent>
            </Tooltip>
          </div>
        </div>
        {hasReasoning && (
          <p className="text-muted-foreground text-[10px] line-clamp-2 mt-0.5" title={s.reasoning}>
            {s.reasoning}
          </p>
        )}
      </div>
    );
  };

  return (
    <TooltipProvider>
      <div className="flex flex-col h-full min-h-0 w-full max-w-full">
        {/* Tab bar */}
        <div className="flex items-center gap-0.5 px-1 pt-1 pb-0 bg-muted/30 border-b border-border overflow-x-auto shrink-0">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => switchTab(tab.id)}
              className={`group flex items-center gap-1 px-2 py-1 text-[11px] rounded-t-md border border-b-0 transition-colors ${
                tab.id === activeTabId
                  ? 'bg-background text-foreground border-border'
                  : 'bg-muted/50 text-muted-foreground border-transparent hover:bg-muted'
              }`}
            >
              <span className="truncate max-w-[80px]">{tab.label}</span>
              {tabs.length > 1 && (
                <X
                  className="w-3 h-3 opacity-0 group-hover:opacity-100 hover:text-destructive cursor-pointer shrink-0"
                  onClick={(e) => { e.stopPropagation(); closeTab(tab.id); }}
                />
              )}
            </button>
          ))}
          <button
            onClick={addTab}
            className="px-1.5 py-1 text-muted-foreground hover:text-foreground text-[11px]"
            title="New chat"
          >
            +
          </button>
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="ml-auto px-1.5 py-1 text-muted-foreground hover:text-destructive text-[11px] flex items-center gap-0.5"
              title="Clear chat"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
        {/* Scroll only this content; input stays fixed at bottom */}
        <div className="flex-1 min-h-0 overflow-y-auto bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
          <div className="p-3 min-w-0">
            {messages.length === 0 && toolCallEntries.length === 0 && suggestions.length === 0 && !suggestionsLoading ? (
              <div className="flex flex-col items-center justify-center h-full space-y-2 min-w-0 px-1">
                <div className="text-center space-y-1 w-full min-w-0">
                  <p className="text-muted-foreground text-xs break-words overflow-hidden">
                    Ask a question, run a valuation, or type <kbd className="px-1 py-0.5 rounded bg-muted text-[10px] font-mono">@company</kbd> to analyze
                  </p>
                </div>
              </div>
            ) : (
            <div className="space-y-2 min-w-0">
              {messages.map((message, idx) => {
                const prevUserMessage = idx > 0 && messages[idx - 1]?.role === 'user' ? messages[idx - 1].content : undefined;
                return (
                <div
                  key={message.id}
                  className={`flex gap-2 min-w-0 ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`group relative max-w-[92%] min-w-0 rounded-lg px-2 py-1 text-xs ${
                      message.role === 'user'
                        ? 'bg-gradient-to-r from-gray-600 to-gray-700 text-white'
                        : 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800'
                    }`}
                  >
                    {message.processing ? (
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Analyzing...</span>
                      </div>
                    ) : (
                      <>
                        <div className="prose prose-xs dark:prose-invert max-w-none break-words overflow-wrap-anywhere text-xs leading-snug max-h-[200px] overflow-y-auto">
                          <ReactMarkdown
                            components={{
                              code({ node, className, children, ...props }: any) {
                                const inline = node?.position === undefined;
                                const match = /language-(\w+)/.exec(className || '');
                                return !inline && match ? (
                                  <SyntaxHighlighter
                                    style={atomDark}
                                    language={match[1]}
                                    PreTag="div"
                                    customStyle={{ fontSize: '10px' }}
                                    {...props}
                                  >
                                    {String(children).replace(/\n$/, '')}
                                  </SyntaxHighlighter>
                                ) : (
                                  <code className={className} {...props}>
                                    {children}
                                  </code>
                                );
                              },
                              a({ node, className, children, href, ...props }: any) {
                                return (
                                  <a
                                    href={href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 underline font-medium transition-colors"
                                    {...props}
                                  >
                                    {children}
                                  </a>
                                );
                              },
                              p({ node, className, children, ...props }: any) {
                                return (
                                  <p className="mb-1.5 leading-snug" {...props}>
                                    {children}
                                  </p>
                                );
                              },
                              h1({ node, className, children, ...props }: any) {
                                return (
                                  <h1 className="text-sm font-bold mb-1.5 mt-2 text-gray-900 dark:text-gray-100" {...props}>
                                    {children}
                                  </h1>
                                );
                              },
                              h2({ node, className, children, ...props }: any) {
                                return (
                                  <h2 className="text-xs font-semibold mb-1 mt-2 text-gray-800 dark:text-gray-200" {...props}>
                                    {children}
                                  </h2>
                                );
                              },
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>

                        {/* Compact company badges — full analysis is in memo */}
                        {message.companies && message.companies.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {message.companies.map((company: CompanyAnalysisData, idx: number) => (
                              <Badge key={idx} variant="outline" className="text-[10px]">
                                {company.company || company.name || `Company ${idx + 1}`}
                              </Badge>
                            ))}
                          </div>
                        )}

                        {/* Charts are NEVER rendered inline — they go to memo.
                            Show a compact indicator instead */}
                        {message.charts && message.charts.length > 0 && (
                          <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                            <BarChart3 className="h-3 w-3" />
                            <span>{message.charts.length} chart{message.charts.length > 1 ? 's' : ''} in memo</span>
                          </div>
                        )}

                        {/* Deck: compact summary, not inline slides */}
                        {message.deckSlides && message.deckSlides.length > 0 && (
                          <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                            <FileTextIcon className="h-3 w-3" />
                            <span>{message.deckSlides.length} slides generated</span>
                          </div>
                        )}

                        {/* Docs/memo: view document + export buttons */}
                        {message.docsSections && message.docsSections.length > 0 && (
                          <div className="mt-3 flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-xs gap-1.5"
                              onClick={() => openDocumentViewer(message)}
                            >
                              <Maximize2 className="h-3 w-3" />
                              View Document
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-xs gap-1.5"
                              onClick={() => handlePdfExport(message)}
                              disabled={exportingPdf}
                            >
                              {exportingPdf
                                ? <Loader2 className="h-3 w-3 animate-spin" />
                                : <Download className="h-3 w-3" />}
                              Export PDF
                            </Button>
                          </div>
                        )}

                        {/* Cap tables inline — ownership bar style */}
                        {message.capTables && message.capTables.length > 0 && (
                          <div className="mt-3 space-y-3">
                            {message.capTables.map((item: any, idx: number) => (
                              <div key={idx} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 bg-gray-50/50 dark:bg-gray-800/30">
                                <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{item.company} — Ownership</span>
                                {item.capTable?.investors && (
                                  <div className="mt-1.5 space-y-0.5">
                                    {item.capTable.investors.slice(0, 8).map((inv: any, invIdx: number) => (
                                      <div key={invIdx} className="flex items-center gap-2 text-[11px]">
                                        <span className="truncate flex-1 min-w-0">{inv.name}</span>
                                        {inv.round && <span className="text-muted-foreground text-[10px] shrink-0">{inv.round}</span>}
                                        <div className="w-20 shrink-0 flex items-center gap-1">
                                          <div className="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                                            <div className="h-full rounded-full bg-blue-500 dark:bg-blue-400" style={{ width: `${Math.min((inv.ownership * 100), 100)}%` }} />
                                          </div>
                                          <span className="tabular-nums text-[10px] w-10 text-right">{(inv.ownership * 100).toFixed(1)}%</span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {item.capTable?.liquidation_stack && item.capTable.liquidation_stack.length > 0 && (
                                  <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Liquidation Preferences</span>
                                    <div className="mt-1 space-y-0.5">
                                      {item.capTable.liquidation_stack.map((liq: any, li: number) => (
                                        <div key={li} className="flex items-center gap-2 text-[11px]">
                                          <span className="text-muted-foreground w-4 text-right shrink-0">{li + 1}.</span>
                                          <span className="truncate flex-1 min-w-0">{liq.investor}</span>
                                          <span className="tabular-nums shrink-0">${(liq.amount / 1e6).toFixed(1)}M</span>
                                          <span className="text-muted-foreground shrink-0">{liq.multiple}x</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Matrix snippets inline with message */}
                        {message.matrixSnippets && matrixData && message.matrixSnippets.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {message.matrixSnippets.map((snippet, idx) => {
                              const rows = matrixData.rows.filter((r) => snippet.rowIds.includes(r.id));
                              const cols = snippet.columnIds
                                ? matrixData.columns.filter((c) => snippet.columnIds!.includes(c.id))
                                : matrixData.columns.slice(0, 6);
                              return (
                                <MatrixSnippet
                                  key={idx}
                                  rows={rows}
                                  columns={cols}
                                  title={snippet.title}
                                  maxRows={5}
                                />
                              );
                            })}
                          </div>
                        )}

                        {/* Plan steps progress (inline in chat flow) */}
                        {message.planSteps && message.planSteps.length > 0 && (
                          <div className="mt-2 space-y-0.5">
                            {message.planSteps.map((step: any) => (
                              <div key={step.id} className="flex items-center gap-1.5 text-xs">
                                {step.status === 'running' && <Loader2 className="h-3 w-3 animate-spin text-blue-500" />}
                                {step.status === 'done' && <Check className="h-3 w-3 text-green-500" />}
                                {step.status === 'failed' && <X className="h-3 w-3 text-red-500" />}
                                {step.status === 'pending' && <div className="h-3 w-3 rounded-full border border-gray-300" />}
                                <span className={step.status === 'done' ? 'text-muted-foreground' : ''}>{step.label}</span>
                                {step.tool && <Badge variant="outline" className="text-[9px] h-4 px-1">{step.tool}</Badge>}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Plan approval card (ephemeral — not saved) */}
                        {message.awaitingApproval && message.planSteps && message.planSteps.length > 0 && (
                          <div className="border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/30 rounded-lg p-3 my-2">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs font-medium">Execution Plan</span>
                              <span className="text-[10px] text-muted-foreground">Saved to memo on Execute</span>
                            </div>
                            <ol className="space-y-1 text-xs mb-3">
                              {message.planSteps.map((s: any, i: number) => (
                                <li key={s.id} className="flex items-center gap-2">
                                  <span className="text-muted-foreground w-4">{i + 1}.</span>
                                  <span>{s.label}</span>
                                  {s.tool && <Badge variant="outline" className="text-[9px] h-4 px-1">{s.tool}</Badge>}
                                </li>
                              ))}
                            </ol>
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                className="h-6 text-xs gap-1"
                                onClick={() => {
                                  const approvedPrompt = messages.slice().reverse().find(m => m.role === 'user')?.content;
                                  if (approvedPrompt) {
                                    // Auto-save plan steps to memo before executing
                                    if (onMemoUpdates && message.planSteps) {
                                      onMemoUpdates({
                                        action: 'append',
                                        sections: [
                                          { type: 'heading2', content: `Plan: ${approvedPrompt.slice(0, 60)}` },
                                          ...message.planSteps.map((s: any) => ({
                                            type: 'paragraph' as const,
                                            content: `${s.label}${s.tool ? ` [${s.tool}]` : ''}`,
                                          })),
                                        ],
                                      });
                                    }
                                    // Mark plan as approved so it won't re-trigger plan mode
                                    setMessages(prev => prev.map(m => m.id === message.id ? { ...m, awaitingApproval: false } : m));
                                    // Store plan steps so they're sent back to backend for guided execution
                                    approvedPlanStepsRef.current = message.planSteps || [];
                                    // Set the approved flag and input, then auto-submit
                                    setPendingApprovedPlan(true);
                                    setInput(approvedPrompt);
                                    // Auto-submit after state update (handleSend reads input from state)
                                    setTimeout(() => handleSend(), 50);
                                  }
                                }}
                              >
                                <PlayCircle className="h-3 w-3" />
                                Execute
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-xs"
                                onClick={() => setMessages(prev => prev.map(m => m.id === message.id ? { ...m, awaitingApproval: false } : m))}
                              >
                                Dismiss
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* Agent suggestions: action items, warnings, insights (inline) */}
                        {message.agentSuggestions && message.agentSuggestions.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {message.agentSuggestions.map((s: any, i: number) => (
                              <div key={i} className={`flex items-start gap-2 p-2 rounded text-xs ${
                                s.type === 'warning' ? 'bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800' :
                                s.type === 'action_item' ? 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800' :
                                'bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700'
                              }`}>
                                {s.type === 'warning' && <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0 mt-0.5" />}
                                {s.type === 'action_item' && <Target className="h-3 w-3 text-blue-500 shrink-0 mt-0.5" />}
                                {s.type === 'insight' && <Lightbulb className="h-3 w-3 text-gray-500 shrink-0 mt-0.5" />}
                                <div>
                                  <p className="font-medium">{s.title}</p>
                                  <p className="text-muted-foreground">{s.description}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Inline todos: checkable action items from agent */}
                        {message.todoItems && message.todoItems.length > 0 && (
                          <div className="mt-2 space-y-1">
                            <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">Action Items</p>
                            {message.todoItems.map((todo) => (
                              <div
                                key={todo.id}
                                className={`flex items-start gap-2 p-2 rounded text-xs border ${
                                  todo.done
                                    ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800 opacity-60'
                                    : 'bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800'
                                }`}
                              >
                                <button
                                  className="shrink-0 mt-0.5"
                                  onClick={() => {
                                    setMessages(prev => prev.map(m =>
                                      m.id === message.id
                                        ? {
                                            ...m,
                                            todoItems: m.todoItems?.map(t =>
                                              t.id === todo.id ? { ...t, done: !t.done } : t
                                            ),
                                          }
                                        : m
                                    ));
                                  }}
                                >
                                  {todo.done
                                    ? <Check className="h-3.5 w-3.5 text-green-600" />
                                    : <div className="h-3.5 w-3.5 border border-blue-400 rounded-sm" />
                                  }
                                </button>
                                <div className="flex-1 min-w-0">
                                  <p className={`font-medium ${todo.done ? 'line-through' : ''}`}>
                                    {todo.title}
                                    {todo.company && (
                                      <span className="ml-1 text-[10px] text-muted-foreground">@{todo.company}</span>
                                    )}
                                  </p>
                                  {todo.description && (
                                    <p className="text-muted-foreground">{todo.description}</p>
                                  )}
                                </div>
                                {todo.priority && (
                                  <Badge variant="outline" className={`text-[9px] h-4 ${
                                    todo.priority === 'high' ? 'border-red-300 text-red-600' :
                                    todo.priority === 'low' ? 'border-gray-300 text-gray-500' :
                                    'border-blue-300 text-blue-600'
                                  }`}>
                                    {todo.priority}
                                  </Badge>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Inline memo sections: stream of consciousness from enrichment/diligence */}
                        {message.memoSections && message.memoSections.length > 0 && (
                          <div className="mt-3 space-y-1.5 border-l-2 border-indigo-300 dark:border-indigo-700 pl-3">
                            {message.memoSections.map((section: any, i: number) => {
                              if (section.type === 'heading1') {
                                return <p key={i} className="text-sm font-semibold text-foreground">{section.content}</p>;
                              }
                              if (section.type === 'heading2') {
                                return <p key={i} className="text-xs font-semibold text-foreground mt-2">{section.content}</p>;
                              }
                              if (section.type === 'heading3') {
                                return <p key={i} className="text-xs font-medium text-muted-foreground mt-1">{section.content}</p>;
                              }
                              if (section.type === 'list' && section.items) {
                                return (
                                  <ul key={i} className="text-xs text-muted-foreground space-y-0.5 ml-2">
                                    {section.items.map((item: string, j: number) => (
                                      <li key={j} className="flex gap-1.5">
                                        <span className="text-indigo-400 shrink-0">•</span>
                                        <span dangerouslySetInnerHTML={{ __html: item.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>') }} />
                                      </li>
                                    ))}
                                  </ul>
                                );
                              }
                              if (section.type === 'paragraph' && section.content) {
                                return <p key={i} className="text-xs text-muted-foreground">{section.content}</p>;
                              }
                              return null;
                            })}
                          </div>
                        )}

                        {/* Explanation (collapsible, subtle) */}
                        {message.explanation && (message.explanation.steps?.length || message.explanation.method || message.explanation.reasoning) && (
                          <details className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                            <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                              Explanation
                            </summary>
                            <div className="mt-2 space-y-1 text-xs text-gray-600 dark:text-gray-400">
                              {message.explanation.steps?.map((s, i) => (
                                <div key={i}>• {s.action}{s.result ? `: ${s.result}` : ''}</div>
                              ))}
                              {message.explanation.method && <div>Method: {message.explanation.method}</div>}
                              {message.explanation.reasoning && <div>{message.explanation.reasoning}</div>}
                            </div>
                          </details>
                        )}

                        {/* Rich citations: source (blue), document (green), reasoning (amber) */}
                        {message.citations && message.citations.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-800">
                            <div className="flex flex-wrap gap-1">
                              {message.citations.slice(0, 8).map((citation: any, idx: number) => {
                                const cType = citation.type || 'source';
                                return (
                                  <span key={idx} className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full ${
                                    cType === 'source' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' :
                                    cType === 'document' ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300' :
                                    'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
                                  }`}>
                                    {cType === 'source' && citation.url ? (
                                      <a href={citation.url} target="_blank" rel="noopener noreferrer" className="underline truncate max-w-[200px]">
                                        {citation.source || citation.title || citation.url}
                                      </a>
                                    ) : cType === 'reasoning' ? (
                                      <span title={citation.content}>{citation.title || 'Reasoning'}</span>
                                    ) : (
                                      <span>{citation.source || citation.title || `Doc ${idx + 1}`}</span>
                                    )}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Retry button when tools failed */}
                        {message.toolsFailed && message.toolsFailed.length > 0 && (
                          <div className="mt-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-xs"
                              onClick={() => {
                                setInput(prevUserMessage || message.content.slice(0, 100));
                                textareaRef.current?.focus();
                              }}
                            >
                              <RotateCcw className="h-3 w-3 mr-1" />
                              Retry
                            </Button>
                          </div>
                        )}
                        
                        {/* Tools used (inline, same bubble) */}
                        {message.toolsUsed && message.toolsUsed.length > 0 && (
                          <div className="flex flex-wrap gap-2 mt-2">
                            {message.toolsUsed.map((tool, idx) => {
                              const Icon = TOOL_ICONS[tool] || Sparkles;
                              return (
                                <Badge
                                  key={idx}
                                  variant="secondary"
                                  className="text-xs flex items-center gap-1"
                                >
                                  <Icon className="h-3 w-3" />
                                  {tool.replace(/_/g, ' ')}
                                </Badge>
                              );
                            })}
                          </div>
                        )}
                        
                        {/* RL Feedback Component */}
                        {message.role === 'assistant' && !message.processing && (
                          <AgentFeedback
                            sessionId={sessionId}
                            messageId={message.id}
                            company={extractCompanyFromMessage(message.content)}
                            responseType={determineResponseType(message)}
                            query={idx > 0 && messages[idx - 1]?.role === 'user' ? messages[idx - 1].content : ''}
                            response={message.content}
                            onFeedback={(feedback) => {
                              console.log('[AgentChat] Feedback received:', feedback.feedbackType, feedback.company);
                            }}
                          />
                        )}
                        
                        {/* Message Actions */}
                        {!message.processing && (
                          <div className="absolute -bottom-8 right-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-800 p-1">
                            {message.role === 'assistant' && (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 w-7 p-0"
                                onClick={() => copyToClipboard(message.content)}
                              >
                                <Copy className="h-3 w-3" />
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 w-7 p-0 hover:text-destructive"
                              onClick={() => deleteMessage(message.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  
                  {message.role === 'user' && (
                    <div className="h-8 w-8 border-2 border-gray-500/20 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center">
                      <User className="h-5 w-5 text-white" />
                    </div>
                  )}
                </div>
                );
              })}

              {/* Tool runs: inline in message flow */}
              {toolCallEntries.length > 0 && (
                <div className="flex justify-start">
                  <div className="max-w-[95%] rounded-lg px-2.5 py-1.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 min-w-0 space-y-1">
                    {toolCallEntries.map((entry, entryIdx) => {
                      const Icon = TOOL_ICONS[entry.action_id] || Sparkles;
                      const label = (entry.action_id || '').replace(/_/g, ' ');
                      return (
                        <Tooltip key={`${entry.row_id}-${entry.column_id}-${entry.action_id}-${entryIdx}`}>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-2 rounded-md border border-gray-100 dark:border-gray-800 px-2 py-1.5 text-sm">
                              {entry.status === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />}
                              {entry.status === 'success' && <Check className="h-3.5 w-3.5 text-green-600 shrink-0" />}
                              {entry.status === 'error' && <X className="h-3.5 w-3.5 text-destructive shrink-0" />}
                              <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                              <span className="truncate font-medium capitalize">{label}</span>
                              {entry.companyName && <span className="text-xs text-muted-foreground truncate">{entry.companyName}</span>}
                              {entry.status === 'error' && entry.error && (
                                <span className="text-xs text-destructive truncate max-w-[100px]">{entry.error}</span>
                              )}
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>
                            {label}
                            {entry.companyName && ` · ${entry.companyName}`}
                            {entry.status === 'running' && ' — Running…'}
                            {entry.status === 'error' && entry.error && ` — ${entry.error}`}
                          </TooltipContent>
                        </Tooltip>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Suggestions: collapsible message-like block in the conversation flow */}
              {(suggestions.length > 0 || suggestionsLoading) && (
                <div className="flex justify-start">
                  <div className="max-w-[95%] rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 min-w-0 overflow-hidden">
                    <button
                      onClick={() => setSuggestionsCollapsed((c) => !c)}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {suggestionsLoading
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                        : <FileSearch className="h-3.5 w-3.5 shrink-0" />}
                      <span className="font-medium">
                        {suggestionsLoading
                          ? 'Scanning documents…'
                          : `${suggestions.length} suggestion${suggestions.length !== 1 ? 's' : ''} from documents`}
                      </span>
                      {suggestions.length > 0 && (
                        <span className="ml-auto text-[10px]">{suggestionsCollapsed ? 'Show' : 'Hide'}</span>
                      )}
                    </button>
                    {!suggestionsCollapsed && suggestions.length > 0 && (
                      <div className="px-2.5 pb-1.5 space-y-1 max-h-[220px] overflow-y-auto border-t border-gray-100 dark:border-gray-800">
                        {suggestionsError && (
                          <p className="text-xs text-destructive py-1">{suggestionsError}</p>
                        )}
                        {suggestions.map((s) => renderSuggestionCard(s))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
          </div>
        </div>

        {/* Input bar — Cursor-style: sticky at bottom, minimal send, accepts dropped memo sections */}
        <div
          className={`shrink-0 p-2 border-t border-border/80 bg-background/95 backdrop-blur-sm ${dragOverInput ? 'ring-2 ring-primary/50 bg-primary/5' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverInput(true); }}
          onDragLeave={() => setDragOverInput(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverInput(false);
            const raw = e.dataTransfer.getData('application/dilla-memo-section');
            if (raw) {
              try {
                const section = JSON.parse(raw);
                const content = section.section?.content || section.content || e.dataTransfer.getData('text/plain') || '';
                if (content) {
                  setDroppedContext({ type: section.section?.type || 'paragraph', content });
                }
              } catch {}
            }
          }}
        >
          {/* Dropped context card */}
          {droppedContext && (
            <div className="mb-1.5 mx-0.5 p-2 rounded-lg bg-muted/50 border text-xs flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <span className="text-[10px] font-medium text-muted-foreground uppercase">Context from memo</span>
                <p className="text-foreground line-clamp-2 mt-0.5">{droppedContext.content}</p>
              </div>
              <button onClick={() => setDroppedContext(null)} className="shrink-0 h-4 w-4 text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
          <input
            ref={uploadFileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.xlsx,.xls"
            className="hidden"
            onChange={handleFileSelect}
          />
          <div className="flex items-end gap-1.5 rounded-xl border border-input bg-muted/30 dark:bg-muted/20 px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
            <div className="flex-1 relative min-w-0">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Message... (Enter to send)"
                className="min-h-[36px] max-h-[120px] resize-none pr-9 text-sm border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground"
                disabled={isLoading}
              />
            </div>
            {onUploadDocument && matrixData?.rows?.length && fundId ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 rounded-lg"
                disabled={uploading || isLoading}
                onClick={() => uploadFileInputRef.current?.click()}
                title="Upload documents"
              >
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 rounded-lg"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              title="Send (Enter)"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ArrowUp className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* A4 Document Viewer Popover — Google Docs style */}
      <Sheet open={documentViewerOpen} onOpenChange={setDocumentViewerOpen}>
        <SheetContent side="right" className="w-full sm:max-w-none sm:w-[720px] md:w-[816px] p-0 overflow-hidden">
          <div className="flex flex-col h-full">
            <SheetHeader className="shrink-0 px-6 py-4 border-b bg-gray-50 dark:bg-gray-900/50">
              <div className="flex items-center justify-between">
                <SheetTitle className="text-base">
                  {documentViewerMessage?.docsSections?.[0]?.title || 'Document'}
                </SheetTitle>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-xs gap-1.5"
                    onClick={() => documentViewerMessage && handlePdfExport(documentViewerMessage)}
                    disabled={exportingPdf}
                  >
                    {exportingPdf ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
                    Export PDF
                  </Button>
                </div>
              </div>
            </SheetHeader>

            {/* A4 page body */}
            <div className="flex-1 overflow-y-auto bg-gray-100 dark:bg-gray-950 py-8 px-4">
              <div className="mx-auto bg-white dark:bg-gray-900 shadow-lg rounded-sm max-w-[680px] min-h-[900px] px-12 py-16">
                {documentViewerMessage?.docsSections?.map((section, sIdx) => {
                  const level = section.level ?? 1;
                  const HeadingTag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3';
                  const headingClass = level === 1
                    ? 'text-2xl font-bold mb-4 mt-8 first:mt-0 text-gray-900 dark:text-gray-100 border-b pb-2'
                    : level === 2
                      ? 'text-xl font-semibold mb-3 mt-6 text-gray-800 dark:text-gray-200'
                      : 'text-lg font-medium mb-2 mt-4 text-gray-700 dark:text-gray-300';

                  // Check if a chart should appear after this section
                  const chartPositions = documentViewerMessage.docsChartPositions || [];
                  const docsCharts = documentViewerMessage.docsCharts || documentViewerMessage.charts || [];
                  const chartsAfterSection = chartPositions
                    .map((pos, cIdx) => ({ ...pos, chartIdx: cIdx }))
                    .filter((pos) => pos.afterParagraph === sIdx + 1 && pos.chartIdx < docsCharts.length);

                  return (
                    <React.Fragment key={sIdx}>
                      {section.title && (
                        <HeadingTag className={headingClass}>
                          {section.title}
                        </HeadingTag>
                      )}
                      {section.content && (
                        <div className="prose prose-sm dark:prose-invert max-w-none mb-4 text-gray-700 dark:text-gray-300 leading-relaxed">
                          <ReactMarkdown>{section.content}</ReactMarkdown>
                        </div>
                      )}
                      {/* Inline charts positioned after this section */}
                      {chartsAfterSection.map(({ chartIdx }) => {
                        const chart = docsCharts[chartIdx];
                        if (!chart) return null;
                        const hasData = chart.data && (Array.isArray(chart.data) ? chart.data.length > 0 : Object.keys(chart.data).length > 0);
                        return hasData ? (
                          <div key={`chart-${chartIdx}`} className="my-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/30">
                            <TableauLevelCharts
                              type={chart.type as any}
                              data={chart.data}
                              title={chart.title}
                              interactive={true}
                              height={320}
                              width="100%"
                            />
                          </div>
                        ) : (
                          <div key={`chart-${chartIdx}`} className="my-4 flex items-center justify-center h-20 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-sm text-muted-foreground">
                            {chart.title ? `${chart.title} — data unavailable` : 'Chart data unavailable'}
                          </div>
                        );
                      })}
                    </React.Fragment>
                  );
                })}

                {/* Render remaining charts that weren't positioned */}
                {(() => {
                  const docsCharts = documentViewerMessage?.docsCharts || documentViewerMessage?.charts || [];
                  const positions = documentViewerMessage?.docsChartPositions || [];
                  const positionedIndices = new Set(positions.map((_, i) => i));
                  const unpositioned = docsCharts.filter((_, i) => !positionedIndices.has(i));
                  if (unpositioned.length === 0) return null;
                  return (
                    <div className="mt-8 space-y-4">
                      <h2 className="text-xl font-semibold mb-3 text-gray-800 dark:text-gray-200">Charts</h2>
                      {unpositioned.map((chart, idx) => {
                        const hasData = chart.data && (Array.isArray(chart.data) ? chart.data.length > 0 : Object.keys(chart.data).length > 0);
                        return hasData ? (
                          <div key={`extra-chart-${idx}`} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/30">
                            <TableauLevelCharts
                              type={chart.type as any}
                              data={chart.data}
                              title={chart.title}
                              interactive={true}
                              height={320}
                              width="100%"
                            />
                          </div>
                        ) : (
                          <div key={`extra-chart-${idx}`} className="flex items-center justify-center h-20 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-sm text-muted-foreground">
                            {chart.title ? `${chart.title} — data unavailable` : 'Chart data unavailable'}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}

                {/* Company analysis cards in document */}
                {documentViewerMessage?.companies && documentViewerMessage.companies.length > 0 && (
                  <div className="mt-8 space-y-4">
                    <h2 className="text-xl font-semibold mb-3 text-gray-800 dark:text-gray-200 border-b pb-2">Company Overview</h2>
                    {documentViewerMessage.companies.map((company: CompanyAnalysisData, cidx: number) => (
                      <CompanyAnalysisCard key={cidx} data={company} />
                    ))}
                  </div>
                )}

                {/* Cap tables in document — with ownership bars */}
                {documentViewerMessage?.capTables && documentViewerMessage.capTables.length > 0 && (
                  <div className="mt-8 space-y-6">
                    <h2 className="text-xl font-semibold mb-3 text-gray-800 dark:text-gray-200 border-b pb-2">Ownership Structure</h2>
                    {documentViewerMessage.capTables.map((item: any, idx: number) => (
                      <div key={idx} className="space-y-3">
                        <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300">{item.company}</h3>
                        {item.capTable?.investors && item.capTable.investors.length > 0 && (
                          <table className="w-full text-sm border-collapse">
                            <thead>
                              <tr className="border-b-2 border-gray-200 dark:border-gray-600">
                                <th className="text-left py-2 pr-4 font-semibold text-gray-600 dark:text-gray-400">Investor</th>
                                <th className="text-left py-2 pr-4 font-semibold text-gray-600 dark:text-gray-400">Round</th>
                                <th className="text-right py-2 pr-4 font-semibold text-gray-600 dark:text-gray-400">Ownership</th>
                                <th className="py-2 w-32"></th>
                              </tr>
                            </thead>
                            <tbody>
                              {item.capTable.investors.map((inv: any, invIdx: number) => (
                                <tr key={invIdx} className={`border-b border-gray-100 dark:border-gray-700 ${invIdx % 2 === 0 ? '' : 'bg-gray-50 dark:bg-gray-800/30'}`}>
                                  <td className="py-1.5 pr-4">{inv.name}</td>
                                  <td className="py-1.5 pr-4 text-muted-foreground">{inv.round || '--'}</td>
                                  <td className="py-1.5 pr-4 text-right font-mono tabular-nums">{(inv.ownership * 100).toFixed(2)}%</td>
                                  <td className="py-1.5">
                                    <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                                      <div className="h-full rounded-full bg-blue-500 dark:bg-blue-400" style={{ width: `${Math.min(inv.ownership * 100, 100)}%` }} />
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                        {item.capTable?.liquidation_stack && item.capTable.liquidation_stack.length > 0 && (
                          <div className="mt-3">
                            <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Liquidation Preferences</h4>
                            <table className="w-full text-sm border-collapse">
                              <thead>
                                <tr className="border-b border-gray-200 dark:border-gray-600">
                                  <th className="text-left py-1 pr-4 text-xs font-medium text-gray-500">#</th>
                                  <th className="text-left py-1 pr-4 text-xs font-medium text-gray-500">Investor</th>
                                  <th className="text-right py-1 pr-4 text-xs font-medium text-gray-500">Amount</th>
                                  <th className="text-right py-1 text-xs font-medium text-gray-500">Multiple</th>
                                </tr>
                              </thead>
                              <tbody>
                                {item.capTable.liquidation_stack.map((pref: any, prefIdx: number) => (
                                  <tr key={prefIdx} className="border-b border-gray-50 dark:border-gray-800">
                                    <td className="py-1 pr-4 text-muted-foreground">{prefIdx + 1}</td>
                                    <td className="py-1 pr-4">{pref.investor}</td>
                                    <td className="py-1 pr-4 text-right font-mono">${(pref.amount / 1e6).toFixed(1)}M</td>
                                    <td className="py-1 text-right font-mono">{pref.multiple}x</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Citations at bottom of document */}
                {documentViewerMessage?.citations && documentViewerMessage.citations.length > 0 && (
                  <div className="mt-12 pt-6 border-t border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-3 uppercase tracking-wider">Sources</h3>
                    <div className="space-y-1">
                      {documentViewerMessage.citations.map((citation, idx) => (
                        <a
                          key={idx}
                          href={citation.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-xs text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          [{idx + 1}] {citation.source || citation.title || citation.url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </TooltipProvider>
  );
}