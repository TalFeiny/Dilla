'use client';

import React, { useState, useEffect } from 'react';
import supabase from '@/lib/supabase';

interface Fund {
  id: string;
  name: string;
  fund_type: string;
  status: string;
  target_size_usd: number;
  committed_capital_usd: number;
  vintage_year: number;
  investment_period_years: number;
  fund_life_years: number;
  management_fee_pct: number;
  carried_interest_pct: number;
  created_at: string;
  updated_at: string;
}

interface FundAccount {
  id: string;
  fund_id: string;
  account_name: string;
  account_type: string;
  balance_usd: number;
  currency: string;
  status: string;
  created_at: string;
}

interface RegulatoryFiling {
  id: string;
  fund_id: string;
  filing_type: string;
  status: string;
  due_date: string;
  filed_date?: string;
  description: string;
  created_at: string;
}

export default function FundAdminPage() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [fundAccounts, setFundAccounts] = useState<FundAccount[]>([]);
  const [regulatoryFilings, setRegulatoryFilings] = useState<RegulatoryFiling[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [fundFilter, setFundFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');

  // Fetch fund data from Supabase
  const fetchFundData = async () => {
    try {
      setLoading(true);
      
      // Fetch funds (if funds table exists)
      let { data: fundsData, error: fundsError } = await supabase
        .from('funds')
        .select('*')
        .order('name', { ascending: true });

      if (fundsError && fundsError.message.includes('relation "funds" does not exist')) {
        console.log('funds table not found, using mock data');
        fundsData = generateMockFunds();
      }

      // Fetch fund accounts (if fund_accounts table exists)
      let { data: accountsData, error: accountsError } = await supabase
        .from('fund_accounts')
        .select('*')
        .order('account_name', { ascending: true });

      if (accountsError && accountsError.message.includes('relation "fund_accounts" does not exist')) {
        console.log('fund_accounts table not found, using mock data');
        accountsData = generateMockFundAccounts();
      }

      // Fetch regulatory filings (if regulatory_filings table exists)
      let { data: filingsData, error: filingsError } = await supabase
        .from('regulatory_filings')
        .select('*')
        .order('due_date', { ascending: true });

      if (filingsError && filingsError.message.includes('relation "regulatory_filings" does not exist')) {
        console.log('regulatory_filings table not found, using mock data');
        filingsData = generateMockRegulatoryFilings();
      }

      setFunds(fundsData || []);
      setFundAccounts(accountsData || []);
      setRegulatoryFilings(filingsData || []);
    } catch (error) {
      console.error('Error fetching fund data:', error);
      setFunds(generateMockFunds());
      setFundAccounts(generateMockFundAccounts());
      setRegulatoryFilings(generateMockRegulatoryFilings());
    } finally {
      setLoading(false);
    }
  };

  // Generate mock funds for demonstration
  const generateMockFunds = (): Fund[] => {
    return [
      {
        id: 'fund_001',
        name: 'Venture Capital Fund I',
        fund_type: 'venture_capital',
        status: 'active',
        target_size_usd: 100000000,
        committed_capital_usd: 85000000,
        vintage_year: 2023,
        investment_period_years: 5,
        fund_life_years: 10,
        management_fee_pct: 2.0,
        carried_interest_pct: 20.0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      {
        id: 'fund_002',
        name: 'Growth Equity Fund II',
        fund_type: 'growth_equity',
        status: 'raising',
        target_size_usd: 200000000,
        committed_capital_usd: 120000000,
        vintage_year: 2024,
        investment_period_years: 4,
        fund_life_years: 8,
        management_fee_pct: 1.5,
        carried_interest_pct: 18.0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      {
        id: 'fund_003',
        name: 'Seed Fund III',
        fund_type: 'seed',
        status: 'closed',
        target_size_usd: 50000000,
        committed_capital_usd: 50000000,
        vintage_year: 2022,
        investment_period_years: 3,
        fund_life_years: 7,
        management_fee_pct: 2.5,
        carried_interest_pct: 25.0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ];
  };

  // Generate mock fund accounts for demonstration
  const generateMockFundAccounts = (): FundAccount[] => {
    return [
      {
        id: 'acc_001',
        fund_id: 'fund_001',
        account_name: 'Main Investment Account',
        account_type: 'investment',
        balance_usd: 45000000,
        currency: 'USD',
        status: 'active',
        created_at: new Date().toISOString()
      },
      {
        id: 'acc_002',
        fund_id: 'fund_001',
        account_name: 'Management Fee Account',
        account_type: 'management_fee',
        balance_usd: 1700000,
        currency: 'USD',
        status: 'active',
        created_at: new Date().toISOString()
      },
      {
        id: 'acc_003',
        fund_id: 'fund_002',
        account_name: 'Capital Account',
        account_type: 'capital',
        balance_usd: 120000000,
        currency: 'USD',
        status: 'active',
        created_at: new Date().toISOString()
      }
    ];
  };

  // Generate mock regulatory filings for demonstration
  const generateMockRegulatoryFilings = (): RegulatoryFiling[] => {
    return [
      {
        id: 'filing_001',
        fund_id: 'fund_001',
        filing_type: 'Form ADV',
        status: 'completed',
        due_date: new Date(Date.now() - 86400000 * 30).toISOString(),
        filed_date: new Date(Date.now() - 86400000 * 30).toISOString(),
        description: 'Annual Form ADV filing for Venture Capital Fund I',
        created_at: new Date().toISOString()
      },
      {
        id: 'filing_002',
        fund_id: 'fund_002',
        filing_type: 'Form D',
        status: 'pending',
        due_date: new Date(Date.now() + 86400000 * 7).toISOString(),
        description: 'Form D filing for Growth Equity Fund II',
        created_at: new Date().toISOString()
      },
      {
        id: 'filing_003',
        fund_id: 'fund_003',
        filing_type: 'Tax Return',
        status: 'overdue',
        due_date: new Date(Date.now() - 86400000 * 14).toISOString(),
        description: 'Annual tax return for Seed Fund III',
        created_at: new Date().toISOString()
      }
    ];
  };

  useEffect(() => {
    fetchFundData();
  }, []);

  // Filter funds
  const filteredFunds = React.useMemo(() => {
    return funds.filter(fund => {
      const matchesSearch = fund.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           fund.fund_type.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || fund.status === statusFilter;
      const matchesType = typeFilter === 'all' || fund.fund_type === typeFilter;
      
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [funds, searchTerm, statusFilter, typeFilter]);

  // Filter fund accounts
  const filteredFundAccounts = React.useMemo(() => {
    return fundAccounts.filter(account => {
      const matchesSearch = account.account_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           account.account_type.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFund = fundFilter === 'all' || account.fund_id === fundFilter;
      
      return matchesSearch && matchesFund;
    });
  }, [fundAccounts, searchTerm, fundFilter]);

  // Filter regulatory filings
  const filteredRegulatoryFilings = React.useMemo(() => {
    return regulatoryFilings.filter(filing => {
      const matchesSearch = filing.filing_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           filing.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFund = fundFilter === 'all' || filing.fund_id === fundFilter;
      const matchesStatus = statusFilter === 'all' || filing.status === statusFilter;
      
      return matchesSearch && matchesFund && matchesStatus;
    });
  }, [regulatoryFilings, searchTerm, fundFilter, statusFilter]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'raising': return 'bg-blue-100 text-blue-800';
      case 'closed': return 'bg-gray-100 text-gray-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'overdue': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'venture_capital': return 'bg-blue-100 text-blue-800';
      case 'growth_equity': return 'bg-green-100 text-green-800';
      case 'seed': return 'bg-gray-100 text-gray-800';
      case 'investment': return 'bg-indigo-100 text-indigo-800';
      case 'management_fee': return 'bg-orange-100 text-orange-800';
      case 'capital': return 'bg-teal-100 text-teal-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with gradient */}
      <div className="bg-gradient-to-r from-gray-700 to-gray-800 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-8">
            <h1 className="text-4xl font-bold text-white tracking-tight">Fund Administration</h1>
            <p className="mt-2 text-lg text-gray-100">Manage fund structures, accounts, and regulatory compliance</p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Total Funds</p>
            <p className="text-2xl font-bold text-gray-900">{funds.length}</p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Total Committed Capital</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(funds.reduce((sum, fund) => sum + fund.committed_capital_usd, 0))}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Active Funds</p>
            <p className="text-2xl font-bold text-gray-900">
              {funds.filter(fund => fund.status === 'active').length}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Pending Filings</p>
            <p className="text-2xl font-bold text-yellow-600">
              {regulatoryFilings.filter(filing => filing.status === 'pending').length}
            </p>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
              <input
                type="text"
                placeholder="Search funds, accounts, or filings..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Fund</label>
              <select
                value={fundFilter}
                onChange={(e) => setFundFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Funds</option>
                {funds.map(fund => (
                  <option key={fund.id} value={fund.id}>{fund.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="raising">Raising</option>
                <option value="closed">Closed</option>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="overdue">Overdue</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-transparent"
              >
                <option value="all">All Types</option>
                <option value="venture_capital">Venture Capital</option>
                <option value="growth_equity">Growth Equity</option>
                <option value="seed">Seed</option>
              </select>
            </div>
          </div>
        </div>

        {/* Funds Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Funds</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fund Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target Size</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Committed</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vintage</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Management Fee</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredFunds.map((fund) => (
                  <tr key={fund.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{fund.name}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getTypeColor(fund.fund_type)}`}>
                        {fund.fund_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(fund.status)}`}>
                        {fund.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(fund.target_size_usd)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(fund.committed_capital_usd)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{fund.vintage_year}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatPercentage(fund.management_fee_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Fund Accounts Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Fund Accounts</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Account Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Balance</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Currency</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredFundAccounts.map((account) => (
                  <tr key={account.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{account.account_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getTypeColor(account.account_type)}`}>
                        {account.account_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{formatCurrency(account.balance_usd)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{account.currency}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(account.status)}`}>
                        {account.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Regulatory Filings Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Regulatory Filings</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filing Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Due Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filed Date</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredRegulatoryFilings.map((filing) => (
                  <tr key={filing.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{filing.filing_type}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(filing.status)}`}>
                        {filing.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{filing.description}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(filing.due_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {filing.filed_date ? new Date(filing.filed_date).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
