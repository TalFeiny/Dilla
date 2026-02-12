'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { GraduationCap, Plus, Trash2, X, Sparkles, Search, Calculator, Loader2 } from 'lucide-react';
import { UnifiedMatrix, MatrixData } from '@/components/matrix/UnifiedMatrix';
import { buildMatrixDataFromPortfolioCompanies, type PortfolioCompanyForMatrix } from '@/lib/matrix/portfolio-matrix-builder';
import { getAvailableActions, type CellAction } from '@/lib/matrix/cell-action-registry';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Line } from 'recharts';
import { format, addMonths } from 'date-fns';
import { parseCurrencyInput } from '@/lib/matrix/cell-formatters';
import { updateMatrixCell } from '@/lib/matrix/matrix-api-service';

// Helper function to format currency with clear units
function formatCurrency(value: number | null | undefined, showUnits: boolean = true): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  
  const absValue = Math.abs(value);
  
  if (absValue >= 1000000) {
    // Show in millions
    const millions = value / 1000000;
    return showUnits ? `$${millions.toFixed(1)}M USD` : `$${millions.toFixed(1)}M`;
  } else if (absValue >= 1000) {
    // Show in thousands
    const thousands = value / 1000;
    return showUnits ? `$${thousands.toFixed(1)}K USD` : `$${thousands.toFixed(1)}K`;
  } else {
    // Show in USD
    return showUnits ? `$${value.toFixed(0)} USD` : `$${value.toFixed(0)}`;
  }
}

// Helper function to safely parse integer
function safeParseInt(value: string | number | null | undefined, defaultValue: number = 0): number {
  if (value === null || value === undefined || value === '') {
    return defaultValue;
  }
  if (typeof value === 'number') {
    return isNaN(value) ? defaultValue : value;
  }
  const parsed = parseInt(String(value), 10);
  return isNaN(parsed) ? defaultValue : parsed;
}

// Helper function to safely parse float
function safeParseFloat(value: string | number | null | undefined, defaultValue: number = 0): number {
  if (value === null || value === undefined || value === '') {
    return defaultValue;
  }
  if (typeof value === 'number') {
    return isNaN(value) ? defaultValue : value;
  }
  const parsed = parseFloat(String(value));
  return isNaN(parsed) ? defaultValue : parsed;
}

interface PortfolioCompany {
  id: string;
  name: string;
  sector: string;
  stage: string;
  investmentAmount: number;
  ownershipPercentage: number;
  currentArr: number;
  valuation: number;
  investmentDate: string;
  exitDate?: string;
  exitValue?: number;
  exitMultiple?: number;
  fundId: string;
  // Calculated fields
  individualIrr?: number;
  individualMultiple?: number;
  individualReturn?: number;
  // Portfolio report fields
  cashInBank?: number;
  investmentLead?: string;
  lastContacted?: string;
  burnRate?: number;
  runwayMonths?: number;
  grossMargin?: number;
  cashUpdatedAt?: string;
  burnRateUpdatedAt?: string;
  runwayUpdatedAt?: string;
  revenueUpdatedAt?: string;
  grossMarginUpdatedAt?: string;
}

interface Portfolio {
  id: string;
  name: string;
  fundSize: number;
  totalInvested: number;
  totalValuation: number;
  companies: PortfolioCompany[];
}

interface NewPortfolio {
  name: string;
  fundSize: number;
  targetMultiple: number;
  vintageYear: number;
  fundType: string;
  sectors: string[];
  strategy: string;
  deploymentPeriod: number;
  harvestPeriod: number;
}

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>('');
  const [availableCompanies, setAvailableCompanies] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [showAddFundModal, setShowAddFundModal] = useState(false);
  const [showSimulationModal, setShowSimulationModal] = useState(false);
  const [selectedPortfolioForSimulation, setSelectedPortfolioForSimulation] = useState<Portfolio | null>(null);
  const [selectedCompanyForEdit, setSelectedCompanyForEdit] = useState<PortfolioCompany | null>(null);
  const [showEditCompanyModal, setShowEditCompanyModal] = useState(false);
  const [deletingPortfolioId, setDeletingPortfolioId] = useState<string | null>(null);
  const [availableActions, setAvailableActions] = useState<CellAction[]>([]);
  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    fundSize: 0,
    targetMultiple: 30000,
    vintageYear: new Date().getFullYear(),
    fundType: 'venture'
  });
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

  const loadPortfolios = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await fetch('/api/portfolio');
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        const errorMessage = errorData.message || errorData.error || `Failed to load portfolios (${response.status})`;
        setError(errorMessage);
        console.error('Error loading portfolios:', errorMessage);
        setPortfolios([]);
        return;
      }
      
      const data = await response.json();
      // Check if response is an error object
      if (data.error) {
        setError(data.message || data.error);
        setPortfolios([]);
      } else {
        // Metrics are now pre-calculated on the server
        setPortfolios(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load portfolios';
      setError(errorMessage);
      console.error('Error loading portfolios:', error);
      setPortfolios([]);
    } finally {
      setIsLoading(false);
      // Notify matrices to refresh so they pick up new companies (add/edit/delete)
      window.dispatchEvent(new CustomEvent('refreshMatrix'));
    }
  };

  useEffect(() => {
    loadPortfolios();
    searchCompanies('');
  }, []);

  useEffect(() => {
    getAvailableActions('portfolio')
      .then(setAvailableActions)
      .catch(() => setAvailableActions([]));
  }, []);

  const searchCompanies = async (query: string) => {
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

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      searchCompanies(searchQuery);
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery]);

  const generateRandomPortfolio = async () => {
    const portfolioName = `Random Portfolio ${new Date().toLocaleDateString()}`;
    const fundSize = Math.floor(Math.random() * 90000000) + 10000000; // 10M to 100M
    
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
    
    // Ensure we have an array of companies
    const companiesArray = Array.isArray(selectedCompanies) ? selectedCompanies : [];
    
    if (companiesArray.length === 0) {
      alert('No companies found to add to portfolio');
      return;
    }

    // Add each company to the portfolio
    console.log(`Adding ${companiesArray.length} companies to portfolio ${portfolioId}`);
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
        console.log(`Successfully added ${company.name} (${successCount}/${companiesArray.length})`);
      } else {
        failCount++;
        const error = await response.text();
        console.error(`Failed to add ${company.name}:`, error);
      }
    }
    
    console.log(`Finished: ${successCount} success, ${failCount} failed out of ${companiesArray.length} total`);
    

    loadPortfolios();
    alert(`Created random portfolio "${portfolioName}" with ${companiesArray.length} companies!`);
  };

  const handleAddPortfolio = async () => {
    // Validate inputs
    if (!newPortfolio.name || newPortfolio.name.trim() === '') {
      setError('Fund name is required');
      return;
    }

    if (!newPortfolio.fundSize || newPortfolio.fundSize <= 0) {
      setError('Fund size must be greater than 0');
      return;
    }

    setError(null);
    try {
      const response = await fetch('/api/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPortfolio)
      });

      if (response.ok) {
        setShowAddFundModal(false);
        setNewPortfolio({
          name: '',
          fundSize: 0,
          targetMultiple: 30000,
          vintageYear: new Date().getFullYear(),
          fundType: 'venture'
        });
        loadPortfolios();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Failed to create fund' }));
        setError(errorData.error || errorData.details?.message || `Failed to create fund (${response.status})`);
      }
    } catch (error) {
      console.error('Error adding portfolio:', error);
      setError(error instanceof Error ? error.message : 'An error occurred while creating the fund. Please try again.');
    }
  };

  const handleAddCompany = async () => {
    if (!selectedPortfolio) {
      alert('Please select a portfolio first');
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

    try {
      const response = await fetch(`/api/portfolio/${selectedPortfolio}/companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCompany)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to add company' }));
        alert(errorData.error || errorData.details?.message || 'Failed to add company');
        return;
      }

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
      loadPortfolios();
    } catch (error) {
      console.error('Error adding company:', error);
      alert('An error occurred while adding the company. Please try again.');
    }
  };

  const handleDeletePortfolio = async (portfolioId: string) => {
    if (!confirm('Are you sure you want to delete this portfolio? This will remove the fund and unlink all associated companies. This action cannot be undone.')) {
      return;
    }

    setDeletingPortfolioId(portfolioId);
    setError(null);

    try {
      console.log('Deleting portfolio:', portfolioId);
      const response = await fetch(`/api/portfolio/${portfolioId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      console.log('Delete response status:', response.status);
      console.log('Delete response headers:', Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        let errorMessage = `Failed to delete portfolio (${response.status})`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorData.message || errorMessage;
          console.error('Delete error data:', errorData);
        } catch (parseError) {
          const errorText = await response.text();
          console.error('Delete error text:', errorText);
          errorMessage = errorText || errorMessage;
        }
        console.error('Delete error:', errorMessage);
        setError(errorMessage);
        alert(`Error deleting portfolio: ${errorMessage}\n\nPlease check:\n1. Supabase connection is configured\n2. You have permission to delete this portfolio\n3. The portfolio ID is valid`);
        return;
      }

      const result = await response.json().catch(() => ({}));
      console.log('Delete successful:', result);
      
      // Reload portfolios
      await loadPortfolios();
      
      if (selectedPortfolio === portfolioId) {
        setSelectedPortfolio('');
      }
      
      // Show success message
      alert('Portfolio deleted successfully!');
    } catch (error) {
      console.error('Error deleting portfolio:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete portfolio';
      setError(errorMessage);
      alert(`Error deleting portfolio: ${errorMessage}\n\nThis may be due to:\n1. Network connection issues\n2. Supabase service not available\n3. Server error`);
    } finally {
      setDeletingPortfolioId(null);
    }
  };

  const handleEditCompany = (company: PortfolioCompany) => {
    setSelectedCompanyForEdit(company);
    setShowEditCompanyModal(true);
  };

  const handleDeleteCompany = async (portfolioId: string, companyId: string) => {
    if (!confirm('Are you sure you want to remove this company from the portfolio?')) {
      return;
    }

    try {
      const response = await fetch(`/api/portfolio/${portfolioId}/companies?companyId=${companyId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Failed to delete company' }));
        alert(errorData.error || errorData.details?.message || 'Failed to delete company');
        return;
      }

      loadPortfolios();
    } catch (error) {
      console.error('Error deleting company:', error);
      alert('An error occurred while deleting the company. Please try again.');
    }
  };

  const handleSaveEditCompany = async () => {
    if (!selectedCompanyForEdit || !selectedCompanyForEdit.fundId) return;

    const toStr = (v: unknown): string | null =>
      v == null ? null : typeof v === 'string' ? v : (typeof v === 'object' && v !== null && !Array.isArray(v)
        ? String((v as { value?: unknown }).value ?? (v as { displayValue?: unknown }).displayValue ?? '').trim() || null
        : String(v));

    try {
      const payload: Record<string, unknown> = {
        total_invested_usd: selectedCompanyForEdit.investmentAmount,
        ownership_percentage: selectedCompanyForEdit.ownershipPercentage,
        first_investment_date: toStr(selectedCompanyForEdit.investmentDate) ?? selectedCompanyForEdit.investmentDate ?? null,
        sector: toStr(selectedCompanyForEdit.sector) ?? selectedCompanyForEdit.sector ?? null,
        investment_lead: toStr(selectedCompanyForEdit.investmentLead) ?? selectedCompanyForEdit.investmentLead ?? null,
        last_contacted_date: toStr(selectedCompanyForEdit.lastContacted) ?? selectedCompanyForEdit.lastContacted ?? null
      };
      const response = await fetch(`/api/portfolio/${selectedCompanyForEdit.fundId}/companies/${selectedCompanyForEdit.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setShowEditCompanyModal(false);
        setSelectedCompanyForEdit(null);
        loadPortfolios();
      }
    } catch (error) {
      console.error('Error updating company:', error);
    }
  };

  const handleEditMatrixCell = async (companyId: string, field: string, value: any) => {
    const portfolio = portfolios.find(p => p.companies.some(c => c.id === companyId));
    if (!portfolio) {
      throw new Error('Portfolio not found');
    }

    // Map matrix column ids to API body keys (snake_case)
    const fieldMap: Record<string, string> = {
      'company': 'name',
      'companyName': 'name',
      'name': 'name',
      'arr': 'current_arr_usd',
      'currentArr': 'current_arr_usd',
      'burnRate': 'burn_rate_monthly_usd',
      'runway': 'runway_months',
      'runwayMonths': 'runway_months',
      'grossMargin': 'gross_margin',
      'totalInvested': 'total_invested_usd',
      'invested': 'total_invested_usd',
      'ownershipPercentage': 'ownership_percentage',
      'ownership': 'ownership_percentage',
      'cashInBank': 'cash_in_bank_usd',
      'sector': 'sector',
      'investmentLead': 'investment_lead',
      'firstInvestmentDate': 'first_investment_date',
      'investmentDate': 'first_investment_date',
      'lastContactedDate': 'last_contacted_date',
      'valuation': 'current_valuation_usd',
      'currentValuation': 'current_valuation_usd',
    };

    const apiField = fieldMap[field] || field;
    // Coerce to primitive so we never send [object Object] or store objects
    const raw = value != null && typeof value === 'object' && !Array.isArray(value)
      ? (value.value ?? value.displayValue ?? value.display_value ?? '')
      : value;
    // Never send id-like value as company name (fixes "companyb16366363" bug)
    const looksLikeId = (v: unknown): boolean => {
      if (v == null) return false;
      const s = String(v).trim();
      return /^company[a-z0-9]+$/i.test(s) || /^[a-f0-9-]{36}$/i.test(s) || /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(s);
    };
    if ((field === 'company' || field === 'companyName' || apiField === 'name') && raw != null && raw !== '' && looksLikeId(raw)) {
      return; // skip update; user should enter a real name
    }

    const currencyFields = ['arr', 'currentArr', 'burnRate', 'totalInvested', 'invested', 'cashInBank'];
    const stringOrDateFields = ['name', 'company', 'companyName', 'sector', 'investmentLead', 'firstInvestmentDate', 'investmentDate', 'lastContactedDate'];
    const numRaw = typeof raw === 'string' ? parseFloat(String(raw).replace(/[^0-9.-]/g, '')) : Number(raw);

    let apiValue: number | string | null;
    if (currencyFields.includes(field) || apiField === 'current_valuation_usd') {
      apiValue = parseCurrencyInput(raw);
    } else if (field === 'runway' || field === 'runwayMonths') {
      apiValue = parseInt(String(raw), 10) || 0;
    } else if (field === 'grossMargin') {
      apiValue = !isNaN(numRaw) ? numRaw : 0;
      if (typeof apiValue === 'number' && apiValue > 1) apiValue = apiValue / 100;
    } else if (field === 'ownership' || field === 'ownershipPercentage') {
      apiValue = !isNaN(numRaw) ? numRaw : 0;
    } else if (stringOrDateFields.includes(field)) {
      apiValue = raw != null ? (typeof raw === 'string' ? raw : String(raw)).trim() : '';
      if (apiValue === '') apiValue = null;
    } else {
      apiValue = typeof raw === 'string' || typeof raw === 'number' ? raw : (raw != null ? String(raw) : null);
    }

    try {
      const body: Record<string, number | string | null> = { [apiField]: apiValue };
      const response = await fetch(`/api/portfolio/${portfolio.id}/companies/${companyId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to update company');
      }

      // Refresh parent totals in background; do not await so a failed refresh never
      // causes the matrix to revert the cell (matrix already has optimistic update).
      loadPortfolios().catch((err) => console.warn('Background portfolio refresh failed:', err));
    } catch (error) {
      console.error('Error updating matrix cell:', error);
      throw error;
    }
  };

  const handleAddFundingRound = async (companyId: string, roundData: any) => {
    const portfolio = portfolios.find(p => p.companies.some(c => c.id === companyId));
    if (!portfolio) {
      throw new Error('Portfolio not found');
    }

    try {
      const response = await fetch(`/api/portfolio/${portfolio.id}/companies/${companyId}/funding-rounds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(roundData)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to add funding round');
      }

      await loadPortfolios();
    } catch (error) {
      console.error('Error adding funding round:', error);
      throw error;
    }
  };

  // Calculate pacing data for charts
  const calculatePacingData = (portfolio: Portfolio) => {
    const companies = portfolio.companies;
    if (companies.length === 0) return [];

    // Find earliest investment date
    let startDate = new Date();
    for (const company of companies) {
      if (company.investmentDate) {
        const date = new Date(company.investmentDate);
        if (date < startDate) {
          startDate = date;
        }
      }
    }

    const months: any[] = [];
    const currentDate = new Date();
    let monthDate = new Date(startDate);
    
    while (monthDate <= currentDate) {
      const monthKey = format(monthDate, 'yyyy-MM');
      const monthCompanies = companies.filter(c => {
        if (!c.investmentDate) return false;
        const invDate = new Date(c.investmentDate);
        return invDate <= monthDate;
      });
      
      months.push({
        month: format(monthDate, 'MMM yyyy'),
        monthKey,
        companies: monthCompanies.length,
        invested: monthCompanies.reduce((sum, c) => sum + (c.investmentAmount || 0), 0)
      });
      
      monthDate = addMonths(monthDate, 1);
    }
    
    return months;
  };

  const [runningScenarios, setRunningScenarios] = useState<string | null>(null);
  const [runningPWERM, setRunningPWERM] = useState<string | null>(null);

  const handleRunScenarios = async (portfolioId: string) => {
    setRunningScenarios(portfolioId);
    try {
      const response = await fetch(`/api/scenarios/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolioId })
      });

      if (response.ok) {
        const data = await response.json();
        alert('Portfolio scenario analysis started! This will analyze different market conditions and exit scenarios.');
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`Failed to start scenarios analysis: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error running scenarios:', error);
      alert(`Error running scenarios analysis: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setRunningScenarios(null);
    }
  };

  const handleRunPWERM = async (portfolioId: string) => {
    setRunningPWERM(portfolioId);
    try {
      const response = await fetch(`/api/pwerm/scenarios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolioId })
      });

      if (response.ok) {
        const data = await response.json();
        const successCount = data.results?.length || 0;
        const errorCount = data.errors?.length || 0;
        alert(`PWERM analysis completed!\n${successCount} companies analyzed successfully${errorCount > 0 ? `\n${errorCount} errors` : ''}`);
        // Reload portfolios to show updated PWERM data
        await loadPortfolios();
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        alert(`Failed to run PWERM analysis: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error running PWERM:', error);
      alert(`Error running PWERM analysis: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setRunningPWERM(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <h1 className="text-3xl font-bold">Portfolio Management</h1>
        <div className="flex flex-wrap gap-2">
          <Button onClick={generateRandomPortfolio} variant="outline">
            <Sparkles className="w-4 h-4 mr-2" />
            Random Portfolio
          </Button>
          <Button onClick={() => setShowAddFundModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Fund
          </Button>
        </div>
      </div>

      {error ? (
        <Alert className="mb-6 border-red-500 bg-red-50">
          <AlertDescription className="text-red-800">
            <div className="flex flex-col gap-2">
              <p className="font-semibold">Error loading portfolios: {error}</p>
              <p className="text-sm">This may be due to a missing Supabase configuration. Please check your environment variables (NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY).</p>
              <Button onClick={loadPortfolios} variant="outline" size="sm" className="w-fit mt-2">
                Retry
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : portfolios.length === 0 ? (
        <Card className="mb-6 border-2 border-dashed">
          <CardContent className="py-12 text-center">
            <GraduationCap className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No portfolios yet</h3>
            <p className="text-gray-600 mb-4">Create your first fund to start managing your portfolio</p>
            <Button onClick={() => setShowAddFundModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Fund
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-8">
          {portfolios.map((portfolio) => (
            <Card key={portfolio.id} className="shadow-lg">
              <CardHeader className="pb-4">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div className="flex-1">
                    <CardTitle className="text-xl mb-2">{portfolio.name}</CardTitle>
                    <CardDescription className="flex flex-wrap gap-2">
                      <span>Fund Size: {formatCurrency(portfolio.fundSize)}</span>
                      <span>•</span>
                      <span>Invested: {formatCurrency(portfolio.totalInvested)}</span>
                      <span>•</span>
                      <span>Current Value: {formatCurrency(portfolio.totalValuation)}</span>
                    </CardDescription>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDeletePortfolio(portfolio.id)}
                    disabled={deletingPortfolioId === portfolio.id}
                  >
                    {deletingPortfolioId === portfolio.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="space-y-6">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Companies ({portfolio.companies.length})</h3>
                      <p className="text-sm text-gray-500 mt-1">Manage your portfolio companies and run analyses</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() => {
                          setSelectedPortfolioForSimulation(portfolio);
                          setShowSimulationModal(true);
                        }}
                        size="sm"
                        variant="outline"
                      >
                        <Calculator className="w-4 h-4 mr-2" />
                        Simulate Outcomes
                      </Button>
                      <Button
                        onClick={() => handleRunScenarios(portfolio.id)}
                        size="sm"
                        variant="outline"
                        disabled={runningScenarios === portfolio.id}
                        className="bg-blue-50 hover:bg-blue-100 text-blue-700 border-blue-300"
                      >
                        {runningScenarios === portfolio.id ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Running...
                          </>
                        ) : (
                          <>
                            <Calculator className="w-4 h-4 mr-2" />
                            Run Scenarios
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={() => handleRunPWERM(portfolio.id)}
                        size="sm"
                        variant="outline"
                        disabled={runningPWERM === portfolio.id}
                        className="bg-purple-50 hover:bg-purple-100 text-purple-700 border-purple-300"
                      >
                        {runningPWERM === portfolio.id ? (
                          <>
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            Running...
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-4 h-4 mr-2" />
                            Run PWERM
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                  
                  {/* Pacing Charts */}
                  {portfolio.companies.length > 0 && (
                    <div className="mb-6 space-y-4">
                      <h4 className="text-sm font-semibold text-gray-700">Pacing Analysis</h4>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="bg-white border border-gray-200 rounded p-3">
                          <h5 className="text-xs font-medium text-gray-600 mb-2">Capital Deployment</h5>
                          <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={calculatePacingData(portfolio)}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                                <XAxis 
                                  dataKey="month" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={60}
                                  stroke="#6b7280" 
                                  fontSize={9}
                                />
                                <YAxis 
                                  tickFormatter={(val) => `$${(val / 1000000).toFixed(1)}M`}
                                  stroke="#6b7280" 
                                  fontSize={9}
                                />
                                <Tooltip />
                                <Area 
                                  type="monotone" 
                                  dataKey="invested" 
                                  stroke="#3B82F6" 
                                  fill="#3B82F6" 
                                  fillOpacity={0.3}
                                />
                              </AreaChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                        <div className="bg-white border border-gray-200 rounded p-3">
                          <h5 className="text-xs font-medium text-gray-600 mb-2">Company Count</h5>
                          <div className="h-48">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={calculatePacingData(portfolio)}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                                <XAxis 
                                  dataKey="month" 
                                  angle={-45}
                                  textAnchor="end"
                                  height={60}
                                  stroke="#6b7280" 
                                  fontSize={9}
                                />
                                <YAxis stroke="#6b7280" fontSize={9} />
                                <Tooltip />
                                <Bar dataKey="companies" fill="#10B981" />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="flex flex-col" style={{ height: 660, minHeight: 660 }} role="region" aria-label="Portfolio matrix">
                  <UnifiedMatrix
                    mode="portfolio"
                    fundId={portfolio.id}
                    initialData={buildMatrixDataFromPortfolioCompanies(portfolio.companies as unknown as PortfolioCompanyForMatrix[], portfolio.id)}
                    availableActions={availableActions}
                    onCellEdit={async (rowId, columnId, value, options) => {
                      if (columnId === 'documents' && options?.metadata?.documents != null) {
                        await updateMatrixCell({
                          companyId: rowId,
                          rowId,
                          columnId: 'documents',
                          newValue: value,
                          fundId: portfolio.id,
                          data_source: options.data_source ?? 'manual',
                          metadata: { documents: options.metadata.documents },
                        });
                        return;
                      }
                      if (options?.sourceDocumentId != null) {
                        await updateMatrixCell({
                          companyId: rowId,
                          rowId,
                          columnId,
                          newValue: value,
                          fundId: portfolio.id,
                          data_source: 'document',
                          sourceDocumentId: options.sourceDocumentId,
                          metadata: { sourceDocumentId: options.sourceDocumentId },
                        });
                        return;
                      }
                      await handleEditMatrixCell(rowId, columnId, value);
                    }}
                    onRefresh={loadPortfolios}
                    showQueryBar={false}
                    showExport={true}
                  />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add Fund Modal */}
      {showAddFundModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md max-h-[90vh] overflow-y-auto">
            <CardHeader className="pb-4">
              <div className="flex justify-between items-center">
                <CardTitle>Add New Fund</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => {
                  setShowAddFundModal(false);
                  setError(null);
                }}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-2">
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <div>
                <Label htmlFor="fundName">Fund Name</Label>
                <Input
                  id="fundName"
                  value={newPortfolio.name}
                  onChange={(e) => {
                    setNewPortfolio({...newPortfolio, name: e.target.value});
                    setError(null);
                  }}
                  placeholder="Enter fund name"
                />
              </div>
              <div>
                <Label htmlFor="fundSize">Fund Size (USD)</Label>
                <Input
                  id="fundSize"
                  type="number"
                  value={newPortfolio.fundSize || ''}
                  onChange={(e) => {
                    setNewPortfolio({...newPortfolio, fundSize: safeParseInt(e.target.value, 0)});
                    setError(null);
                  }}
                  placeholder="Enter fund size in USD"
                />
              </div>
              <div>
                <Label htmlFor="targetMultiple">Target Multiple (bps)</Label>
                <Input
                  id="targetMultiple"
                  type="number"
                  value={newPortfolio.targetMultiple || ''}
                  onChange={(e) => setNewPortfolio({...newPortfolio, targetMultiple: safeParseInt(e.target.value, 30000)})}
                  placeholder="30000"
                />
              </div>
              <div>
                <Label htmlFor="vintageYear">Vintage Year</Label>
                <Input
                  id="vintageYear"
                  type="number"
                  value={newPortfolio.vintageYear || ''}
                  onChange={(e) => setNewPortfolio({...newPortfolio, vintageYear: safeParseInt(e.target.value, new Date().getFullYear())})}
                  placeholder="2024"
                />
              </div>
              <div>
                <Label htmlFor="fundType">Fund Type</Label>
                <Input
                  id="fundType"
                  value={newPortfolio.fundType}
                  onChange={(e) => setNewPortfolio({...newPortfolio, fundType: e.target.value})}
                  placeholder="venture"
                />
              </div>
              <Button onClick={handleAddPortfolio} className="w-full">
                Create Fund
              </Button>
            </CardContent>
          </Card>
        </div>
      )}


      {/* Simulation Modal */}
      {showSimulationModal && selectedPortfolioForSimulation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <Card className="w-full max-w-4xl m-4 max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Portfolio Outcome Simulation</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowSimulationModal(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <CardDescription>
                Simulate ownership dilution and exit scenarios for {selectedPortfolioForSimulation.name}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-purple-50 p-4 rounded-lg">
                  <h4 className="font-semibold text-purple-900 mb-2">Portfolio Stats</h4>
                  <p className="text-sm">Companies: {selectedPortfolioForSimulation.companies.length}</p>
                  <p className="text-sm">Total Invested: {formatCurrency(selectedPortfolioForSimulation.totalInvested)}</p>
                  <p className="text-sm">Current Value: {formatCurrency(selectedPortfolioForSimulation.totalValuation)}</p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-semibold text-blue-900 mb-2">Ownership Analysis</h4>
                  <p className="text-sm">Average Ownership: {(selectedPortfolioForSimulation.companies.reduce((sum, c) => sum + c.ownershipPercentage, 0) / selectedPortfolioForSimulation.companies.length).toFixed(1)}%</p>
                  <p className="text-sm">Max Ownership: {Math.max(...selectedPortfolioForSimulation.companies.map(c => c.ownershipPercentage))}%</p>
                  <p className="text-sm">Min Ownership: {Math.min(...selectedPortfolioForSimulation.companies.map(c => c.ownershipPercentage))}%</p>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-semibold">Exit Scenarios</h4>
                {selectedPortfolioForSimulation.companies.map((company) => {
                  const acquirePrice = company.valuation * (3 + Math.random() * 7); // 3-10x current valuation
                  const ipoPrice = company.valuation * (10 + Math.random() * 20); // 10-30x for IPO
                  const failureReturn = 0;
                  
                  return (
                    <div key={company.id} className="border rounded-lg p-4">
                      <h5 className="font-medium mb-2">{company.name}</h5>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-600">Acquisition (3-10x)</p>
                          <p className="font-bold text-green-600">
                            {formatCurrency((acquirePrice * company.ownershipPercentage / 100))}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(acquirePrice / company.investmentAmount).toFixed(1)}x return
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600">IPO (10-30x)</p>
                          <p className="font-bold text-blue-600">
                            ${((ipoPrice * company.ownershipPercentage / 100)).toLocaleString()}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(ipoPrice / company.investmentAmount).toFixed(1)}x return
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600">Write-off</p>
                          <p className="font-bold text-red-600">$0</p>
                          <p className="text-xs text-gray-500">0x return</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Portfolio Outcomes</h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Conservative (50% fail, 40% acquire, 10% IPO):</span>
                    <span className="font-bold">
                      {(() => {
                        const companies = selectedPortfolioForSimulation.companies;
                        const numFail = Math.floor(companies.length * 0.5);
                        const numAcquire = Math.floor(companies.length * 0.4);
                        const numIPO = companies.length - numFail - numAcquire;
                        
                        let totalReturn = 0;
                        companies.forEach((c, i) => {
                          if (i < numFail) {
                            // Failed companies
                            totalReturn += 0;
                          } else if (i < numFail + numAcquire) {
                            // Acquired companies (5x average)
                            totalReturn += c.investmentAmount * 5;
                          } else {
                            // IPO companies (20x average)
                            totalReturn += c.investmentAmount * 20;
                          }
                        });
                        
                        const multiple = totalReturn / selectedPortfolioForSimulation.totalInvested;
                        return `${multiple.toFixed(1)}x (${formatCurrency(totalReturn, false)})`;
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Optimistic (20% fail, 60% acquire, 20% IPO):</span>
                    <span className="font-bold text-green-600">
                      {(() => {
                        const companies = selectedPortfolioForSimulation.companies;
                        const numFail = Math.floor(companies.length * 0.2);
                        const numAcquire = Math.floor(companies.length * 0.6);
                        const numIPO = companies.length - numFail - numAcquire;
                        
                        let totalReturn = 0;
                        companies.forEach((c, i) => {
                          if (i < numFail) {
                            totalReturn += 0;
                          } else if (i < numFail + numAcquire) {
                            totalReturn += c.investmentAmount * 5;
                          } else {
                            totalReturn += c.investmentAmount * 20;
                          }
                        });
                        
                        const multiple = totalReturn / selectedPortfolioForSimulation.totalInvested;
                        return `${multiple.toFixed(1)}x (${formatCurrency(totalReturn, false)})`;
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
