'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
// import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Textarea } from '@/components/ui/textarea';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { ChipTray } from '@/components/chips/ChipTray';
import { ChipInput, type ChipInputRef } from '@/components/chips/ChipInput';
import type { ChipDef, InputSegment } from '@/lib/chips/types';
import { compose, buildPrompt } from '@/lib/chips/compose';
import {
  ArrowUp,
  ArrowRight,
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
  ListTodo,
  BookOpen,
  FileSpreadsheet,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
import { getSupabaseBrowser } from '@/lib/supabase/browser';
import { SkeletonChart } from '@/components/ui/skeleton';
import type { MatrixData } from '@/components/matrix/UnifiedMatrix';
import { contextManager } from '@/lib/agent-context-manager';


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
  docsSections?: Array<{ type?: string; title?: string; content?: string; level?: number; table?: { headers?: string[]; rows?: any[][]; caption?: string }; chart?: { type: string; title?: string; data: any }; items?: string[] }>;
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
  /** Clarification request from agent — options for user to pick */
  clarification?: { question: string; options: string[]; reasoning?: string };
  /** Checkpoint — agent produced outputs and suggests next steps */
  checkpoint?: { summary: string; next_steps: string[]; reasoning?: string };
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

import { SuggestionCard, type DocumentSuggestion } from '@/components/matrix/DocumentSuggestions';

interface AgentChatProps {
  sessionId?: string;
  onMessageSent?: (message: string) => void;
  matrixData?: MatrixData | null;
  fundId?: string;
  mode?: 'portfolio' | 'custom' | 'lp' | 'pnl' | 'legal' | 'workflow';
  onCellEdit?: (rowId: string, columnId: string, value: unknown, options?: { data_source?: string; metadata?: Record<string, unknown> }) => Promise<void>;
  onRunService?: (actionId: string, rowId: string, columnId: string) => Promise<void>;
  onToolCallLog?: (entry: Omit<{ action_id: string; row_id: string; column_id: string; status: 'running' | 'success' | 'error'; error?: string; companyName?: string; explanation?: string }, 'id' | 'at'>) => void;
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
  toolCallEntries?: Array<{ action_id: string; row_id: string; column_id: string; status: 'running' | 'success' | 'error'; error?: string; companyName?: string; explanation?: string }>;
  /** Optional: highlight target cell in grid when suggestion is hovered/focused */
  onHighlightCell?: (rowId: string, columnId: string) => void;
  /** Callback when agent response contains memo_updates (sections to append/replace) */
  onMemoUpdates?: (updates: { action: string; sections?: Array<{ type: string; content?: string; chart?: unknown; chartId?: number; items?: string[]; table?: unknown }>; chartId?: number; chart?: unknown }) => void;
  /** Current memo sections for sending as context */
  memoSections?: Array<{ type: string; content?: string }>;
  /** Emit rich analysis content to the bottom panel instead of crammed into sidebar */
  onAnalysisReady?: (analysis: {
    sections: Array<{ title?: string; content?: string; level?: number }>;
    charts: Array<{ type: string; title?: string; data: any }>;
    companies?: any[];
    capTables?: any[];
  }) => void;
  /** Scenario fork tree: agent created/updated a branch */
  onScenarioBranchCreated?: (result: any) => void;
  /** Scenario fork tree: agent returned comparison charts */
  onScenarioComparisonReady?: (result: any) => void;
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
  'pnl.upload_csv': FileSpreadsheet,
  'pnl.clean_match': FileSpreadsheet,
  'document.extract': FileTextIcon,
};

/** Build compressed matrix context for backend (< 5KB) with optional gridSnapshot for cell values */
function buildMatrixContext(matrixData: MatrixData | null | undefined, fundId?: string, gridMode?: string): MatrixContext | undefined {
  if (!matrixData?.rows?.length) return undefined;
  const gridSnapshot = buildGridSnapshot(matrixData, 5000, gridMode || 'portfolio');
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
  onScenarioBranchCreated,
  onScenarioComparisonReady,
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
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [suggestionsCollapsed, setSuggestionsCollapsed] = useState(false);
  const [documentViewerOpen, setDocumentViewerOpen] = useState(false);
  const [documentViewerMessage, setDocumentViewerMessage] = useState<Message | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [pendingApprovedPlan, setPendingApprovedPlan] = useState(false);
  const [streamingSteps, setStreamingSteps] = useState<Array<{ id: string; label: string; status: 'pending' | 'running' | 'done' | 'failed'; detail?: string }>>([]);
  const [streamingStage, setStreamingStage] = useState<string>('');
  const approvedPlanStepsRef = useRef<any[]>([]);
  const workingMemoryRef = useRef<Array<{ tool: string; summary: string }>>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const autoBriefedRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const chipInputRef = useRef<ChipInputRef>(null);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);
  const [dragOverInput, setDragOverInput] = useState(false);
  const [chipTrayOpen, setChipTrayOpen] = useState(true);
  const [planModeOn, setPlanModeOn] = useState(false);
  const [memoContextOn, setMemoContextOn] = useState(() => {
    if (typeof window === 'undefined') return false;
    try { return JSON.parse(localStorage.getItem('dilla_memo_artifacts') || '[]').length > 0; } catch { return false; }
  });
  const [memoArtifacts, setMemoArtifacts] = useState<any[]>(() => {
    if (typeof window === 'undefined') return [];
    try { return JSON.parse(localStorage.getItem('dilla_memo_artifacts') || '[]'); } catch { return []; }
  });

  // Persist artifacts to localStorage whenever they change
  useEffect(() => {
    try { localStorage.setItem('dilla_memo_artifacts', JSON.stringify(memoArtifacts)); } catch {}
  }, [memoArtifacts]);

  // Sync messages to active tab
  useEffect(() => {
    setTabs(prev => prev.map(t => t.id === activeTabId ? { ...t, messages } : t));
  }, [messages, activeTabId]);

  // Scheduled task results: subscribe to agent_tasks via Supabase Realtime.
  // When the worker completes a task (last_run_status flips to success/error),
  // inject the result as an assistant message — same UX as the auto-brief.
  useEffect(() => {
    if (!fundId) return;

    const sb = getSupabaseBrowser();
    const channel = sb
      .channel(`agent_tasks:${fundId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'agent_tasks',
          filter: `fund_id=eq.${fundId}`,
        },
        (payload: any) => {
          const task = payload.new;
          if (!task.notify_chat) return;
          if (task.last_run_status !== 'success') return;
          if (!task.last_run_result?.text) return;

          setMessages(prev => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant' as const,
              content: `**Scheduled: ${task.label}**\n\n${task.last_run_result.text}`,
              timestamp: new Date(task.last_run_at),
            },
          ]);
        }
      )
      .subscribe();

    return () => { sb.removeChannel(channel); };
  }, [fundId]);

  // Auto-brief: agent opens the conversation proactively on first load
  useEffect(() => {
    // Only run once per session, only when there are no messages, and only in data modes
    if (autoBriefedRef.current) return;
    if (!['pnl', 'portfolio', 'lp'].includes(mode || '')) return;
    if (!fundId) return;

    // Prevent re-running across re-renders within the same browser session
    const sessionKey = `dilla-auto-briefed-${fundId}-${mode}`;
    if (sessionStorage.getItem(sessionKey)) return;

    autoBriefedRef.current = true;
    sessionStorage.setItem(sessionKey, '1');

    const autoBriefPrompts: Record<string, string> = {
      pnl: "Open the session with a proactive CFO brief. Pull the company's actuals, check burn rate, runway, revenue trajectory, and gross margin. Flag 2-3 specific anomalies or risks you see in the data. Be direct and specific — no generic commentary.",
      portfolio: "Open the session with a portfolio health brief. Check company health scores, flag anything that needs attention, surface key fund metrics. Give me 2-3 specific things I should know right now.",
      lp: "Open the session with an LP brief. Summarise fund performance, DPI, TVPI, and any notable portfolio developments. Flag 2-3 things worth highlighting to LPs.",
    };

    const prompt = autoBriefPrompts[mode || 'portfolio'];
    const companyId = mode === 'pnl' ? matrixData?.rows?.find((r: any) => r.companyId)?.companyId : undefined;

    const placeholderId = crypto.randomUUID();
    setMessages([{
      id: placeholderId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      processing: true,
    }]);
    setIsLoading(true);

    const now = new Date();
    const matrixContext = matrixData && (matrixData.rows?.length > 0 || matrixData.columns?.length > 0)
      ? buildMatrixContext(matrixData, fundId, mode)
      : undefined;

    const agentEndpoint = mode === 'pnl' ? '/api/agent/cfo-brain' : '/api/agent/unified-brain';

    fetch(agentEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        output_format: 'reply',
        sessionId: currentSessionId,
        context: {
          messageHistory: [],
          gridMode: mode || 'portfolio',
          company_id: companyId,
          fundId,
          matrixContext,
          datetime: {
            iso: now.toISOString(),
            date: now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
            time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            quarter: `Q${Math.ceil((now.getMonth() + 1) / 3)} ${now.getFullYear()}`,
          },
        },
        agent_context: {
          recent_analyses: [],
          fund_id: fundId || null,
          working_memory: [],
          current_datetime: now.toISOString(),
          is_auto_brief: true,
        },
        stream: true,
      }),
    }).then(async (res) => {
      if (!res.ok) { setIsLoading(false); setMessages([]); return; }

      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('ndjson') && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult: any = null;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const event = JSON.parse(line);
              if (event.type === 'progress' && event.stage) setStreamingStage(event.stage);
              if (event.type === 'complete') finalResult = event;
            } catch { /* ignore */ }
          }
        }
        if (finalResult) {
          const norm = finalResult.data ?? finalResult;
          setMessages([{
            id: placeholderId,
            role: 'assistant',
            content: norm.response || norm.content || '',
            timestamp: new Date(),
            processing: false,
            agentSuggestions: norm.suggestions,
            todoItems: (norm.todos ?? norm.todo_items ?? []).map((t: any, i: number) => ({
              id: `todo-${Date.now()}-${i}`,
              title: t.title || '',
              description: t.description,
              priority: t.priority,
              company: t.company,
              due: t.due,
              done: false,
            })),
          }]);
        } else {
          setMessages([]);
        }
      } else {
        const data = await res.json();
        const norm = data.data ?? data;
        setMessages([{
          id: placeholderId,
          role: 'assistant',
          content: norm.response || norm.content || '',
          timestamp: new Date(),
          processing: false,
        }]);
      }
    }).catch(() => {
      setMessages([]);
    }).finally(() => {
      setIsLoading(false);
      setStreamingStage('');
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fundId, mode]);

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

  // Only auto-scroll on new messages, not on tool call status updates
  const prevMessageCount = useRef(messages.length);
  useEffect(() => {
    if (messages.length > prevMessageCount.current) {
      scrollToBottom();
    }
    prevMessageCount.current = messages.length;
  }, [messages]);
  // Scroll once when suggestions first appear
  useEffect(() => {
    if (suggestions.length > 0) scrollToBottom();
  }, [suggestions.length > 0]);

  /** Collapse the multiple possible response shapes into one canonical object. */
  const normalizeResponse = (data: any) => {
    const result = data.result || data;
    return {
      result,
      planSteps: result.plan_steps ?? result.steps ?? data.plan_steps ?? data.steps,
      memoUpdates: result.memo_updates ?? data.memo_updates,
      format: result.format ?? data.format ?? 'analysis',
      companies: result.companies || data.companies || [],
      charts: result.charts || result.chart_data || data.charts || data.chart_data || [],
      citations: result.citations || data.citations || [],
      slides: result.slides ?? result.deck?.slides,
      suggestions: result.suggestions ?? data.suggestions,
      explanation: result.explanation ?? data.explanation,
      awaitingApproval: result.awaiting_approval ?? data.awaiting_approval ?? false,
      warnings: result.warnings ?? data.warnings ?? [],
      gridCommands: data.result?.grid_commands ?? data.grid_commands ?? [],
      gridSuggestions: result.grid_suggestions ?? data.grid_suggestions ?? [],
      memoArtifacts: result.memo_artifacts ?? data.memo_artifacts ?? null,
      memoType: result.memo_type ?? data.memo_type ?? null,
      isResumable: result.is_resumable ?? data.is_resumable ?? false,
      todos: result.todos ?? result.todo_items ?? data.todos ?? [],
      pnlRefresh: result.pnl_refresh ?? data.pnl_refresh ?? false,
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
    // Support both chip input (contentEditable) and plain textarea
    const chipSegments = chipInputRef.current?.getSegments() ?? [];
    const hasChips = chipSegments.some(s => s.type === 'chip');
    const hasChipContent = chipInputRef.current?.hasContent() ?? false;
    const hasPlainContent = input.trim().length > 0;

    const hasPendingFiles = pendingFiles.length > 0;
    if (!(hasChipContent || hasPlainContent || hasPendingFiles) || isLoading) return;

    // Build the prompt: if chips are present, compose a workflow prompt
    let fullContent: string;
    let chipWorkflow: ReturnType<typeof compose> | undefined;

    if (hasChips) {
      chipWorkflow = compose(chipSegments);
      fullContent = buildPrompt(chipWorkflow);
      chipInputRef.current?.clear();
    } else {
      fullContent = input;
    }

    // Capture staged files and clear them from state
    const filesToUpload = [...pendingFiles];
    setPendingFiles([]);

    // If files are attached but no text, generate a default prompt
    if (filesToUpload.length > 0 && !fullContent.trim()) {
      fullContent = `Analyze the uploaded file${filesToUpload.length > 1 ? 's' : ''}: ${filesToUpload.map(f => f.name).join(', ')}`;
    }

    // Show file names in the user message
    const fileLabel = filesToUpload.length > 0
      ? `[${filesToUpload.map(f => f.name).join(', ')}]\n`
      : '';

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: fileLabel + fullContent,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    if (hasChips) chipInputRef.current?.clear();
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

      // --- Upload staged files first (if any) ---
      let uploadedDocIds: string[] = [];
      let uploadedFileNames: string[] = [];
      if (filesToUpload.length > 0 && onUploadDocument) {
        setUploading(true);
        try {
          let companyId: string | undefined;
          const rowsWithCompany = matrixData?.rows.filter((r) => r.companyId) ?? [];
          if (rowsWithCompany.length >= 1) companyId = rowsWithCompany[0].companyId;

          // Upload via the same batch endpoint
          const formData = new FormData();
          for (const file of filesToUpload) {
            formData.append('file', file);
            uploadedFileNames.push(file.name);
          }
          if (companyId) formData.append('company_id', companyId);
          if (fundId) formData.append('fund_id', fundId);
          formData.append('mode', mode);

          const uploadRes = await fetch('/api/documents/batch', { method: 'POST', body: formData });
          if (uploadRes.ok) {
            const uploadData = await uploadRes.json();
            uploadedDocIds = uploadData.documentIds || [];
          }
        } catch (uploadErr) {
          console.error('File upload failed:', uploadErr);
        } finally {
          setUploading(false);
        }
      }

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
        ? buildMatrixContext(matrixData, fundId, mode)
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
        prompt: fullContent,
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
          // Grid mode: tells backend what the user is looking at (portfolio, pnl, lp, custom)
          gridMode: mode || 'portfolio',
          // Pass company_id for PNL mode — extracted from matrix row metadata
          company_id: mode === 'pnl' && matrixData?.rows?.find((r: any) => r.companyId)?.companyId || undefined,
          fundId,
          // Pass plan steps back so backend can execute the approved plan
          plan_steps: planStepsToSend.length > 0 ? planStepsToSend : undefined,
          // Plan mode toggle: when on, backend generates execution plan before acting
          plan_mode: planModeOn || undefined,
          // Memo artifacts as optional context (user-toggled, not auto-injected)
          memo_artifacts: memoContextOn && memoArtifacts.length > 0 ? memoArtifacts : undefined,
          // Datetime context for time-aware analysis
          datetime: {
            iso: now.toISOString(),
            date: now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
            time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            quarter: `Q${Math.ceil((now.getMonth() + 1) / 3)} ${now.getFullYear()}`,
          },
          // Uploaded documents attached with this message
          ...(uploadedDocIds.length > 0 ? {
            uploaded_document_ids: uploadedDocIds,
            uploaded_file_names: uploadedFileNames,
          } : {}),
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
        // Chip workflow: structured tool hints from inline chips
        ...(chipWorkflow && chipWorkflow.steps.length > 0 ? {
          chip_workflow: {
            steps: chipWorkflow.steps.map(s => ({
              tool: s.chip.def.tool,
              params: s.inputs,
              chip_id: s.chip.def.id,
              depends_on: s.dependsOn,
              kind: s.chip.def.kind ?? 'tool',
              loop_over: s.chip.def.loopOver,
              condition_metric: s.chip.def.conditionMetric,
              condition_op: s.chip.def.conditionOp,
              assumption_keys: s.chip.def.assumptionKeys,
              bridge_tools: s.chip.def.bridgeTools,
              event_category: s.chip.def.eventCategory,
              prior_keys: s.chip.def.priorKeys,
            })),
            nl_context: chipWorkflow.nlContext,
          },
        } : {}),
      };

      // Abort any in-flight request before starting a new one
      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Route to the right agent brain by mode
      const agentEndpoint = mode === 'pnl'
        ? '/api/agent/cfo-brain'
        : mode === 'legal'
        ? '/api/agent/legal-brain'
        : '/api/agent/unified-brain';

      const res = await fetch(agentEndpoint, {
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
              if (event.type === 'progress') {
                // Update streaming stage indicator
                if (event.stage) setStreamingStage(event.stage);
                if (event.plan_steps) {
                  const steps = event.plan_steps.map((s: any, i: number) => ({
                    id: s.id ?? `step-${i}`,
                    label: s.label ?? s.description ?? s.action ?? `Step ${i + 1}`,
                    status: (s.status ?? 'running') as 'pending' | 'running' | 'done' | 'failed',
                    detail: s.detail,
                  }));
                  setStreamingSteps(steps);
                  if (onPlanStepsUpdate) onPlanStepsUpdate(steps);
                } else if (event.message) {
                  // Progress event without plan_steps — show as a single step
                  setStreamingSteps(prev => {
                    const existing = prev.find(s => s.label === event.message);
                    if (existing) return prev;
                    return [...prev, { id: `prog-${prev.length}`, label: event.message, status: 'running' as const }];
                  });
                }
              } else if (event.type === 'token') {
                // Stream text tokens into the placeholder message in real-time
                const tokenContent = event.content || '';
                if (tokenContent) {
                  setMessages(prev => prev.map(m =>
                    m.id === placeholderId
                      ? { ...m, content: m.content + tokenContent, processing: true }
                      : m
                  ));
                }
              } else if (event.type === 'tool_call') {
                // Show tool call as a running step
                setStreamingStage('executing');
                setStreamingSteps(prev => {
                  const updated = prev.map(s => s.id.startsWith('think-') && s.status === 'running' ? { ...s, status: 'done' as const } : s);
                  return [...updated, {
                    id: `tool-${event.tool}-${event.tool_call_id || Date.now()}`,
                    label: event.tool || 'tool',
                    status: 'running' as const,
                  }];
                });
              } else if (event.type === 'tool_result') {
                // Mark tool call step as done
                setStreamingSteps(prev => prev.map(s =>
                  s.id === `tool-${event.tool}-${event.tool_call_id}`
                    ? { ...s, status: (event.result?.error ? 'failed' : 'done') as 'done' | 'failed' }
                    : s
                ));
              } else if (event.type === 'classification') {
                // Show intent classification immediately
                setStreamingStage(event.response_mode === 'reply' ? 'replying' : event.response_mode === 'action' ? 'acting' : 'analyzing');
                setStreamingSteps(prev => [
                  ...prev,
                  { id: 'classify', label: `${event.intent} (${event.response_mode})`, status: 'done' as const, detail: `confidence: ${Math.round((event.confidence ?? 1) * 100)}%` },
                ]);
              } else if (event.type === 'thinking') {
                // Agent reasoning — show as a running step
                const thinkLabel = event.reasoning?.slice(0, 80) || 'Reasoning...';
                setStreamingSteps(prev => {
                  // Mark previous thinking steps as done
                  const updated = prev.map(s => s.id.startsWith('think-') && s.status === 'running' ? { ...s, status: 'done' as const } : s);
                  return [...updated, { id: `think-${event.iteration}`, label: thinkLabel, status: 'running' as const }];
                });
              } else if (event.type === 'tool_start') {
                // Tool starting — add as running step
                setStreamingStage('executing');
                setStreamingSteps(prev => {
                  // Mark previous thinking as done
                  const updated = prev.map(s => s.id.startsWith('think-') && s.status === 'running' ? { ...s, status: 'done' as const } : s);
                  return [...updated, {
                    id: `tool-${event.tool}-${event.iteration}`,
                    label: event.tool,
                    status: 'running' as const,
                    detail: event.cost_tier !== 'free' ? event.cost_tier : undefined,
                  }];
                });
              } else if (event.type === 'tool_end') {
                // Tool completed — mark step done/failed
                setStreamingSteps(prev => prev.map(s =>
                  s.id === `tool-${event.tool}-${event.iteration}`
                    ? { ...s, status: event.success ? 'done' as const : 'failed' as const, detail: event.duration_ms ? `${event.duration_ms}ms` : s.detail }
                    : s
                ));
              } else if (event.type === 'status') {
                // Generic status update (e.g., synthesizing)
                if (event.stage) setStreamingStage(event.stage);
                if (event.message) {
                  setStreamingSteps(prev => [
                    ...prev,
                    { id: `status-${Date.now()}`, label: event.message, status: 'running' as const },
                  ]);
                }
              } else if (event.type === 'memo_section' && event.section && onMemoUpdates) {
                // Stream memo sections to MemoEditor in real-time
                onMemoUpdates({ action: 'append', sections: [event.section] });
              } else if (event.type === 'chart_data' && event.chart) {
                // Accumulate streamed charts for final message
                if (!data) data = { success: true, result: {} };
                if (!data.result) data.result = {};
                if (!data.result.charts) data.result.charts = [];
                data.result.charts.push(event.chart);
                // Also stream charts to memo in real-time (with chartId for live updates)
                if (onMemoUpdates) {
                  onMemoUpdates({ action: 'append', sections: [{ type: 'chart', chart: event.chart, chartId: event.chart.id }] });
                }
              } else if (event.type === 'chart_rebuild' && event.chart) {
                // Live chart update — replace existing chart in accumulated data and memo
                const rebuildId = event.chart_id ?? event.chart?.id;
                if (data?.result?.charts) {
                  const idx = data.result.charts.findIndex((c: any) => c.id === rebuildId);
                  if (idx >= 0) data.result.charts[idx] = event.chart;
                }
                if (onMemoUpdates) {
                  onMemoUpdates({ action: 'update_chart', chartId: rebuildId, chart: event.chart });
                }
              } else if (event.type === 'clarification_needed') {
                // Agent wants to ask the user a question before proceeding
                const clarifyMsg: Message = {
                  id: `clarify-${Date.now()}`,
                  role: 'assistant',
                  content: event.question || 'Could you clarify?',
                  timestamp: new Date(),
                  clarification: {
                    question: event.question,
                    options: event.options || [],
                    reasoning: event.reasoning,
                  },
                };
                setMessages(prev => [...prev, clarifyMsg]);
                setIsLoading(false);
                setStreamingStage('');
                setStreamingSteps([]);
                return; // Exit stream processing — wait for user to pick an option
              } else if (event.type === 'checkpoint') {
                // Agent produced outputs and suggests next steps
                const checkpointMsg: Message = {
                  id: `checkpoint-${Date.now()}`,
                  role: 'assistant',
                  content: event.summary || 'Results ready for review.',
                  timestamp: new Date(),
                  checkpoint: {
                    summary: event.summary,
                    next_steps: event.next_steps || [],
                    reasoning: event.reasoning,
                  },
                };
                setMessages(prev => [...prev, checkpointMsg]);
                setIsLoading(false);
                setStreamingStage('');
                setStreamingSteps([]);
                return; // Pause — user can click a next step or type their own follow-up
              } else if (event.type === 'doc_processing_progress') {
                // Multi-doc processing progress — update streaming steps
                const pctLabel = event.total > 0
                  ? `Processing documents: ${event.completed}/${event.total}`
                  : 'Processing documents...';
                const docDetail = event.current_doc
                  ? `${event.current_doc} (${event.provider || ''})`
                  : undefined;
                setStreamingStage('processing_docs');
                setStreamingSteps(prev => {
                  const existing = prev.find(s => s.id === 'doc-batch-progress');
                  if (existing) {
                    return prev.map(s =>
                      s.id === 'doc-batch-progress'
                        ? { ...s, label: pctLabel, detail: docDetail, status: (event.completed >= event.total ? 'done' : 'running') as 'done' | 'running' }
                        : s
                    );
                  }
                  return [...prev, {
                    id: 'doc-batch-progress',
                    label: pctLabel,
                    status: 'running' as const,
                    detail: docDetail,
                  }];
                });
              } else if (event.type === 'doc_extracted') {
                // Single document extracted successfully
                setStreamingSteps(prev => [
                  ...prev,
                  {
                    id: `doc-ok-${event.doc_id}`,
                    label: `Extracted: ${event.file_name || event.doc_id}`,
                    status: 'done' as const,
                    detail: event.provider ? `via ${event.provider}` : undefined,
                  },
                ]);
              } else if (event.type === 'doc_error') {
                // Single document extraction failed
                setStreamingSteps(prev => [
                  ...prev,
                  {
                    id: `doc-err-${event.doc_id}`,
                    label: `Failed: ${event.file_name || event.doc_id}`,
                    status: 'failed' as const,
                    detail: event.error,
                  },
                ]);
              } else if (event.type === 'doc_search_result') {
                // Targeted search result for one document
                const answerPreview = event.answer != null
                  ? String(event.answer).slice(0, 80)
                  : 'No answer';
                setStreamingSteps(prev => [
                  ...prev,
                  {
                    id: `doc-search-${event.doc_id}`,
                    label: `${event.file_name || event.doc_id}: ${answerPreview}`,
                    status: 'done' as const,
                    detail: event.reasoning?.slice(0, 120),
                  },
                ]);
              } else if (event.type === 'batch_complete' || event.type === 'search_complete') {
                // Mark the batch progress step as done
                setStreamingSteps(prev => prev.map(s =>
                  s.id === 'doc-batch-progress' ? { ...s, status: 'done' as const } : s
                ));
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

      // Detect scenario branch operations from agent response
      if (result.branch && onScenarioBranchCreated) {
        onScenarioBranchCreated(result);
        // Refresh the grid so scenarios view picks up the new branch
        window.dispatchEvent(new CustomEvent('refreshPnl'));
      }
      if (onScenarioComparisonReady && norm.charts?.length) {
        // Route scenario/forecast charts to grid ChartViewport —
        // works for comparison results, PNL scenario forecasts,
        // and streamed chart_data from tool results
        onScenarioComparisonReady({ charts: norm.charts, ...result });
      }

      // Forward grid_suggestions from FPA tools → suggestions accept/reject flow
      // Deduplicate by (rowId, columnId) — keeps the last value when multiple tools
      // (e.g. fpa_forecast + fpa_cash_flow) suggest edits for the same cell.
      // SKIP any cells already handled by commandsToRun (grid_commands or intent)
      // to prevent the same action firing twice from the same response.
      if (norm.gridSuggestions?.length && onGridCommandsFromBackend) {
        // Build set of cells already executed by commandsToRun
        const alreadyHandled = new Set<string>();
        for (const cmd of commandsToRun) {
          if (cmd.rowId && cmd.columnId) alreadyHandled.add(`${cmd.rowId}:${cmd.columnId}`);
        }
        const seen = new Map<string, any>();
        for (const s of norm.gridSuggestions) {
          const key = `${s.rowId}:${s.columnId}`;
          if (!alreadyHandled.has(key)) {
            seen.set(key, s);
          }
        }
        if (seen.size > 0) {
          const suggestionCmds = Array.from(seen.values()).map((s: any) => ({
            action: 'edit' as const,
            rowId: s.rowId,
            columnId: s.columnId,
            value: s.value,
            source_service: s.source_service || 'fpa_forecast',
            reasoning: s.reasoning,
          }));
          onGridCommandsFromBackend(suggestionCmds).catch((err: any) =>
            console.error('[AgentChat] grid_suggestions error:', err)
          );
        }
      }

      // P&L grid refresh: when FPA write tools ran, signal the control panel to re-fetch
      if (norm.pnlRefresh) {
        window.dispatchEvent(new CustomEvent('refreshPnl'));
      }

      // Store resumable memo artifacts (plan memos) for cross-session context
      if (norm.memoArtifacts?.length) {
        setMemoArtifacts(prev => [...prev, ...norm.memoArtifacts].slice(-20));
        setMemoContextOn(true);
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

      // Docs sections + charts from backend only — no frontend enrichment/reprocessing
      let docsSections: Array<{ type?: string; title?: string; content?: string; level?: number; table?: any; chart?: any; items?: string[] }> | undefined;
      let docsCharts: Array<{ type: string; title?: string; data: any }> | undefined;
      let docsChartPositions: Array<{ afterParagraph: number; inline: boolean }> | undefined;

      const rawSections = result.sections ?? result.memo?.sections ?? result.docs?.sections;
      if (Array.isArray(rawSections) && rawSections.length > 0) {
        docsSections = rawSections;
      }

      // Extract the agent synthesis early so it is available for fallback parsing
      const synthesis = result.content || result.summary || result.synthesis || '';

      // --- Content generation ---
      // The agent decides what goes where. Chat shows the agent's full reply text.
      // Surfaces (memo, grid, charts) are populated ONLY by explicit backend tool calls
      // (write_to_memo, generate_chart, suggest_grid_edit, etc).
      // The frontend never auto-generates surface content from chat text.
      let content = '';
      let capTables: any[] = [];
      let citations: any[] = [];

      const companies = norm.companies;
      const allCitations = norm.citations;

      // Extract cap tables from companies (used by viewer)
      if (companies && companies.length > 0) {
        companies.forEach((company: any) => {
          const companyName = company.company || company.name || '';
          if (company.cap_table) {
            capTables.push({ company: companyName, capTable: company.cap_table });
          }
        });
      }

      // Citations for structured rendering
      if (allCitations && allCitations.length > 0) {
        citations = allCitations;
      }

      // Chat content = what the agent said. Full text, no truncation.
      content = synthesis || result.response || result.answer || result.message || result.reply || '';

      // Fallback for empty responses
      if (!content) {
        const fallbackFields = [
          result.analysis?.executive_summary,
          typeof (data.analysis || data.synthesis || result.text) === 'string' ? (data.analysis || data.synthesis || result.text) : null,
          result.summary,
          result.analysis_text,
          typeof result.explanation === 'string' ? result.explanation : result.explanation?.reasoning,
          result.portfolio_summary || result.fund_summary,
          result.insight,
        ].filter((v): v is string => typeof v === 'string' && v.trim().length > 10);

        if (fallbackFields.length > 0) {
          content = fallbackFields[0];
        }
      }

      // Deck slides: append a note but keep full chat text
      if (deckSlides?.length && content) {
        content += `\n\n**Deck ready** — ${deckSlides.length} slides generated.`;
      } else if (deckSlides?.length) {
        content = `**Investment deck generated** — ${deckSlides.length} slides. Click to preview.`;
      }

      // Memo updates ONLY from explicit backend tool output — never auto-generated
      if (norm.memoUpdates?.sections?.length && onMemoUpdates) {
        onMemoUpdates(norm.memoUpdates);
      }
      
      const toolsUsed = data.tool_calls?.map((tc: any) => tc.tool) || 
                        data.metadata?.tools_used || 
                        (result.metadata ? result.metadata.entities?.actions || [] : []);
      
      // Charts: route to memo surface (scenario branches are handled separately via grid events).
      const allCharts = [...norm.charts, ...chartCharts];
      const charts: typeof allCharts = []; // Never inline in chat
      if (allCharts.length > 0) {
        if (!docsCharts) docsCharts = [];
        docsCharts.push(...allCharts.map(c => ({ type: c.type, title: c.title, data: c.data })));
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

      // Emit rich analysis to bottom panel when we have docs/chart content from backend
      if (onAnalysisReady && (docsSections?.length || docsCharts?.length)) {
        onAnalysisReady({
          sections: docsSections || [],
          charts: docsCharts || [],
          companies: companies,
          capTables: capTables,
        });
      }

      // Auto-open document viewer when backend sent docs sections or charts
      if (docsSections?.length || docsCharts?.length) {
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
      setStreamingSteps([]);
      setStreamingStage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    e.target.value = '';
    if (!files.length) return;
    // Stage files — they'll be uploaded when the user hits Send
    setPendingFiles(prev => [...prev, ...files]);
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
      // Derive a title: prefer the first heading's content, fall back to title field
      const firstSection = message.docsSections[0] as any;
      const title = firstSection?.title
        || (firstSection?.type?.startsWith?.('heading') ? firstSection.content : null)
        || 'Investment Memo';

      const res = await fetch('/api/memos/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections: message.docsSections,
          charts: message.docsCharts || message.charts || [],
          chartPositions: message.docsChartPositions || [],
          title,
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
      a.download = `${title.replace(/[^a-zA-Z0-9 ]/g, '').replace(/\s+/g, '_').substring(0, 50)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('PDF export failed:', err?.message || err);
      alert(`PDF export failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setExportingPdf(false);
    }
  };

  /** Compact suggestion card — same tiny size, hover popover shows full detail */
  const renderSuggestionCard = (s: DocumentSuggestion) => {
    const row = matrixData?.rows?.find((r) => r.id === s.rowId);
    const col = matrixData?.columns?.find((c) => c.id === s.columnId);
    const companyName = row?.companyName ?? row?.id ?? s.rowId;
    const colName = col?.name ?? s.columnId;
    const currentStr = formatSuggestionValue(s.currentValue, s.columnId);
    const suggestedStr = formatSuggestionValue(s.suggestedValue, s.columnId);
    const hasReasoning = s.reasoning?.trim().length > 0;
    const isLegalClause = typeof s.suggestedValue === 'object' && s.suggestedValue !== null && !Array.isArray(s.suggestedValue);
    const clauseObj = isLegalClause ? s.suggestedValue as Record<string, unknown> : null;
    const sourceLabel = s.sourceDocumentName || (s.sourceService ? s.sourceService.replace(/[._]/g, ' ') : 'Unknown');

    return (
      <HoverCard key={s.id} openDelay={200} closeDelay={100}>
        <HoverCardTrigger asChild>
          <div
            className="flex items-center gap-1.5 rounded border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-2 py-1 min-w-0 text-[11px] cursor-default"
            onMouseEnter={() => onHighlightCell?.(s.rowId, s.columnId)}
            onMouseLeave={() => onHighlightCell?.('', '')}
          >
            <span className="truncate text-foreground font-medium min-w-0">{companyName}</span>
            <span className="text-muted-foreground shrink-0">{colName}:</span>
            {currentStr !== 'N/A' && (
              <>
                <span className="text-muted-foreground line-through shrink-0">{currentStr}</span>
                <ArrowRight className="w-2.5 h-2.5 text-muted-foreground shrink-0" />
              </>
            )}
            <span className="font-semibold text-foreground truncate">
              {isLegalClause ? (clauseObj?.title as string ?? clauseObj?.clauseType as string ?? suggestedStr) : suggestedStr}
            </span>
            <div className="flex items-center gap-0.5 shrink-0 ml-auto">
              <button type="button" onClick={(e) => { e.stopPropagation(); onSuggestionReject?.(s.id); }} className="p-0.5 rounded hover:bg-destructive/20 text-muted-foreground hover:text-destructive" aria-label="Reject">
                <X className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={async (e) => {
                  e.stopPropagation();
                  if (!onSuggestionAccept) return;
                  try { await Promise.resolve(onSuggestionAccept(s.id, { rowId: s.rowId, columnId: s.columnId, suggestedValue: s.suggestedValue, sourceDocumentId: s.sourceDocumentId })); } catch {}
                }}
                className="p-0.5 rounded hover:bg-primary/20 text-muted-foreground hover:text-primary"
                aria-label="Accept"
              >
                <Check className="h-3 w-3" />
              </button>
            </div>
          </div>
        </HoverCardTrigger>
        <HoverCardContent side="left" align="start" className="w-[320px] p-0 text-xs">
          {/* Value change */}
          <div className="px-3 py-2 border-b border-gray-100 dark:border-gray-800">
            <div className="font-medium text-foreground">{companyName} — {colName}</div>
            <div className="flex items-center gap-1.5 mt-1 text-[11px]">
              {currentStr !== 'N/A' && (
                <>
                  <span className="text-muted-foreground line-through">{currentStr}</span>
                  <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
                </>
              )}
              <span className="font-semibold">{isLegalClause ? (clauseObj?.title as string ?? suggestedStr) : suggestedStr}</span>
              {s.confidence != null && (
                <span className="text-[10px] text-muted-foreground ml-auto">{Math.round(s.confidence * 100)}%</span>
              )}
            </div>
          </div>
          {/* Legal clause detail */}
          {isLegalClause && clauseObj && (
            <div className="px-3 py-2 space-y-1.5 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
              {clauseObj.text && (<div><span className="text-muted-foreground text-[10px] uppercase tracking-wide">Clause</span><p className="text-xs leading-relaxed mt-0.5">{String(clauseObj.text)}</p></div>)}
              {clauseObj.party && (<div><span className="text-muted-foreground text-[10px] uppercase tracking-wide">Party</span><p className="text-xs mt-0.5">{String(clauseObj.party)}</p></div>)}
              {clauseObj.clauseType && (<div><span className="text-muted-foreground text-[10px] uppercase tracking-wide">Type</span><p className="text-xs mt-0.5">{String(clauseObj.clauseType)}</p></div>)}
              {clauseObj.flags && (<div><span className="text-muted-foreground text-[10px] uppercase tracking-wide">Flags</span><p className="text-xs mt-0.5">{String(clauseObj.flags)}</p></div>)}
            </div>
          )}
          {/* Source */}
          <div className="px-3 py-1.5 flex items-center gap-1.5 border-b border-gray-100 dark:border-gray-800">
            <FileTextIcon className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[11px] text-muted-foreground">Source:</span>
            <span className="text-[11px] font-medium truncate">{sourceLabel}</span>
          </div>
          {/* Reasoning */}
          {hasReasoning && (
            <div className="px-3 py-2">
              <span className="text-muted-foreground text-[10px] uppercase tracking-wide">Reasoning</span>
              <p className="text-xs text-foreground mt-0.5 leading-relaxed">{s.reasoning}</p>
            </div>
          )}
        </HoverCardContent>
      </HoverCard>
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
                    {mode === 'pnl' ? (
                      <>Forecast revenue, adjust expenses, run scenarios, or ask about margins and runway</>
                    ) : mode === 'legal' ? (
                      <>Upload a contract, review clauses, or ask about terms and obligations</>
                    ) : (
                      <>Run a valuation, model scenarios, or type <kbd className="px-1 py-0.5 rounded bg-muted text-[10px] font-mono">@company</kbd> to analyze</>
                    )}
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
                        : 'bg-card text-card-foreground border border-border'
                    }`}
                  >
                    {message.processing ? (
                      <div className="space-y-1.5 min-w-[200px] font-mono">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                            {streamingStage === 'execution' || streamingStage === 'executing' ? 'Executing tools...' :
                             streamingStage === 'formatting' ? 'Formatting output...' :
                             streamingStage === 'initialization' || streamingStage === 'analyzing' ? 'Classifying intent...' :
                             streamingStage === 'synthesizing' ? 'Composing response...' :
                             streamingStage === 'replying' ? 'Replying...' :
                             streamingStage === 'acting' ? 'Running action...' :
                             streamingStage ? streamingStage.charAt(0).toUpperCase() + streamingStage.slice(1) + '...' :
                             'Analyzing...'}
                          </span>
                        </div>
                        {streamingSteps.length > 0 && (
                          <div className="pl-1 space-y-0.5 max-h-[200px] overflow-y-auto border-l border-gray-200 dark:border-gray-700 ml-1.5">
                            {streamingSteps.map((step) => (
                              <div key={step.id} className="flex items-center gap-1.5 text-[10px] pl-2">
                                {step.status === 'done' ? (
                                  <span className="text-green-500 shrink-0 font-bold">✓</span>
                                ) : step.status === 'failed' ? (
                                  <span className="text-red-500 shrink-0 font-bold">✗</span>
                                ) : step.status === 'running' ? (
                                  <Loader2 className="h-2.5 w-2.5 animate-spin text-blue-500 shrink-0" />
                                ) : (
                                  <span className="text-gray-300 shrink-0">○</span>
                                )}
                                <span className={`truncate ${step.status === 'done' ? 'text-gray-500 dark:text-gray-500' : step.status === 'failed' ? 'text-red-400' : 'text-gray-700 dark:text-gray-200'}`}>
                                  {step.label}
                                </span>
                                {step.detail && (
                                  <span className="text-[9px] text-gray-400 shrink-0 ml-auto">{step.detail}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <>
                        <div className="prose prose-xs dark:prose-invert max-w-none break-words overflow-wrap-anywhere text-xs leading-snug">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              table({ children }: any) {
                                return (
                                  <div className="my-2 overflow-x-auto">
                                    <table className="w-full text-xs border-collapse">{children}</table>
                                  </div>
                                );
                              },
                              thead({ children }: any) {
                                return <thead>{children}</thead>;
                              },
                              tbody({ children }: any) {
                                return <tbody>{children}</tbody>;
                              },
                              tr({ children, ...props }: any) {
                                return (
                                  <tr className="border-b border-gray-100 dark:border-gray-700 even:bg-gray-50 dark:even:bg-gray-800/30">
                                    {children}
                                  </tr>
                                );
                              },
                              th({ children }: any) {
                                return (
                                  <th className="text-left py-1.5 pr-3 font-semibold text-gray-500 dark:text-gray-400 text-[10px] uppercase tracking-wider border-b-2 border-gray-200 dark:border-gray-600">
                                    {children}
                                  </th>
                                );
                              },
                              td({ children }: any) {
                                return (
                                  <td className="py-1 pr-3 text-gray-700 dark:text-gray-300 align-top">
                                    {children}
                                  </td>
                                );
                              },
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
                                  <h1 className="text-xs font-bold mb-1 mt-1.5 text-gray-900 dark:text-gray-100" {...props}>
                                    {children}
                                  </h1>
                                );
                              },
                              h2({ node, className, children, ...props }: any) {
                                return (
                                  <h2 className="text-xs font-semibold mb-0.5 mt-1.5 text-gray-800 dark:text-gray-200" {...props}>
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
                                <span className={step.status === 'done' ? 'text-muted-foreground line-through' : ''}>
                                  {step.label.includes(':') ? step.label.split(':')[1]?.trim() || step.label : step.label}
                                </span>
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
                        
                        {/* Clarification Options */}
                        {message.role === 'assistant' && (message as any).clarification && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {((message as any).clarification.options || []).map((opt: string, optIdx: number) => (
                              <button
                                key={optIdx}
                                className="px-3 py-1.5 text-sm rounded-lg border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-800/50 transition-colors"
                                onClick={() => {
                                  const clarifyAnswer = `${(message as any).clarification.question} → ${opt}`;
                                  setInput(clarifyAnswer);
                                  setTimeout(() => handleSend(), 50);
                                }}
                              >
                                {opt}
                              </button>
                            ))}
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
                            <div className="rounded-md border border-gray-100 dark:border-gray-800 px-2 py-1.5 text-sm">
                              <div className="flex items-center gap-2">
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
                              {entry.explanation && entry.status === 'success' && (
                                <p className="mt-1 text-xs text-muted-foreground leading-relaxed whitespace-pre-line">{entry.explanation}</p>
                              )}
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-xs">
                            {entry.explanation || label}
                            {!entry.explanation && entry.companyName && ` · ${entry.companyName}`}
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
                      <div className="px-2.5 pb-1.5 space-y-1 border-t border-gray-100 dark:border-gray-800">
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
                  const newArtifact = {
                    id: `drag-${Date.now()}`,
                    type: section.section?.type || 'memo',
                    content,
                    source: 'drag',
                  };
                  setMemoArtifacts(prev => [...prev, newArtifact]);
                  setMemoContextOn(true);
                }
              } catch {}
            }
          }}
        >
          <input
            ref={uploadFileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.xlsx,.xls,.csv"
            className="hidden"
            onChange={handleFileSelect}
          />
          {/* Memo context preview card — shown when memo toggle is on and artifacts exist */}
          {/* Context chips — show artifacts as removable chips above input */}
          {memoArtifacts.length > 0 && (
            <div className="mb-1.5 mx-0.5 flex flex-wrap gap-1 items-center">
              {memoArtifacts.slice(-10).map((a: any, i: number) => {
                const title = a.title || a.data?.title || a.name || a.data?.name || '';
                const content = a.content || a.data?.content || a.summary || a.data?.summary || a.text || a.data?.text || '';
                const chipLabel = title || (content ? content.slice(0, 40) : (a.type || 'context'));
                const actualIndex = memoArtifacts.length > 10 ? memoArtifacts.length - 10 + i : i;
                return (
                  <span
                    key={a.id || i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-[11px] text-indigo-700 dark:text-indigo-300 max-w-[200px] group"
                    title={title && content ? `${title}: ${content.slice(0, 200)}` : (content || title)}
                  >
                    <span className="truncate">{chipLabel}</span>
                    <button
                      onClick={() => {
                        const updated = memoArtifacts.filter((_: any, j: number) => j !== actualIndex);
                        setMemoArtifacts(updated);
                      }}
                      className="shrink-0 h-3 w-3 opacity-60 hover:opacity-100 hover:text-destructive transition-opacity"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                );
              })}
              {memoArtifacts.length > 0 && (
                <button
                  onClick={() => setMemoArtifacts([])}
                  className="text-[9px] text-muted-foreground hover:text-destructive px-1"
                  title="Clear all context"
                >
                  Clear all
                </button>
              )}
            </div>
          )}
          {/* Chip Tray — capability surface above input */}
          <ChipTray
            companyId={mode === 'pnl' ? matrixData?.rows?.find((r: any) => r.companyId)?.companyId : undefined}
            onSelectChip={(def: ChipDef) => chipInputRef.current?.insertChip(def)}
            collapsed={!chipTrayOpen}
            onToggleCollapse={() => setChipTrayOpen(prev => !prev)}
            className="mx-0.5 mb-1 rounded-lg"
          />
          {/* Toolbar — toggles above input */}
          <div className="flex items-center gap-1 mb-1 mx-0.5">
            <Button
              variant="ghost"
              size="icon"
              className={`h-6 w-6 rounded-md ${planModeOn ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300' : 'text-muted-foreground'}`}
              onClick={() => setPlanModeOn(prev => !prev)}
              title={planModeOn ? 'Plan mode ON' : 'Plan mode OFF'}
            >
              <ListTodo className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={`h-6 w-6 rounded-md ${memoContextOn ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300' : 'text-muted-foreground'}`}
              onClick={() => setMemoContextOn(prev => !prev)}
              title={memoContextOn ? 'Context ON — artifacts sent with messages' : 'Context OFF'}
            >
              <BookOpen className="h-3 w-3" />
            </Button>
            {planModeOn && (
              <Badge variant="outline" className="text-[9px] h-4 px-1.5 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800">
                Plan
              </Badge>
            )}
            {memoContextOn && memoArtifacts.length > 0 && (
              <span className="text-[9px] text-indigo-500 dark:text-indigo-400">{memoArtifacts.length} context item{memoArtifacts.length !== 1 ? 's' : ''}</span>
            )}
          </div>
          {/* Staged file attachments — shown as removable chips */}
          {pendingFiles.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-1 mx-0.5">
              {pendingFiles.map((file, i) => {
                const isSpreadsheet = /\.(xlsx?|csv)$/i.test(file.name);
                const Icon = isSpreadsheet ? FileSpreadsheet : FileTextIcon;
                return (
                  <span
                    key={`${file.name}-${i}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-[11px] text-emerald-700 dark:text-emerald-300 max-w-[200px] group"
                    title={file.name}
                  >
                    <Icon className="h-3 w-3 shrink-0" />
                    <span className="truncate">{file.name}</span>
                    <button
                      onClick={() => setPendingFiles(prev => prev.filter((_, j) => j !== i))}
                      className="shrink-0 h-3 w-3 opacity-60 hover:opacity-100 hover:text-destructive transition-opacity"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                );
              })}
            </div>
          )}
          {/* Input box — clean, full width. Supports inline chips + NL text. */}
          <div className="flex items-end gap-1.5 rounded-xl border border-input bg-muted/30 dark:bg-muted/20 px-2 py-1.5 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-background">
            <ChipInput
              ref={chipInputRef}
              onSubmit={(segments) => handleSend()}
              onChange={() => {
                // Keep the plain text state in sync (for send button disabled check)
                const segs = chipInputRef.current?.getSegments() ?? [];
                const text = segs.filter(s => s.type === 'text').map(s => (s as any).text).join('');
                setInput(text || (segs.some(s => s.type === 'chip') ? ' ' : ''));
              }}
              placeholder={planModeOn ? 'Describe what to plan... (Enter to send)' : mode === 'pnl' ? 'Adjust forecast, ask about P&L... (Enter to send)' : mode === 'legal' ? 'Ask about a clause, upload a contract... (Enter to send)' : 'Type or drag tools here... (Enter to send)'}
              disabled={isLoading}
              minHeight={36}
              maxHeight={120}
            />
            {onUploadDocument ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 rounded-lg"
                disabled={uploading || isLoading}
                onClick={() => uploadFileInputRef.current?.click()}
                title="Attach files"
              >
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0 rounded-lg"
              onClick={handleSend}
              disabled={(!input.trim() && !chipInputRef.current?.hasContent() && pendingFiles.length === 0) || isLoading}
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
                  {documentViewerMessage?.docsSections?.[0]?.content || documentViewerMessage?.docsSections?.[0]?.title || 'Document'}
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
                {documentViewerMessage?.docsSections?.map((section: any, sIdx: number) => {
                  const sectionType = section.type || 'paragraph';

                  // Render by structured section type
                  return (
                    <React.Fragment key={sIdx}>
                      {/* Headings */}
                      {sectionType === 'heading1' && (
                        <h1 className="text-2xl font-bold mb-4 mt-8 first:mt-0 text-gray-900 dark:text-gray-100 border-b pb-2">
                          {section.content || section.title}
                        </h1>
                      )}
                      {sectionType === 'heading2' && (
                        <h2 className="text-xl font-semibold mb-3 mt-6 text-gray-800 dark:text-gray-200">
                          {section.content || section.title}
                        </h2>
                      )}
                      {sectionType === 'heading3' && (
                        <h3 className="text-lg font-medium mb-2 mt-4 text-gray-700 dark:text-gray-300">
                          {section.content || section.title}
                        </h3>
                      )}

                      {/* Paragraph — render markdown */}
                      {sectionType === 'paragraph' && section.content && (
                        <div className="prose prose-sm dark:prose-invert max-w-none mb-4 text-gray-700 dark:text-gray-300 leading-relaxed">
                          <ReactMarkdown>{section.content}</ReactMarkdown>
                        </div>
                      )}

                      {/* Table — structured headers + rows */}
                      {sectionType === 'table' && section.table && (
                        <div className="my-4 overflow-x-auto">
                          <table className="w-full text-sm border-collapse">
                            {section.table.caption && (
                              <caption className="text-xs text-muted-foreground mb-2 text-left font-medium">{section.table.caption}</caption>
                            )}
                            <thead>
                              <tr className="border-b-2 border-gray-200 dark:border-gray-600">
                                {section.table.headers?.map((h: string, hi: number) => (
                                  <th key={hi} className="text-left py-2 pr-4 font-semibold text-gray-600 dark:text-gray-400 text-xs uppercase tracking-wider">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {section.table.rows?.map((row: any[], ri: number) => (
                                <tr key={ri} className={`border-b border-gray-100 dark:border-gray-700 ${ri % 2 === 1 ? 'bg-gray-50 dark:bg-gray-800/30' : ''}`}>
                                  {row.map((cell: any, ci: number) => (
                                    <td key={ci} className="py-1.5 pr-4 text-gray-700 dark:text-gray-300">
                                      {typeof cell === 'string' ? <ReactMarkdown>{cell}</ReactMarkdown> : String(cell ?? '—')}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {/* Chart — render via TableauLevelCharts */}
                      {sectionType === 'chart' && section.chart && (() => {
                        const chart = section.chart;
                        const hasData = chart.data && (Array.isArray(chart.data) ? chart.data.length > 0 : typeof chart.data === 'object' && Object.keys(chart.data).length > 0);
                        return hasData ? (
                          <div className="my-6 border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-gray-50 dark:bg-gray-800/30">
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
                          <div className="my-4 flex items-center justify-center h-20 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-sm text-muted-foreground">
                            {chart.title ? `${chart.title} — data unavailable` : 'Chart data unavailable'}
                          </div>
                        );
                      })()}

                      {/* List — bullet or numbered */}
                      {sectionType === 'list' && section.items && (
                        <ul className="list-disc list-inside mb-4 space-y-1 text-gray-700 dark:text-gray-300 text-sm">
                          {section.items.map((item: string, li: number) => (
                            <li key={li}>
                              <ReactMarkdown components={{ p: ({ children }) => <span>{children}</span> }}>{item}</ReactMarkdown>
                            </li>
                          ))}
                        </ul>
                      )}

                      {/* Quote */}
                      {sectionType === 'quote' && section.content && (
                        <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 py-2 mb-4 text-gray-600 dark:text-gray-400 italic text-sm">
                          <ReactMarkdown>{section.content}</ReactMarkdown>
                        </blockquote>
                      )}

                      {/* Code block */}
                      {sectionType === 'code' && section.content && (
                        <pre className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 mb-4 overflow-x-auto text-xs font-mono text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
                          {section.content}
                        </pre>
                      )}

                      {/* Fallback: legacy format (section.title + section.content without type) */}
                      {!sectionType.startsWith('heading') && sectionType !== 'paragraph' && sectionType !== 'table' && sectionType !== 'chart' && sectionType !== 'list' && sectionType !== 'quote' && sectionType !== 'code' && (
                        <>
                          {section.title && (
                            <h2 className="text-xl font-semibold mb-3 mt-6 text-gray-800 dark:text-gray-200">
                              {section.title}
                            </h2>
                          )}
                          {section.content && (
                            <div className="prose prose-sm dark:prose-invert max-w-none mb-4 text-gray-700 dark:text-gray-300 leading-relaxed">
                              <ReactMarkdown>{section.content}</ReactMarkdown>
                            </div>
                          )}
                        </>
                      )}
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