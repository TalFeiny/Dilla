'use client';

/**
 * Matrix Control Panel - Home/Control Centre
 * 
 * One matrix = killer control centre. Merges portfolio, valuation, documents,
 * analytics, charts, portfolio construction, currency, and fund admin into a
 * single canvas with sophisticated shadcn components.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { UnifiedMatrix, MatrixData } from '@/components/matrix/UnifiedMatrix';
import { MatrixMode } from '@/lib/matrix/matrix-api-service';
import { getModeConfig, getAllModes } from '@/lib/matrix/matrix-mode-manager';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Database,
  Sparkles,
  Users,
  FileText,
  Settings,
  Plus,
  Upload,
  BarChart3,
  Calculator,
  FileSpreadsheet,
  Search,
  Loader2,
  Trash2,
  ScrollText,
  Zap,
  MoreHorizontal,
} from 'lucide-react';
import supabase from '@/lib/supabase';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { addCompanyToMatrix } from '@/lib/matrix/matrix-api-service';
import { formatCurrency } from '@/lib/utils/formatters';
import { getAvailableActions, type CellAction } from '@/lib/matrix/cell-action-registry';
import { toast } from 'sonner';
import CitationDisplay, { type Citation, deduplicateCitations } from '@/components/CitationDisplay';
import { ScenarioInput } from '@/components/matrix/ScenarioInput';
import type { ToolCallEntry } from '@/components/matrix/AgentPanel';

const MAX_TOOL_CALL_ENTRIES = 100;

export default function MatrixControlPanel() {
  const router = useRouter();
  const [mode, setMode] = useState<MatrixMode>('portfolio');
  const [fundId, setFundId] = useState<string | undefined>();
  const [funds, setFunds] = useState<any[]>([]);
  const [matrixData, setMatrixData] = useState<MatrixData | null>(null);
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showScenarioSheet, setShowScenarioSheet] = useState(false);
  const [companySearchQuery, setCompanySearchQuery] = useState('');
  const [companySearchResults, setCompanySearchResults] = useState<any[]>([]);
  const [isSearchingCompanies, setIsSearchingCompanies] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<any>(null);
  const [isAddingCompany, setIsAddingCompany] = useState(false);
  const [availableCompanies, setAvailableCompanies] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [newCompany, setNewCompany] = useState({
    name: '',
    sector: '',
    stage: '',
    investmentAmount: 0,
    ownershipPercentage: 0,
    investmentDate: new Date().toISOString().split('T')[0],
    currentArr: 0,
    valuation: 0
  });
  const [showAddFundModal, setShowAddFundModal] = useState(false);
  const [deletingPortfolioId, setDeletingPortfolioId] = useState<string | null>(null);
  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    fundSize: 0,
    targetMultiple: 30000,
    vintageYear: new Date().getFullYear(),
    fundType: 'venture'
  });
  const [portfolioMetrics, setPortfolioMetrics] = useState<{
    fundSize?: number;
    totalInvested?: number;
    totalValuation?: number;
  }>({});
  const [citations, setCitations] = useState<Citation[]>([]);
  const [showAuditLog, setShowAuditLog] = useState(false);
  const [auditLogEntries, setAuditLogEntries] = useState<any[]>([]);
  const [auditLogLoading, setAuditLogLoading] = useState(false);
  const [lastValuationWorkings, setLastValuationWorkings] = useState<{
    companyName: string;
    method: string;
    explanation: string;
    details: any;
  } | null>(null);
  const [availableActions, setAvailableActions] = useState<CellAction[]>([]);
  /** Phase 6: Tool-call feed for Agent panel Activity tab */
  const [toolCallEntries, setToolCallEntries] = useState<ToolCallEntry[]>([]);

  useEffect(() => {
    checkUser();
    loadFunds();
  }, []);

  useEffect(() => {
    getAvailableActions(mode || 'portfolio')
      .then(setAvailableActions)
      .catch(() => setAvailableActions([]));
  }, [mode]);

  const checkUser = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        router.push('/login');
        return;
      }
      setUser(user);
    } catch (error) {
      console.error('Error checking user:', error);
      router.push('/login');
    } finally {
      setLoading(false);
    }
  };

  const loadFunds = async () => {
    try {
      const response = await fetch('/api/funds');
      if (response.ok) {
        const data = await response.json();
        // Handle both array format (new) and object format (legacy)
        const fundsArray = Array.isArray(data) ? data : (data.funds || []);
        setFunds(fundsArray);
        if (fundsArray.length > 0 && !fundId) {
          setFundId(fundsArray[0].id);
        }
      }
    } catch (error) {
      console.error('Error loading funds:', error);
    }
  };

  // Load portfolio metrics when fundId changes
  useEffect(() => {
    if (fundId && mode === 'portfolio') {
      loadPortfolioMetrics();
    }
  }, [fundId, mode]);

  // Fetch audit log (matrix_edits) when Audit sheet opens
  useEffect(() => {
    if (!showAuditLog || !fundId) return;
    const fetchAuditLog = async () => {
      setAuditLogLoading(true);
      try {
        const res = await fetch(`/api/portfolio/${fundId}/matrix-edits?limit=100`);
        if (res.ok) {
          const { edits } = await res.json();
          setAuditLogEntries(edits || []);
        } else {
          setAuditLogEntries([]);
        }
      } catch (e) {
        console.error('Failed to fetch audit log:', e);
        setAuditLogEntries([]);
      } finally {
        setAuditLogLoading(false);
      }
    };
    fetchAuditLog();
  }, [showAuditLog, fundId]);

  const loadPortfolioMetrics = async () => {
    if (!fundId) return;
    
    try {
      const response = await fetch('/api/portfolio');
      if (response.ok) {
        const portfolios = await response.json();
        const portfolio = Array.isArray(portfolios) 
          ? portfolios.find((p: any) => p.id === fundId)
          : null;
        
        if (portfolio) {
          setPortfolioMetrics({
            fundSize: portfolio.fundSize,
            totalInvested: portfolio.totalInvested,
            totalValuation: portfolio.totalValuation,
          });
        }
      }
    } catch (error) {
      console.error('Error loading portfolio metrics:', error);
    }
  };

  const handleAddPortfolio = async () => {
    try {
      const response = await fetch('/api/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPortfolio)
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.id) {
        setShowAddFundModal(false);
        setNewPortfolio({
          name: '',
          fundSize: 0,
          targetMultiple: 30000,
          vintageYear: new Date().getFullYear(),
          fundType: 'venture'
        });
        // Optimistically add new fund to list and select it so grid appears immediately
        const newFund = {
          id: data.id,
          name: data.name || newPortfolio.name,
          fund_size_usd: data.fund_size_usd ?? newPortfolio.fundSize,
          vintage_year: data.vintage_year ?? newPortfolio.vintageYear,
          fund_type: data.fund_type || newPortfolio.fundType,
          ...data
        };
        setFunds((prev) => [newFund, ...(prev || [])]);
        setFundId(data.id);
        setMatrixData(null);
        await loadFunds();
      } else {
        alert(data?.error || 'Failed to create fund');
      }
    } catch (error) {
      console.error('Error adding portfolio:', error);
      alert('An error occurred while creating the fund. Please try again.');
    }
  };

  const handleDeletePortfolio = async (portfolioId: string) => {
    if (!confirm('Are you sure you want to delete this portfolio? This will remove the fund and unlink all associated companies. This action cannot be undone.')) {
      return;
    }

    setDeletingPortfolioId(portfolioId);

    try {
      const response = await fetch(`/api/portfolio/${portfolioId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to delete portfolio' }));
        alert(errorData.error || 'Failed to delete portfolio');
        return;
      }

      await loadFunds();
      
      if (fundId === portfolioId) {
        setFundId(undefined);
        setMatrixData(null);
        setPortfolioMetrics({});
      }
      
      alert('Portfolio deleted successfully!');
    } catch (error) {
      console.error('Error deleting portfolio:', error);
      alert('An error occurred while deleting the portfolio. Please try again.');
    } finally {
      setDeletingPortfolioId(null);
    }
  };

  const generateRandomPortfolio = async () => {
    const portfolioName = `Random Portfolio ${new Date().toLocaleDateString()}`;
    const fundSize = Math.floor(Math.random() * 90000000) + 10000000; // 10M to 100M
    
    try {
      // Create the portfolio first
      const portfolioResponse = await fetch('/api/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: portfolioName,
          fundSize: fundSize,
          targetMultiple: 30000,
          vintageYear: new Date().getFullYear(),
          fundType: 'venture'
        })
      });

      if (!portfolioResponse.ok) {
        alert('Failed to create random portfolio');
        return;
      }

      const newPortfolio = await portfolioResponse.json();
      const portfolioId = newPortfolio.id;

      // Fetch random companies from the database
      const numCompanies = Math.floor(Math.random() * 10) + 5; // 5-15 companies
      const randomCompaniesResponse = await fetch(`/api/companies/random?limit=${numCompanies}`);
      
      if (!randomCompaniesResponse.ok) {
        alert('Failed to fetch random companies');
        return;
      }
      
      const selectedCompanies = await randomCompaniesResponse.json();
      const companiesArray = Array.isArray(selectedCompanies) ? selectedCompanies : [];
      
      if (companiesArray.length === 0) {
        alert('No companies found to add to portfolio');
        return;
      }

      // Add each company to the portfolio
      let successCount = 0;
      let failCount = 0;
      
      for (const company of companiesArray) {
        const investmentAmount = Math.floor(Math.random() * 4500000) + 500000; // 500K to 5M
        const ownershipPercentage = Math.floor(Math.random() * 15) + 5; // 5% to 20%
        
        const response = await fetch(`/api/portfolio/${portfolioId}/companies`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: company.name,
            sector: company.sector || 'Technology',
            stage: 'Series A',
            investmentAmount: investmentAmount,
            ownershipPercentage: ownershipPercentage,
            investmentDate: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000 * 2).toISOString().split('T')[0],
            currentArr: company.current_arr_usd || Math.floor(Math.random() * 10000000),
            valuation: company.total_invested_usd || investmentAmount * (100 / ownershipPercentage)
          })
        });
        
        if (response.ok) {
          successCount++;
        } else {
          failCount++;
        }
      }

      await loadFunds();
      setFundId(portfolioId);
      alert(`Created random portfolio "${portfolioName}" with ${successCount} companies!`);
    } catch (error) {
      console.error('Error generating random portfolio:', error);
      alert('An error occurred while generating the random portfolio. Please try again.');
    }
  };

  const modeConfig = getModeConfig(mode);
  const allModes = getAllModes();

  /** Phase 6: Append tool-call log entry for Activity tab */
  const onToolCallLog = useCallback((entry: Omit<ToolCallEntry, 'id' | 'at'>) => {
    setToolCallEntries((prev) => {
      const next = [...prev, { ...entry, id: crypto.randomUUID?.() ?? `tc-${Date.now()}`, at: new Date().toISOString() }];
      return next.slice(-MAX_TOOL_CALL_ENTRIES);
    });
  }, []);

  const handleModeChange = (newMode: MatrixMode) => {
    // Reset all state when switching modes to prevent bugs
    setMode(newMode);
    setMatrixData(null);
    setCitations([]);
    // Clear any pending queries or search states
    setCompanySearchQuery('');
    setCompanySearchResults([]);
    setSearchQuery('');
    setAvailableCompanies([]);
  };

  const handleQuery = async (queryText: string): Promise<MatrixData> => {
    const { queryMatrix } = await import('@/lib/matrix/matrix-api-service');
    return queryMatrix({
      query: queryText,
      mode,
      fundId,
    });
  };

  const handleCellEdit = async (
    rowId: string,
    columnId: string,
    value: any,
    options?: { data_source?: string; metadata?: Record<string, unknown> }
  ) => {
    const { updateMatrixCell } = await import('@/lib/matrix/matrix-api-service');
    
    const row = matrixData?.rows.find(r => r.id === rowId);
    const oldValue = row?.cells[columnId]?.value;
    
    try {
      await updateMatrixCell({
        rowId,
        columnId,
        oldValue,
        newValue: value,
        companyId: row?.companyId,
        fundId,
        userId: user?.id,
        data_source: options?.data_source as 'manual' | 'service' | 'document' | 'api' | 'formula' | undefined,
        metadata: options?.metadata,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save cell edit';
      const isMissingCompany =
        !row?.companyId ||
        String(msg).toLowerCase().includes('company_id') ||
        String(msg).toLowerCase().includes('missing required');
      toast.error(
        isMissingCompany
          ? 'Save row to portfolio to persist edits. Rows from @search are in-memory only.'
          : msg
      );
      throw err; // rethrow so UnifiedMatrix knows save failed (edit stays visible)
    }

    if (matrixData) {
      const isCompanyNameColumn = columnId === 'company' || columnId === 'companyName';
      const updatedRows = matrixData.rows.map(r => {
        if (r.id === rowId) {
          const updated = {
            ...r,
            cells: {
              ...r.cells,
              [columnId]: {
                ...r.cells[columnId],
                value,
                source: 'manual' as const,
                lastUpdated: new Date().toISOString(),
                editedBy: user?.email,
              },
            },
          };
          if (isCompanyNameColumn && value != null && value !== '') {
            updated.companyName = String(value);
          }
          return updated;
        }
        return r;
      });
      
      setMatrixData({
        ...matrixData,
        rows: updatedRows,
      });
    }
  };

  const handleApplyScenario = async (cellUpdates: any[]) => {
    if (!matrixData) return;

    // Apply each cell update to the matrix
    const updatedRows = matrixData.rows.map((row) => {
      const updatesForRow = cellUpdates.filter((update) => update.row_id === row.id);
      if (updatesForRow.length === 0) return row;

      const updatedCells = { ...row.cells };
      for (const update of updatesForRow) {
        updatedCells[update.column_id] = {
          ...updatedCells[update.column_id],
          value: update.new_value,
          displayValue: typeof update.new_value === 'number' 
            ? update.new_value.toLocaleString() 
            : String(update.new_value),
          source: 'scenario' as const,
          lastUpdated: new Date().toISOString(),
          editedBy: user?.email,
          metadata: {
            ...updatedCells[update.column_id]?.metadata,
            scenario: true,
            scenario_change: update.change,
            scenario_change_pct: update.change_pct,
          },
        };
      }

      return {
        ...row,
        cells: updatedCells,
      };
    });

    setMatrixData({
      ...matrixData,
      rows: updatedRows,
    });

    setShowScenarioSheet(false);
  };

  // Search for companies when query changes (for simple add company)
  useEffect(() => {
    const searchCompanies = async () => {
      if (!companySearchQuery.trim() || companySearchQuery.length < 2) {
        setCompanySearchResults([]);
        return;
      }

      // Handle @CompanyName mentions
      const query = companySearchQuery.startsWith('@') 
        ? companySearchQuery.slice(1).trim()
        : companySearchQuery.trim();

      if (!query) {
        setCompanySearchResults([]);
        return;
      }

      setIsSearchingCompanies(true);
      try {
        const response = await fetch(`/api/companies/search?q=${encodeURIComponent(query)}&limit=10`);
        if (response.ok) {
          const data = await response.json();
          setCompanySearchResults(data.companies || []);
        }
      } catch (error) {
        console.error('Error searching companies:', error);
        setCompanySearchResults([]);
      } finally {
        setIsSearchingCompanies(false);
      }
    };

    const debounceTimer = setTimeout(searchCompanies, 300);
    return () => clearTimeout(debounceTimer);
  }, [companySearchQuery]);

  // Search companies for full form
  const searchCompaniesForForm = async (query: string) => {
    setIsSearching(true);
    try {
      const response = await fetch(`/api/companies/search?q=${encodeURIComponent(query)}&limit=100`);
      if (response.ok) {
        const data = await response.json();
        setAvailableCompanies(data.companies || []);
      } else {
        console.error('Error searching companies:', response.status, response.statusText);
        setAvailableCompanies([]);
      }
    } catch (error) {
      console.error('Error searching companies:', error);
      setAvailableCompanies([]);
    } finally {
      setIsSearching(false);
    }
  };


  const handleAddCompany = async () => {
    if (!fundId) {
      alert('Please select a fund first');
      return;
    }

    // Validate inputs
    if (!newCompany.name || newCompany.name.trim() === '') {
      alert('Please enter a company name');
      return;
    }

    if (!newCompany.investmentAmount || newCompany.investmentAmount <= 0) {
      alert('Please enter a valid investment amount (greater than 0)');
      return;
    }

    setIsAddingCompany(true);
    try {
      await addCompanyToMatrix({
        name: newCompany.name,
        fundId,
        sector: newCompany.sector,
        stage: newCompany.stage,
        investmentAmount: newCompany.investmentAmount,
        ownershipPercentage: newCompany.ownershipPercentage,
        investmentDate: newCompany.investmentDate,
        currentArr: newCompany.currentArr,
        valuation: newCompany.valuation,
      });

      // Reset form
      setNewCompany({
        name: '',
        sector: '',
        stage: '',
        investmentAmount: 0,
        ownershipPercentage: 0,
        investmentDate: new Date().toISOString().split('T')[0],
        currentArr: 0,
        valuation: 0
      });
      setCompanySearchQuery('');
      setSelectedCompany(null);
      setCompanySearchResults([]);
      setSearchQuery('');
      setAvailableCompanies([]);

      // Always refresh matrix data after successful add (even if grid is empty)
      const event = new CustomEvent('refreshMatrix');
      window.dispatchEvent(event);
      
      // Reload portfolio metrics
      await loadPortfolioMetrics();
    } catch (error) {
      console.error('Error adding company:', error);
      alert(error instanceof Error ? error.message : 'Failed to add company');
    } finally {
      setIsAddingCompany(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  const modeIcons = {
    portfolio: Database,
    query: Sparkles,
    custom: FileText,
    lp: Users,
  };

  const currentModeConfig = getModeConfig(mode);
  const CurrentIcon = modeIcons[mode];

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* Header with Mode Selector */}
      <div className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center space-x-4">
              {/* Mode Selector - Tiny Button */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 px-2">
                    <CurrentIcon className="h-3.5 w-3.5 mr-1.5" />
                    <span className="text-xs">{currentModeConfig.label}</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  {allModes.map((m) => {
                    const config = getModeConfig(m);
                    const Icon = modeIcons[m];
                    return (
                      <DropdownMenuItem
                        key={m}
                        onClick={() => handleModeChange(m)}
                        className={cn(
                          "flex items-center space-x-2",
                          mode === m && "bg-accent"
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        <span>{config.label}</span>
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <div className="flex items-center space-x-3">
              {/* Fund Selector (for Portfolio/LP modes) — keep only Mode + Fund */}
              {(mode === 'portfolio' || mode === 'lp') && (
                funds.length > 0 ? (
                  <Select value={fundId || ''} onValueChange={setFundId}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Select fund" />
                    </SelectTrigger>
                    <SelectContent>
                      {funds.map((fund) => (
                        <SelectItem key={fund.id} value={fund.id}>
                          {fund.name || fund.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : null
              )}

              {/* Overflow menu — Create Fund, What if, Citations, Settings, Delete fund, Metrics */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {(mode === 'portfolio' || mode === 'lp') && (
                    <>
                      <DropdownMenuItem onClick={() => setShowAddFundModal(true)}>
                        <Plus className="h-4 w-4 mr-2" />
                        Create Fund
                      </DropdownMenuItem>
                      {fundId && portfolioMetrics.fundSize !== undefined && (
                        <DropdownMenuItem disabled className="opacity-80">
                          <span className="text-xs">
                            Size: {formatCurrency(portfolioMetrics.fundSize)} · Invested: {formatCurrency(portfolioMetrics.totalInvested)} · Value: {formatCurrency(portfolioMetrics.totalValuation)}
                          </span>
                        </DropdownMenuItem>
                      )}
                      {fundId && funds.length > 0 && (
                        <DropdownMenuItem
                          onClick={() => handleDeletePortfolio(fundId)}
                          disabled={deletingPortfolioId === fundId}
                          className="text-destructive focus:text-destructive"
                        >
                          {deletingPortfolioId === fundId ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4 mr-2" />
                          )}
                          Delete fund
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                    </>
                  )}
                  <DropdownMenuItem onClick={() => setShowScenarioSheet(true)}>
                    <Zap className="h-4 w-4 mr-2" />
                    What if scenarios
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setShowAuditLog(true)}>
                    <ScrollText className="h-4 w-4 mr-2" />
                    Citations & audit
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setShowSettings(true)}>
                    <Settings className="h-4 w-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Add Fund Dialog */}
                {(mode === 'portfolio' || mode === 'lp') && (
                  <Dialog open={showAddFundModal} onOpenChange={setShowAddFundModal}>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Fund</DialogTitle>
                        <DialogDescription>
                          Create a new fund to manage your portfolio companies
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div>
                          <Label htmlFor="fundName">Fund Name *</Label>
                          <Input
                            id="fundName"
                            value={newPortfolio.name}
                            onChange={(e) => setNewPortfolio({ ...newPortfolio, name: e.target.value })}
                            placeholder="Enter fund name"
                          />
                        </div>
                        <div>
                          <Label htmlFor="fundSize">Fund Size (USD) *</Label>
                          <Input
                            id="fundSize"
                            type="number"
                            value={newPortfolio.fundSize || ''}
                            onChange={(e) => setNewPortfolio({ ...newPortfolio, fundSize: parseFloat(e.target.value) || 0 })}
                            placeholder="Enter fund size"
                          />
                        </div>
                        <div>
                          <Label htmlFor="vintageYear">Vintage Year</Label>
                          <Input
                            id="vintageYear"
                            type="number"
                            value={newPortfolio.vintageYear}
                            onChange={(e) => setNewPortfolio({ ...newPortfolio, vintageYear: parseInt(e.target.value) || new Date().getFullYear() })}
                            placeholder="Enter vintage year"
                          />
                        </div>
                        <div>
                          <Label htmlFor="fundType">Fund Type</Label>
                          <Select
                            value={newPortfolio.fundType}
                            onValueChange={(value) => setNewPortfolio({ ...newPortfolio, fundType: value })}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select fund type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="venture">Venture Capital</SelectItem>
                              <SelectItem value="growth">Growth Equity</SelectItem>
                              <SelectItem value="private_equity">Private Equity</SelectItem>
                              <SelectItem value="debt">Debt Fund</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex justify-end gap-2 pt-4">
                          <Button
                            variant="outline"
                            onClick={() => {
                              setShowAddFundModal(false);
                              setNewPortfolio({
                                name: '',
                                fundSize: 0,
                                targetMultiple: 30000,
                                vintageYear: new Date().getFullYear(),
                                fundType: 'venture'
                              });
                            }}
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={handleAddPortfolio}
                            disabled={!newPortfolio.name.trim() || !newPortfolio.fundSize || newPortfolio.fundSize <= 0}
                          >
                            <Plus className="w-4 h-4 mr-2" />
                            Create Fund
                          </Button>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                )}

                <Sheet open={showScenarioSheet} onOpenChange={setShowScenarioSheet}>
                  <SheetContent side="right" className="w-[400px] sm:w-[600px] overflow-y-auto">
                    <SheetHeader>
                      <SheetTitle className="flex items-center gap-2">
                        <Zap className="h-5 w-5" />
                        Scenario Painting
                      </SheetTitle>
                      <SheetDescription>
                        Create "what if" scenarios and see their impact on matrix cells
                      </SheetDescription>
                    </SheetHeader>
                    <div className="mt-6">
                      <ScenarioInput
                        matrixData={matrixData}
                        fundId={fundId}
                        onApplyScenario={handleApplyScenario}
                      />
                    </div>
                  </SheetContent>
                </Sheet>

                <Sheet open={showSettings} onOpenChange={setShowSettings}>
                  <SheetContent side="right" className="w-[400px] sm:w-[540px]">
                    <SheetHeader>
                      <SheetTitle>Matrix Settings</SheetTitle>
                      <SheetDescription>
                        Configure matrix display options and preferences
                      </SheetDescription>
                    </SheetHeader>
                    <div className="mt-6 space-y-4">
                      {/* Settings content will go here */}
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-sm">Display Options</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <p className="text-sm text-muted-foreground">
                            Settings coming soon
                          </p>
                        </CardContent>
                      </Card>
                    </div>
                  </SheetContent>
                </Sheet>

                <Sheet open={showAuditLog} onOpenChange={setShowAuditLog}>
                  <SheetContent side="right" className="w-[400px] sm:w-[600px] overflow-y-auto">
                    <SheetHeader>
                      <SheetTitle className="flex items-center gap-2">
                        <ScrollText className="h-5 w-5" />
                        Citations & service logs
                      </SheetTitle>
                      <SheetDescription>
                        Query citations, valuation workings, and audit trail for decisions
                      </SheetDescription>
                    </SheetHeader>
                    <div className="mt-6 space-y-6">
                      {citations.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2">Sources & citations</h4>
                          <CitationDisplay citations={citations} format="both" />
                        </div>
                      )}
                      {lastValuationWorkings && (
                        <div>
                          <h4 className="text-sm font-semibold mb-2">Last valuation workings</h4>
                          <Card>
                            <CardContent className="pt-4 space-y-2">
                              <p className="text-xs text-muted-foreground">
                                {lastValuationWorkings.companyName} · {lastValuationWorkings.method}
                              </p>
                              {lastValuationWorkings.explanation && (
                                <p className="text-sm">{lastValuationWorkings.explanation}</p>
                              )}
                              {lastValuationWorkings.details && (
                                <details className="text-xs">
                                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                                    View full details
                                  </summary>
                                  <pre className="mt-2 p-2 rounded bg-muted overflow-x-auto max-h-48 overflow-y-auto">
                                    {JSON.stringify(lastValuationWorkings.details, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </CardContent>
                          </Card>
                        </div>
                      )}
                      <div>
                        <h4 className="text-sm font-semibold mb-2">Service logs (audit)</h4>
                        {auditLogLoading ? (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading…
                          </div>
                        ) : !fundId ? (
                          <p className="text-sm text-muted-foreground">Select a fund to view logs.</p>
                        ) : auditLogEntries.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No service runs or edits yet.</p>
                        ) : (
                          <div className="space-y-2 max-h-[400px] overflow-y-auto">
                            {auditLogEntries.map((e: any) => (
                              <Card key={e.id} className="p-3">
                                <div className="text-xs space-y-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-medium truncate">{e.companyName || e.companyId}</span>
                                    <span className="text-muted-foreground shrink-0">
                                      {e.editedAt ? new Date(e.editedAt).toLocaleString() : '—'}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 text-muted-foreground">
                                    <span>{e.columnId}</span>
                                    <span>·</span>
                                    <span>{e.dataSource === 'service' ? (e.metadata?.service || 'service') : e.editedBy || e.dataSource}</span>
                                  </div>
                                  {(e.oldValue != null || e.newValue != null) && (
                                    <div className="pt-1 truncate">
                                      {e.oldValue != null && <span className="text-red-600 line-through">{String(e.oldValue)}</span>}
                                      {e.oldValue != null && e.newValue != null && ' → '}
                                      {e.newValue != null && <span className="text-green-600">{String(e.newValue)}</span>}
                                    </div>
                                  )}
                                  {e.metadata?.explanation && (
                                    <p className="pt-1 text-muted-foreground line-clamp-2">{e.metadata.explanation}</p>
                                  )}
                                </div>
                              </Card>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </SheetContent>
                </Sheet>
              </div>
            </div>

          {/* Mode Description */}
          <div className="pb-3">
            <p className="text-sm text-muted-foreground">
              {modeConfig.description}
            </p>
          </div>
        </div>
      </div>

      {/* Matrix Canvas: out-of-grid wrapper, flex-1 so grid + agent panel fill viewport */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex-1 min-h-0 flex flex-col">
        {(mode === 'portfolio' || mode === 'lp') && !fundId ? (
          <Card className="border-2 border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 px-6 text-center">
              <FileSpreadsheet className="h-14 w-14 text-muted-foreground mb-4" />
              <h2 className="text-xl font-semibold mb-2">Add a grid</h2>
              <p className="text-muted-foreground max-w-md mb-6">
                Create a fund to get your portfolio grid. You can then add companies, columns, import CSV, and run valuations.
              </p>
              <div className="flex flex-wrap gap-3 justify-center">
                <Button onClick={() => setShowAddFundModal(true)} size="lg">
                  <Plus className="h-5 w-5 mr-2" />
                  Create Fund
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
        <Card className="border-0 shadow-lg h-full flex flex-col min-h-[520px]">
          <CardContent className="p-0 flex-1 flex flex-col min-h-0">
            <UnifiedMatrix
              mode={mode}
              fundId={fundId}
              initialData={matrixData || undefined}
              onDataChange={setMatrixData}
              availableActions={availableActions}
              showInsights={modeConfig.showInsights}
              showExport={true}
              showQueryBar={modeConfig.showQueryBar}
              useAgentPanel={true}
              toolCallEntries={toolCallEntries}
              onToolCallLog={onToolCallLog}
              onCellEdit={handleCellEdit}
              onServiceResultLog={(rowId, columnId, response) => {
                const meta = response.metadata ?? {};
                setLastValuationWorkings({
                  companyName: matrixData?.rows.find((r) => r.id === rowId)?.companyName ?? '—',
                  method: (meta.method as string) ?? response.action_id ?? 'service',
                  explanation: (meta.explanation as string) ?? '',
                  details: meta.raw_output ?? meta,
                });
                const citationsFromService = ((meta.citations as unknown) as Citation[]) ?? [];
                if (citationsFromService.length) {
                  setCitations((prev) => deduplicateCitations([...prev, ...citationsFromService]));
                }
              }}
              onQuery={handleQuery}
              onCitationsChange={setCitations}
              onRefresh={async () => {
                // Reload portfolio data when refresh is triggered
                if (fundId && mode === 'portfolio') {
                  await loadPortfolioMetrics();
                  // Force reload by clearing and reloading matrix data
                  setMatrixData(null);
                }
              }}
              onRowEdit={(rowId) => {
                // Find company and open edit dialog
                const row = matrixData?.rows.find(r => r.id === rowId);
                if (row?.companyId) {
                  router.push(`/companies/${row.companyId}`);
                }
              }}
              onRowDelete={async (rowId) => {
                const row = matrixData?.rows.find(r => r.id === rowId);
                if (!row?.companyId || !fundId) return;
                
                if (!confirm(`Are you sure you want to delete ${row.companyName || 'this company'} from the portfolio?`)) {
                  return;
                }
                
                try {
                  const response = await fetch(`/api/portfolio/${fundId}/companies/${row.companyId}`, {
                    method: 'DELETE',
                  });
                  
                  if (response.ok) {
                    // Refresh matrix
                    const event = new CustomEvent('refreshMatrix');
                    window.dispatchEvent(event);
                    await loadPortfolioMetrics();
                  } else {
                    alert('Failed to delete company');
                  }
                } catch (error) {
                  console.error('Error deleting company:', error);
                  alert('Failed to delete company');
                }
              }}
              onRowDuplicate={async (rowId) => {
                const row = matrixData?.rows.find(r => r.id === rowId);
                if (!row || !fundId) return;
                
                // Create a copy with modified name
                const newName = `${row.companyName || 'Company'} (Copy)`;
                try {
                  await addCompanyToMatrix({
                    name: newName,
                    fundId,
                    sector: row.cells.sector?.value || '',
                    stage: row.cells.stage?.value || '',
                    investmentAmount: row.cells.invested?.value || 0,
                    ownershipPercentage: row.cells.ownership?.value ? (row.cells.ownership.value * 100) : 0,
                    investmentDate: new Date().toISOString().split('T')[0],
                    currentArr: row.cells.arr?.value || 0,
                    valuation: row.cells.valuation?.value || 0,
                  });
                  
                  // Refresh matrix
                  const event = new CustomEvent('refreshMatrix');
                  window.dispatchEvent(event);
                  await loadPortfolioMetrics();
                } catch (error) {
                  console.error('Error duplicating company:', error);
                  alert('Failed to duplicate company');
                }
              }}
              onUploadDocument={(rowId) => {
                const row = matrixData?.rows.find(r => r.id === rowId);
                if (row?.companyId) {
                  router.push(`/documents?companyId=${row.companyId}&fundId=${fundId}`);
                }
              }}
            />
          </CardContent>
        </Card>
        )}

        </div>
      </div>
    </div>
  );
}
