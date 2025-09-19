'use client';

import React, { useState } from 'react';
import AgentProgressTracker from '@/components/AgentProgressTracker';
import CitationDisplay from '@/components/CitationDisplay';
import AgentChartGenerator from '@/components/AgentChartGenerator';
import { 
  DollarSign, 
  TrendingUp, 
  TrendingDown, 
  AlertCircle, 
  CheckCircle,
  Clock,
  Send,
  Download,
  Upload,
  RefreshCw,
  Calculator,
  Shield,
  Globe,
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  FileText,
  CreditCard,
  Building,
  Activity,
  Sparkles,
  FileSearch,
  ClipboardCheck,
  BarChart3
} from 'lucide-react';

interface AuditLog {
  id: string;
  action: string;
  table_name: string;
  record_id: string;
  old_values?: any;
  new_values?: any;
  user_id?: string;
  ip_address?: string;
  created_at: string;
  risk_score?: number;
}

interface ComplianceItem {
  id: string;
  type: string;
  status: string;
  due_date: string;
  entity: string;
  priority: string;
  regulatory_requirement?: string;
}

interface FundOperationsData {
  general_ledger?: {
    accounts: Array<{
      account_id: string;
      account_name: string;
      account_type: string;
      balance: number;
      currency: string;
      last_activity: string;
      ytd_change: number;
      ytd_change_pct: number;
    }>;
    trial_balance: {
      total_assets: number;
      total_liabilities: number;
      total_equity: number;
      is_balanced: boolean;
    };
    period: string;
  };
  accounts_receivable?: Array<{
    invoice_id: string;
    lp_name: string;
    amount: number;
    currency: string;
    due_date: string;
    days_outstanding: number;
    status: 'pending' | 'overdue' | 'paid';
    type: 'capital_call' | 'management_fee' | 'other';
  }>;
  accounts_payable?: Array<{
    bill_id: string;
    vendor: string;
    amount: number;
    currency: string;
    due_date: string;
    category: string;
    status: 'pending' | 'scheduled' | 'paid';
    approval_status: 'pending' | 'approved' | 'rejected';
  }>;
  capital_calls?: Array<{
    call_id: string;
    fund: string;
    call_date: string;
    due_date: string;
    total_amount: number;
    currency: string;
    purpose: string;
    status: string;
    collection_rate: number;
    lp_responses?: Array<{
      lp_name: string;
      commitment: number;
      called_amount: number;
      paid_amount: number;
      payment_date?: string;
      status: string;
    }>;
  }>;
  distributions?: Array<{
    distribution_id: string;
    fund: string;
    distribution_date: string;
    total_amount: number;
    currency: string;
    type: string;
    source: string;
    waterfall_calculation?: {
      gross_proceeds: number;
      expenses: number;
      carried_interest: number;
      lp_distribution: number;
    };
  }>;
  custody?: {
    accounts: Array<{
      custody_account: string;
      bank: string;
      account_type: string;
      balance: number;
      currency: string;
      holdings?: Array<{
        asset: string;
        quantity: number;
        market_value: number;
        cost_basis: number;
        unrealized_gain: number;
      }>;
    }>;
    total_aum: number;
    cash_balance: number;
    securities_value: number;
  };
  fx_hedging?: {
    exposures: Array<{
      currency_pair: string;
      exposure_amount: number;
      exposure_type: string;
      current_rate: number;
      hedged_amount: number;
      hedge_ratio: number;
      hedging_instruments?: Array<{
        instrument_type: string;
        notional: number;
        strike_rate: number;
        maturity_date: string;
        mtm_value: number;
      }>;
    }>;
    total_fx_exposure: number;
    hedged_percentage: number;
    potential_fx_impact: number;
  };
  cash_management?: {
    bank_accounts: Array<{
      bank: string;
      account_number: string;
      balance: number;
      currency: string;
      type: string;
      last_reconciled: string;
    }>;
    cash_forecast?: {
      next_30_days: {
        expected_inflows: number;
        expected_outflows: number;
        projected_balance: number;
      };
      next_90_days: {
        expected_inflows: number;
        expected_outflows: number;
        projected_balance: number;
      };
    };
  };
  expense_management?: {
    ytd_expenses: number;
    budget: number;
    burn_rate: number;
    top_categories: Array<{
      category: string;
      amount: number;
      pct_of_total: number;
      vs_budget: number;
    }>;
  };
  insights?: {
    ar_aging: string;
    cash_runway: string;
    fx_risk: string;
    efficiency_ratio: string;
    recommendations: string[];
  };
  audit_logs?: AuditLog[];
  compliance_items?: ComplianceItem[];
  audit_summary?: {
    total_events: number;
    anomalies_detected: number;
    compliance_score: number;
    risk_level: string;
  };
}

export default function FundAdminPage() {
  const [activeTab, setActiveTab] = useState<'ledger' | 'ar' | 'ap' | 'capital' | 'distributions' | 'custody' | 'fx' | 'audit' | 'compliance'>('ledger');
  const [loading, setLoading] = useState(false);
  const [fundData, setFundData] = useState<FundOperationsData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | undefined>();
  const [citations, setCitations] = useState<any[]>([]);
  const [charts, setCharts] = useState<any[]>([]);
  const [showCharts, setShowCharts] = useState(false);

  const fetchFundOperations = async (query?: string) => {
    setLoading(true);
    setIsAnalyzing(true);
    setError(null);
    
    try {
      const prompt = query || 'Generate comprehensive fund operations data for a $150M VC fund with current quarter activities including audit logs and compliance items';
      
      // Fetch fund operations data with streaming
      const fundResponse = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          outputFormat: 'fund-operations',
          specificInstructions: 'Generate realistic fund accounting data with general ledger, AR/AP, capital calls, distributions, custody, and FX hedging information. Include actionable insights.'
        })
      });

      if (!fundResponse.ok) {
        throw new Error('Failed to fetch fund operations data');
      }

      // Handle streaming response for fund data
      const reader = fundResponse.body?.getReader();
      const decoder = new TextDecoder();
      let fundResult: any = null;
      let auditResult: any = null;

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const streamData = JSON.parse(dataStr);
              
              switch (streamData.type) {
                case 'progress':
                  console.log('📊 Fund operations progress:', streamData.message);
                  break;
                  
                case 'complete':
                  fundResult = streamData.result;
                  console.log('✅ Fund operations complete');
                  break;
                  
                case 'error':
                  throw new Error(streamData.message);
              }
            } catch (e) {
              console.warn('Could not parse streaming data:', e);
            }
          }
        }
      }
      
      // Fetch audit data with streaming  
      const auditResponse = await fetch('/api/agent/unified-brain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: 'Generate audit logs and compliance items for fund operations',
          outputFormat: 'audit-analysis',
          specificInstructions: 'Generate realistic audit trail data with compliance tracking, risk scores, and regulatory requirements.'
        })
      });

      if (!auditResponse.ok) {
        throw new Error('Failed to fetch audit data');
      }

      // Handle streaming response for audit data
      const auditReader = auditResponse.body?.getReader();
      
      while (auditReader) {
        const { done, value } = await auditReader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const streamData = JSON.parse(dataStr);
              
              switch (streamData.type) {
                case 'progress':
                  console.log('📊 Audit data progress:', streamData.message);
                  break;
                  
                case 'complete':
                  auditResult = streamData.result;
                  console.log('✅ Audit data complete');
                  break;
                  
                case 'error':
                  throw new Error(streamData.message);
              }
            } catch (e) {
              console.warn('Could not parse streaming data:', e);
            }
          }
        }
      }

      const fundData = { success: true, result: fundResult };
      const auditData = { success: true, result: auditResult };
      
      // Track the task if taskId is returned
      if ('taskId' in fundData && fundData.taskId) {
        setActiveTaskId(fundData.taskId as string);
      } else if ('taskId' in auditData && auditData.taskId) {
        setActiveTaskId(auditData.taskId as string);
      }
      
      if (fundData.success && fundData.result) {
        // Combine fund and audit data
        const combinedData = {
          ...fundData.result,
          audit_logs: auditData.result?.audit_logs || [],
          compliance_items: auditData.result?.compliance_items || [],
          audit_summary: auditData.result?.audit_summary || null
        };
        setFundData(combinedData);
        
        // Extract citations and charts if available
        if (fundData.citations) {
          setCitations(fundData.citations);
        }
        if (fundData.charts) {
          setCharts(fundData.charts);
        }
        
        setError(null);
      } else {
        throw new Error('Invalid response from API');
      }
    } catch (err) {
      console.error('Fund operations error:', err);
      setError('Failed to load fund operations data. Please try again.');
    } finally {
      setLoading(false);
      setIsAnalyzing(false);
    }
  };

  // Remove auto-fetch on mount to prevent loading state
  // useEffect(() => {
  //   fetchFundOperations();
  // }, []);

  const formatCurrency = (amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'paid':
      case 'collected':
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'pending':
      case 'scheduled':
        return 'bg-yellow-100 text-yellow-800';
      case 'overdue':
      case 'defaulted':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      fetchFundOperations(searchQuery);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Progress Tracker */}
      {activeTaskId && (
        <AgentProgressTracker 
          taskId={activeTaskId} 
          onClose={() => setActiveTaskId(undefined)}
        />
      )}
      
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-700 to-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-8">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-4xl font-bold text-white tracking-tight flex items-center gap-2">
                  Fund Operations & Compliance
                  <Sparkles className="h-8 w-8 text-yellow-400" />
                </h1>
                <p className="mt-2 text-lg text-gray-100">
                  AI-powered fund administration, accounting, audit, and compliance management
                </p>
              </div>
              <button
                onClick={() => fetchFundOperations()}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-white text-gray-800 rounded-md hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh Data
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* AI Query Interface */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <form onSubmit={handleSearch} className="flex gap-3">
            <input
              type="text"
              placeholder="Ask about fund operations (e.g., 'Show Q1 capital calls status' or 'Analyze FX exposure for EUR positions')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              disabled={loading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
            />
            <button
              type="submit"
              disabled={loading || !searchQuery.trim()}
              className="px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-800 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
              Analyze
            </button>
          </form>
        </div>

        {/* Key Metrics Dashboard */}
        {fundData && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-600">Total AUM</p>
                <Wallet className="h-5 w-5 text-blue-600" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(fundData.custody?.total_aum || 0)}
              </p>
              <p className="text-xs text-green-600 mt-1">
                +12.5% YTD
              </p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-600">Cash Balance</p>
                <DollarSign className="h-5 w-5 text-green-600" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(fundData.custody?.cash_balance || 0)}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                {fundData.insights?.cash_runway || 'Calculating...'}
              </p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-600">Pending AR</p>
                <ArrowUpRight className="h-5 w-5 text-orange-600" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(
                  fundData.accounts_receivable?.filter(ar => ar.status !== 'paid')
                    .reduce((sum, ar) => sum + ar.amount, 0) || 0
                )}
              </p>
              <p className="text-xs text-orange-600 mt-1">
                {fundData.insights?.ar_aging || 'No overdue items'}
              </p>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-600">FX Exposure</p>
                <Globe className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(fundData.fx_hedging?.total_fx_exposure || 0)}
              </p>
              <p className="text-xs text-purple-600 mt-1">
                {formatPercentage(fundData.fx_hedging?.hedged_percentage || 0)} hedged
              </p>
            </div>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 mb-8">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8 px-6">
              {[
                { id: 'ledger', label: 'General Ledger', icon: FileText },
                { id: 'ar', label: 'Accounts Receivable', icon: ArrowUpRight },
                { id: 'ap', label: 'Accounts Payable', icon: ArrowDownRight },
                { id: 'capital', label: 'Capital Calls', icon: Upload },
                { id: 'distributions', label: 'Distributions', icon: Download },
                { id: 'custody', label: 'Custody', icon: Shield },
                { id: 'fx', label: 'FX Hedging', icon: Globe },
                { id: 'audit', label: 'Audit Logs', icon: FileSearch },
                { id: 'compliance', label: 'Compliance', icon: ClipboardCheck },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === tab.id
                      ? 'border-gray-700 text-gray-700'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-600"></div>
              </div>
            ) : error ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-red-900">Error Loading Data</h3>
                    <p className="text-red-700 mt-1">{error}</p>
                  </div>
                </div>
              </div>
            ) : fundData ? (
              <React.Fragment>
                {/* General Ledger Tab */}
                {activeTab === 'ledger' && fundData.general_ledger && (
                  <div>
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        Trial Balance - {fundData.general_ledger.period}
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="bg-blue-50 rounded-lg p-4">
                          <p className="text-sm text-blue-600">Total Assets</p>
                          <p className="text-xl font-bold text-blue-900">
                            {formatCurrency(fundData.general_ledger.trial_balance.total_assets)}
                          </p>
                        </div>
                        <div className="bg-orange-50 rounded-lg p-4">
                          <p className="text-sm text-orange-600">Total Liabilities</p>
                          <p className="text-xl font-bold text-orange-900">
                            {formatCurrency(fundData.general_ledger.trial_balance.total_liabilities)}
                          </p>
                        </div>
                        <div className="bg-green-50 rounded-lg p-4">
                          <p className="text-sm text-green-600">Total Equity</p>
                          <p className="text-xl font-bold text-green-900">
                            {formatCurrency(fundData.general_ledger.trial_balance.total_equity)}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Account
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Type
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Balance
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              YTD Change
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Last Activity
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {fundData.general_ledger.accounts.map((account) => (
                            <tr key={account.account_id} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div>
                                  <div className="text-sm font-medium text-gray-900">
                                    {account.account_name}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {account.account_id}
                                  </div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
                                  {account.account_type}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                                {formatCurrency(account.balance)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right">
                                <div className="flex items-center justify-end gap-1">
                                  {account.ytd_change >= 0 ? (
                                    <TrendingUp className="h-4 w-4 text-green-500" />
                                  ) : (
                                    <TrendingDown className="h-4 w-4 text-red-500" />
                                  )}
                                  <span className={`text-sm font-medium ${
                                    account.ytd_change >= 0 ? 'text-green-600' : 'text-red-600'
                                  }`}>
                                    {formatPercentage(account.ytd_change_pct)}
                                  </span>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                {new Date(account.last_activity).toLocaleDateString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Accounts Receivable Tab */}
                {activeTab === 'ar' && fundData.accounts_receivable && (
                  <div>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">Accounts Receivable</h3>
                      <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2">
                        <Upload className="h-4 w-4" />
                        New Invoice
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Invoice
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              LP/Client
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Type
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Amount
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Due Date
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Days Outstanding
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Status
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {fundData.accounts_receivable.map((ar) => (
                            <tr key={ar.invoice_id} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                {ar.invoice_id}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {ar.lp_name}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                {ar.type.replace('_', ' ')}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                                {formatCurrency(ar.amount)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                {new Date(ar.due_date).toLocaleDateString()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm">
                                <span className={`font-medium ${
                                  ar.days_outstanding > 30 ? 'text-red-600' : 
                                  ar.days_outstanding > 15 ? 'text-yellow-600' : 
                                  'text-gray-600'
                                }`}>
                                  {ar.days_outstanding} days
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(ar.status)}`}>
                                  {ar.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Capital Calls Tab */}
                {activeTab === 'capital' && fundData.capital_calls && (
                  <div>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">Capital Calls</h3>
                      <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2">
                        <Send className="h-4 w-4" />
                        New Capital Call
                      </button>
                    </div>
                    <div className="space-y-6">
                      {fundData.capital_calls.map((call) => (
                        <div key={call.call_id} className="bg-white rounded-lg border border-gray-200 p-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <h4 className="text-lg font-semibold text-gray-900">{call.call_id}</h4>
                              <p className="text-sm text-gray-600">{call.fund} • {call.purpose}</p>
                            </div>
                            <span className={`px-3 py-1 text-sm font-semibold rounded-full ${getStatusColor(call.status)}`}>
                              {call.status}
                            </span>
                          </div>
                          
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                            <div>
                              <p className="text-xs text-gray-500">Call Amount</p>
                              <p className="text-lg font-bold text-gray-900">
                                {formatCurrency(call.total_amount)}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Call Date</p>
                              <p className="text-sm font-medium text-gray-900">
                                {new Date(call.call_date).toLocaleDateString()}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Due Date</p>
                              <p className="text-sm font-medium text-gray-900">
                                {new Date(call.due_date).toLocaleDateString()}
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500">Collection Rate</p>
                              <p className="text-lg font-bold text-green-600">
                                {formatPercentage(call.collection_rate)}
                              </p>
                            </div>
                          </div>

                          {call.lp_responses && call.lp_responses.length > 0 && (
                            <div className="border-t border-gray-200 pt-4">
                              <p className="text-sm font-medium text-gray-700 mb-2">LP Responses</p>
                              <div className="space-y-2">
                                {call.lp_responses.slice(0, 3).map((lp, idx) => (
                                  <div key={idx} className="flex items-center justify-between text-sm">
                                    <span className="text-gray-600">{lp.lp_name}</span>
                                    <div className="flex items-center gap-4">
                                      <span className="text-gray-900 font-medium">
                                        {formatCurrency(lp.called_amount)}
                                      </span>
                                      <span className={`px-2 py-0.5 text-xs rounded-full ${
                                        lp.status === 'paid' ? 'bg-green-100 text-green-700' :
                                        lp.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                                        'bg-red-100 text-red-700'
                                      }`}>
                                        {lp.status}
                                      </span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Distributions Tab */}
                {activeTab === 'distributions' && fundData.distributions && (
                  <div>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">Distributions</h3>
                      <button className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center gap-2">
                        <Download className="h-4 w-4" />
                        New Distribution
                      </button>
                    </div>
                    <div className="space-y-6">
                      {fundData.distributions.map((dist) => (
                        <div key={dist.distribution_id} className="bg-white rounded-lg border border-gray-200 p-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <h4 className="text-lg font-semibold text-gray-900">{dist.distribution_id}</h4>
                              <p className="text-sm text-gray-600">{dist.fund} • {dist.type}</p>
                              <p className="text-xs text-gray-500 mt-1">{dist.source}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-2xl font-bold text-green-600">
                                {formatCurrency(dist.total_amount)}
                              </p>
                              <p className="text-sm text-gray-500">
                                {new Date(dist.distribution_date).toLocaleDateString()}
                              </p>
                            </div>
                          </div>

                          {dist.waterfall_calculation && (
                            <div className="bg-gray-50 rounded-lg p-4">
                              <p className="text-sm font-medium text-gray-700 mb-3">Waterfall Calculation</p>
                              <div className="space-y-2">
                                <div className="flex justify-between text-sm">
                                  <span className="text-gray-600">Gross Proceeds</span>
                                  <span className="font-medium">{formatCurrency(dist.waterfall_calculation.gross_proceeds)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                  <span className="text-gray-600">Expenses</span>
                                  <span className="font-medium text-red-600">-{formatCurrency(dist.waterfall_calculation.expenses)}</span>
                                </div>
                                <div className="flex justify-between text-sm">
                                  <span className="text-gray-600">Carried Interest (20%)</span>
                                  <span className="font-medium text-orange-600">-{formatCurrency(dist.waterfall_calculation.carried_interest)}</span>
                                </div>
                                <div className="border-t border-gray-300 pt-2 mt-2 flex justify-between text-sm font-semibold">
                                  <span className="text-gray-700">LP Distribution</span>
                                  <span className="text-green-600">{formatCurrency(dist.waterfall_calculation.lp_distribution)}</span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* FX Hedging Tab */}
                {activeTab === 'fx' && fundData.fx_hedging && (
                  <div>
                    <div className="mb-6">
                      <h3 className="text-lg font-semibold text-gray-900 mb-4">Foreign Exchange Hedging</h3>
                      
                      {/* FX Summary Cards */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="bg-purple-50 rounded-lg p-4">
                          <p className="text-sm text-purple-600">Total FX Exposure</p>
                          <p className="text-xl font-bold text-purple-900">
                            {formatCurrency(fundData.fx_hedging.total_fx_exposure)}
                          </p>
                        </div>
                        <div className="bg-green-50 rounded-lg p-4">
                          <p className="text-sm text-green-600">Hedged Percentage</p>
                          <p className="text-xl font-bold text-green-900">
                            {formatPercentage(fundData.fx_hedging.hedged_percentage)}
                          </p>
                        </div>
                        <div className="bg-orange-50 rounded-lg p-4">
                          <p className="text-sm text-orange-600">Potential FX Impact</p>
                          <p className="text-xl font-bold text-orange-900">
                            {formatCurrency(fundData.fx_hedging.potential_fx_impact)}
                          </p>
                        </div>
                      </div>

                      {/* FX Exposures */}
                      <div className="space-y-4">
                        {fundData.fx_hedging.exposures.map((exposure, idx) => (
                          <div key={idx} className="bg-white rounded-lg border border-gray-200 p-6">
                            <div className="flex items-start justify-between mb-4">
                              <div>
                                <h4 className="text-lg font-semibold text-gray-900">{exposure.currency_pair}</h4>
                                <p className="text-sm text-gray-600">
                                  {exposure.exposure_type} exposure • Current rate: {exposure.current_rate}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-xl font-bold text-gray-900">
                                  {formatCurrency(exposure.exposure_amount)}
                                </p>
                                <p className="text-sm text-green-600">
                                  {formatPercentage(exposure.hedge_ratio)} hedged
                                </p>
                              </div>
                            </div>

                            {exposure.hedging_instruments && exposure.hedging_instruments.length > 0 && (
                              <div className="border-t border-gray-200 pt-4">
                                <p className="text-sm font-medium text-gray-700 mb-2">Hedging Instruments</p>
                                <div className="space-y-2">
                                  {exposure.hedging_instruments.map((instrument, iIdx) => (
                                    <div key={iIdx} className="flex items-center justify-between text-sm bg-gray-50 rounded p-2">
                                      <div>
                                        <span className="font-medium text-gray-900">{instrument.instrument_type}</span>
                                        <span className="text-gray-600 ml-2">
                                          Strike: {instrument.strike_rate} • Expires: {new Date(instrument.maturity_date).toLocaleDateString()}
                                        </span>
                                      </div>
                                      <div className="text-right">
                                        <p className="font-medium">{formatCurrency(instrument.notional)}</p>
                                        <p className={`text-xs ${instrument.mtm_value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                          MTM: {formatCurrency(instrument.mtm_value)}
                                        </p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Custody Tab */}
                {activeTab === 'custody' && fundData.custody && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Custody & Holdings</h3>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <div className="bg-blue-50 rounded-lg p-4">
                        <p className="text-sm text-blue-600">Total AUM</p>
                        <p className="text-xl font-bold text-blue-900">
                          {formatCurrency(fundData.custody.total_aum)}
                        </p>
                      </div>
                      <div className="bg-green-50 rounded-lg p-4">
                        <p className="text-sm text-green-600">Cash</p>
                        <p className="text-xl font-bold text-green-900">
                          {formatCurrency(fundData.custody.cash_balance)}
                        </p>
                      </div>
                      <div className="bg-purple-50 rounded-lg p-4">
                        <p className="text-sm text-purple-600">Securities</p>
                        <p className="text-xl font-bold text-purple-900">
                          {formatCurrency(fundData.custody.securities_value)}
                        </p>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {fundData.custody.accounts.map((account) => (
                        <div key={account.custody_account} className="bg-white rounded-lg border border-gray-200 p-6">
                          <div className="flex items-start justify-between mb-4">
                            <div>
                              <h4 className="text-lg font-semibold text-gray-900">{account.bank}</h4>
                              <p className="text-sm text-gray-600">
                                {account.custody_account} • {account.account_type}
                              </p>
                            </div>
                            <p className="text-xl font-bold text-gray-900">
                              {formatCurrency(account.balance)}
                            </p>
                          </div>

                          {account.holdings && account.holdings.length > 0 && (
                            <div className="overflow-x-auto">
                              <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                  <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Asset</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Quantity</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Market Value</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Cost Basis</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Unrealized Gain</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200">
                                  {account.holdings.map((holding, idx) => (
                                    <tr key={idx}>
                                      <td className="px-4 py-2 text-sm font-medium text-gray-900">{holding.asset}</td>
                                      <td className="px-4 py-2 text-sm text-right text-gray-600">{holding.quantity.toLocaleString()}</td>
                                      <td className="px-4 py-2 text-sm text-right font-medium text-gray-900">{formatCurrency(holding.market_value)}</td>
                                      <td className="px-4 py-2 text-sm text-right text-gray-600">{formatCurrency(holding.cost_basis)}</td>
                                      <td className={`px-4 py-2 text-sm text-right font-medium ${
                                        holding.unrealized_gain >= 0 ? 'text-green-600' : 'text-red-600'
                                      }`}>
                                        {formatCurrency(holding.unrealized_gain)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Audit Logs Tab */}
                {activeTab === 'audit' && (
                  <div>
                    <div className="mb-6">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold text-gray-900">System Audit Trail</h3>
                        {fundData?.audit_summary && (
                          <div className="flex items-center gap-4">
                            <div className="text-sm">
                              <span className="text-gray-600">Compliance Score: </span>
                              <span className="font-bold text-green-600">{fundData.audit_summary.compliance_score}%</span>
                            </div>
                            <div className="text-sm">
                              <span className="text-gray-600">Risk Level: </span>
                              <span className={`font-bold ${
                                fundData.audit_summary.risk_level === 'LOW' ? 'text-green-600' :
                                fundData.audit_summary.risk_level === 'MEDIUM' ? 'text-yellow-600' :
                                'text-red-600'
                              }`}>
                                {fundData.audit_summary.risk_level}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Audit Summary Cards */}
                      {fundData?.audit_summary && (
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                          <div className="bg-blue-50 rounded-lg p-4">
                            <p className="text-sm text-blue-600">Total Events</p>
                            <p className="text-xl font-bold text-blue-900">{fundData.audit_summary.total_events}</p>
                          </div>
                          <div className="bg-red-50 rounded-lg p-4">
                            <p className="text-sm text-red-600">Anomalies Detected</p>
                            <p className="text-xl font-bold text-red-900">{fundData.audit_summary.anomalies_detected}</p>
                          </div>
                          <div className="bg-green-50 rounded-lg p-4">
                            <p className="text-sm text-green-600">Compliance Score</p>
                            <p className="text-xl font-bold text-green-900">{fundData.audit_summary.compliance_score}%</p>
                          </div>
                          <div className="bg-yellow-50 rounded-lg p-4">
                            <p className="text-sm text-yellow-600">Risk Level</p>
                            <p className="text-xl font-bold text-yellow-900">{fundData.audit_summary.risk_level}</p>
                          </div>
                        </div>
                      )}

                      {/* Audit Logs Table */}
                      {fundData?.audit_logs && fundData.audit_logs.length > 0 ? (
                        <div className="overflow-x-auto">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Action
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Table
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Record ID
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  User
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  IP Address
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Risk Score
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Timestamp
                                </th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {fundData.audit_logs.map((log) => (
                                <tr key={log.id} className="hover:bg-gray-50">
                                  <td className="px-6 py-4 whitespace-nowrap">
                                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                      log.action === 'INSERT' ? 'bg-green-100 text-green-800' :
                                      log.action === 'UPDATE' ? 'bg-blue-100 text-blue-800' :
                                      log.action === 'DELETE' ? 'bg-red-100 text-red-800' :
                                      'bg-gray-100 text-gray-800'
                                    }`}>
                                      {log.action}
                                    </span>
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                    {log.table_name}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                    {log.record_id}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                    {log.user_id || 'System'}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                    {log.ip_address || 'N/A'}
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="flex items-center">
                                      <div className={`text-sm font-medium ${
                                        (log.risk_score || 0) > 0.7 ? 'text-red-600' :
                                        (log.risk_score || 0) > 0.4 ? 'text-yellow-600' :
                                        'text-green-600'
                                      }`}>
                                        {((log.risk_score || 0) * 100).toFixed(0)}%
                                      </div>
                                    </div>
                                  </td>
                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                    {new Date(log.created_at).toLocaleString()}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="text-center py-8 bg-gray-50 rounded-lg">
                          <FileSearch className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                          <p className="text-gray-600">No audit logs available</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Enhanced Compliance Tab with US & European Compliance */}
                {activeTab === 'compliance' && (
                  <div className="space-y-6">
                    {/* Enhanced Compliance Header with Multiple Actions */}
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">Global Compliance & Regulatory Management (US/UK/EU)</h3>
                      <div className="flex gap-2">
                        <button className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 flex items-center gap-1">
                          <FileText className="h-4 w-4" />
                          US Form ADV
                        </button>
                        <button className="px-3 py-1.5 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700 flex items-center gap-1">
                          <Globe className="h-4 w-4" />
                          EU AIFMD Annex IV
                        </button>
                        <button className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 flex items-center gap-1">
                          <Shield className="h-4 w-4" />
                          UK FCA Reports
                        </button>
                        <button className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700 flex items-center gap-1">
                          <ClipboardCheck className="h-4 w-4" />
                          Add Item
                        </button>
                      </div>
                    </div>

                    {/* Regulatory Filing Calendar */}
                    <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-6 border border-indigo-200">
                      <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <Clock className="h-5 w-5 text-indigo-600" />
                        Regulatory Filing Calendar
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-white rounded-lg p-4 border border-indigo-100">
                          <div className="text-xs text-indigo-600 font-medium">Form ADV Annual</div>
                          <div className="text-lg font-bold text-gray-900 mt-1">March 31</div>
                          <div className="text-xs text-gray-500 mt-1">SEC Filing</div>
                        </div>
                        <div className="bg-white rounded-lg p-4 border border-purple-100">
                          <div className="text-xs text-purple-600 font-medium">Form PF</div>
                          <div className="text-lg font-bold text-gray-900 mt-1">Quarterly</div>
                          <div className="text-xs text-gray-500 mt-1">60 days after quarter</div>
                        </div>
                        <div className="bg-white rounded-lg p-4 border border-indigo-100">
                          <div className="text-xs text-indigo-600 font-medium">13F Holdings</div>
                          <div className="text-lg font-bold text-gray-900 mt-1">Feb 14</div>
                          <div className="text-xs text-gray-500 mt-1">45 days after Q4</div>
                        </div>
                        <div className="bg-white rounded-lg p-4 border border-purple-100">
                          <div className="text-xs text-purple-600 font-medium">K-1 Distribution</div>
                          <div className="text-lg font-bold text-gray-900 mt-1">March 15</div>
                          <div className="text-xs text-gray-500 mt-1">IRS Filing</div>
                        </div>
                      </div>
                    </div>

                    {/* US & European Compliance Status */}
                    <div className="bg-white rounded-lg border border-gray-200 p-6">
                      <h4 className="font-semibold text-gray-900 mb-4">🌍 Global Compliance Status</h4>
                      
                      {/* US Compliance Section */}
                      <div className="mb-6">
                        <h5 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
                          🇺🇸 United States - SEC & IRS Compliance
                        </h5>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">Form ADV Part 1 - Registration</div>
                                <div className="text-xs text-gray-500">Last updated: Dec 15, 2023</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">Form ADV Part 2A - Brochure</div>
                                <div className="text-xs text-gray-500">Last updated: Dec 15, 2023</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-yellow-100 rounded-full flex items-center justify-center">
                                <Clock className="h-4 w-4 text-yellow-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">Form ADV Part 2B - Brochure Supplement</div>
                                <div className="text-xs text-gray-500">Update required - Due March 31</div>
                              </div>
                            </div>
                            <button className="text-xs text-yellow-600 hover:text-yellow-700 font-medium">Update</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">Form PF - Quarterly</div>
                                <div className="text-xs text-gray-500">Q3 2024 Filed</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                        </div>
                      </div>
                      
                      {/* European Compliance Section */}
                      <div className="mb-6">
                        <h5 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
                          🇪🇺 European Union - AIFMD & MiFID II
                        </h5>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">AIFMD Annex IV Reporting</div>
                                <div className="text-xs text-gray-500">Q3 2024 Submitted to ESMA</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">MiFID II Transaction Reporting</div>
                                <div className="text-xs text-gray-500">Daily reporting compliant</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">EMIR Trade Repository</div>
                                <div className="text-xs text-gray-500">All derivatives reported</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                        </div>
                      </div>
                      
                      {/* UK Compliance Section */}
                      <div>
                        <h5 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
                          🇬🇧 United Kingdom - FCA & HMRC
                        </h5>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-yellow-100 rounded-full flex items-center justify-center">
                                <Clock className="h-4 w-4 text-yellow-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">FCA Gabriel Returns</div>
                                <div className="text-xs text-gray-500">Due in 15 days</div>
                              </div>
                            </div>
                            <button className="text-xs text-yellow-600 hover:text-yellow-700 font-medium">Prepare</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">UK Stewardship Code</div>
                                <div className="text-xs text-gray-500">2024 Report Filed</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                          
                          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 text-sm">TCFD Climate Disclosures</div>
                                <div className="text-xs text-gray-500">Annual report compliant</div>
                              </div>
                            </div>
                            <button className="text-xs text-blue-600 hover:text-blue-700">View</button>
                          </div>
                        </div>
                    </div>

                    {/* Compliance Summary */}
                    {fundData?.compliance_items && (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div className="bg-green-50 rounded-lg p-4">
                          <p className="text-sm text-green-600">Completed</p>
                          <p className="text-xl font-bold text-green-900">
                            {fundData.compliance_items.filter(item => item.status === 'completed').length}
                          </p>
                        </div>
                        <div className="bg-yellow-50 rounded-lg p-4">
                          <p className="text-sm text-yellow-600">Pending</p>
                          <p className="text-xl font-bold text-yellow-900">
                            {fundData.compliance_items.filter(item => item.status === 'pending').length}
                          </p>
                        </div>
                        <div className="bg-red-50 rounded-lg p-4">
                          <p className="text-sm text-red-600">Overdue</p>
                          <p className="text-xl font-bold text-red-900">
                            {fundData.compliance_items.filter(item => item.status === 'overdue').length}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Compliance Items */}
                    {fundData?.compliance_items && fundData.compliance_items.length > 0 ? (
                      <div className="space-y-4">
                        {fundData.compliance_items.map((item) => (
                          <div key={item.id} className="bg-white rounded-lg border border-gray-200 p-6">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center gap-3 mb-2">
                                  <h4 className="text-lg font-semibold text-gray-900">{item.type}</h4>
                                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                    item.status === 'completed' ? 'bg-green-100 text-green-800' :
                                    item.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                                    'bg-red-100 text-red-800'
                                  }`}>
                                    {item.status}
                                  </span>
                                  <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                    item.priority === 'HIGH' ? 'bg-red-100 text-red-800' :
                                    item.priority === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                                    'bg-gray-100 text-gray-800'
                                  }`}>
                                    {item.priority} Priority
                                  </span>
                                </div>
                                <p className="text-sm text-gray-600 mb-2">Entity: {item.entity}</p>
                                {item.regulatory_requirement && (
                                  <p className="text-sm text-gray-500 mb-2">
                                    Requirement: {item.regulatory_requirement}
                                  </p>
                                )}
                                <div className="flex items-center gap-4 text-sm">
                                  <div className="flex items-center gap-1">
                                    <Clock className="h-4 w-4 text-gray-400" />
                                    <span className="text-gray-600">
                                      Due: {new Date(item.due_date).toLocaleDateString()}
                                    </span>
                                  </div>
                                  {item.status === 'overdue' && (
                                    <span className="text-red-600 font-medium">
                                      {Math.floor((Date.now() - new Date(item.due_date).getTime()) / (1000 * 60 * 60 * 24))} days overdue
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex gap-2">
                                {item.status !== 'completed' && (
                                  <button className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-md hover:bg-green-700">
                                    Mark Complete
                                  </button>
                                )}
                                <button className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-md hover:bg-gray-200">
                                  View Details
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 bg-gray-50 rounded-lg">
                        <ClipboardCheck className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                        <p className="text-gray-600">No compliance items to track</p>
                      </div>
                    )}
                  </div>
                </div>
                )}

                {/* Accounts Payable Tab */}
                {activeTab === 'ap' && fundData.accounts_payable && (
                  <div>
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-gray-900">Accounts Payable</h3>
                      <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2">
                        <CreditCard className="h-4 w-4" />
                        New Bill
                      </button>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Bill ID
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Vendor
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Category
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Amount
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Due Date
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Approval
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {fundData.accounts_payable.map((ap) => (
                            <tr key={ap.bill_id} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                {ap.bill_id}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {ap.vendor}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                {ap.category}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-gray-900">
                                {formatCurrency(ap.amount)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                                {new Date(ap.due_date).toLocaleDateString()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(ap.status)}`}>
                                  {ap.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                  ap.approval_status === 'approved' ? 'bg-green-100 text-green-800' :
                                  ap.approval_status === 'rejected' ? 'bg-red-100 text-red-800' :
                                  'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {ap.approval_status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </React.Fragment>
            ) : (
              <div className="text-center py-12">
                <Calculator className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">No fund operations data available</p>
              </div>
            )}
          </div>
        </div>

        {/* AI Insights Panel */}
        {fundData?.insights && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-5 w-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">AI Insights & Recommendations</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Key Metrics</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">AR Aging</span>
                    <span className="font-medium text-gray-900">{fundData.insights.ar_aging}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Cash Runway</span>
                    <span className="font-medium text-gray-900">{fundData.insights.cash_runway}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">FX Risk</span>
                    <span className="font-medium text-gray-900">{fundData.insights.fx_risk}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">Efficiency Ratio</span>
                    <span className="font-medium text-gray-900">{fundData.insights.efficiency_ratio}</span>
                  </div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Recommendations</h4>
                <div className="space-y-2">
                  {fundData.insights.recommendations.map((rec, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-sm">
                      <CheckCircle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                      <span className="text-gray-700">{rec}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Citations Section */}
        {citations && citations.length > 0 && (
          <div className="mt-6">
            <CitationDisplay citations={citations} />
          </div>
        )}

        {/* Charts Section */}
        {charts && charts.length > 0 && (
          <div className="mt-6 bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center">
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
                  <div key={index} className="bg-gray-50 rounded-lg p-4">
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
        )}
      </div>
    </div>
  );
}