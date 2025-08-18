'use client';

import React, { useState, useEffect } from 'react';
import supabase from '@/lib/supabase';

interface LP {
  id: string;
  organization_id: string;
  name: string;
  lp_type: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  relationship_start_date: string;
  investment_capacity_usd: number;
  investment_focus: any; // jsonb field
  lpc_member: boolean;
  lpc_role: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function LPsPage() {
  const [lps, setLps] = useState<LP[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Fetch LPs from database
  const fetchLPs = async () => {
    try {
      // Fetch from 'limited_partners' table (primary table)
      let { data, error } = await supabase
        .from('limited_partners')
        .select('*')
        .order('name', { ascending: true });

      // If 'limited_partners' table doesn't exist, try 'lps' table as fallback
      if (error && error.message.includes('relation "limited_partners" does not exist')) {
        console.log('limited_partners table not found, trying lps table...');
        const result = await supabase
          .from('lps')
          .select('*')
          .order('name', { ascending: true });
        data = result.data;
        error = result.error;
      }

      // If still no table, show empty state with instructions
      if (error) {
        console.error('Error fetching LPs:', error);
        setLps([]);
      } else {
        setLps(data || []);
      }
    } catch (error) {
      console.error('Error fetching LPs:', error);
      setLps([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLPs();
  }, []);

  // Filter and sort LPs
  const filteredAndSortedLPs = React.useMemo(() => {
    let filtered = lps.filter(lp => {
      const matchesSearch = lp.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           lp.contact_email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           lp.contact_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || lp.status === statusFilter;
      const matchesType = typeFilter === 'all' || lp.lp_type === typeFilter;
      
      return matchesSearch && matchesStatus && matchesType;
    });

    // Sort
    filtered.sort((a, b) => {
      let aValue: any = a[sortBy as keyof LP];
      let bValue: any = b[sortBy as keyof LP];
      
      if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }
      
      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [lps, searchTerm, statusFilter, typeFilter, sortBy, sortOrder]);

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

  const formatNumber = (value: number) => {
    return value.toFixed(2);
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'inactive': return 'bg-gray-100 text-gray-800';
      case 'prospect': return 'bg-blue-100 text-blue-800';
      case 'exited': return 'bg-purple-100 text-purple-800';
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'suspended': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getTypeColor = (type: string) => {
    if (!type) return 'bg-gray-100 text-gray-600'; // Uncategorized
    switch (type.toLowerCase()) {
      case 'institution': return 'bg-blue-100 text-blue-800';
      case 'individual': return 'bg-green-100 text-green-800';
      case 'family_office': return 'bg-purple-100 text-purple-800';
      case 'sovereign_wealth': return 'bg-yellow-100 text-yellow-800';
      case 'pension_fund': return 'bg-indigo-100 text-indigo-800';
      case 'endowment': return 'bg-pink-100 text-pink-800';
      case 'foundation': return 'bg-orange-100 text-orange-800';
      case 'corporate': return 'bg-teal-100 text-teal-800';
      case 'government': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };



  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with gradient */}
      <div className="bg-gradient-to-r from-gray-700 via-gray-800 to-gray-900 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-8">
            <h1 className="text-4xl font-bold text-white tracking-tight">Limited Partners</h1>
            <p className="mt-2 text-lg text-gray-100">Manage and track your LP relationships and investments</p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Total LPs</p>
            <p className="text-2xl font-bold text-gray-900">{lps.length}</p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Total Investment Capacity</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(lps.reduce((sum, lp) => sum + (lp.investment_capacity_usd || 0), 0))}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">Active LPs</p>
            <p className="text-2xl font-bold text-gray-900">
              {lps.filter(lp => lp.status?.toLowerCase() === 'active').length}
            </p>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <p className="text-sm font-medium text-gray-600">LPC Members</p>
            <p className="text-2xl font-bold text-gray-900">
              {lps.filter(lp => lp.lpc_member).length}
            </p>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
              <input
                type="text"
                placeholder="Search by name, email, or contact..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="prospect">Prospect</option>
                <option value="exited">Exited</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Type</label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="all">All Types</option>
                <option value="individual">Individual</option>
                <option value="institution">Institution</option>
                <option value="family_office">Family Office</option>
                <option value="sovereign_wealth">Sovereign Wealth</option>
                <option value="pension_fund">Pension Fund</option>
                <option value="endowment">Endowment</option>
                <option value="foundation">Foundation</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Sort By</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="name">Name</option>
                <option value="investment_capacity_usd">Investment Capacity</option>
                <option value="relationship_start_date">Relationship Start</option>
                <option value="contact_name">Contact Name</option>
                <option value="lp_type">Type</option>
                <option value="status">Status</option>
              </select>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              {sortOrder === 'asc' ? '↑ Ascending' : '↓ Descending'}
            </button>
          </div>
        </div>

        {/* LPs Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">LP Directory</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LP Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Investment Capacity</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Relationship Start</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LPC Member</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contact</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredAndSortedLPs.map((lp) => (
                  <tr key={lp.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{lp.name}</div>
                        <div className="text-sm text-gray-500">
                          {lp.investment_focus?.industry || 'No industry specified'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(lp.lp_type)}`}>
                        {lp.lp_type ? lp.lp_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Uncategorized'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(lp.status)}`}>
                        {lp.status?.charAt(0).toUpperCase() + lp.status?.slice(1) || 'N/A'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {lp.investment_capacity_usd ? formatCurrency(lp.investment_capacity_usd) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {lp.relationship_start_date ? new Date(lp.relationship_start_date).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${lp.lpc_member ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                        {lp.lpc_member ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div>
                        <div className="font-medium">
                          {lp.contact_name || 'No contact name'}
                        </div>
                        <div className="text-gray-500">
                          {lp.investment_focus?.linkedin_contacts?.length > 0 ? (
                            <span className="text-blue-600">
                              {lp.investment_focus.linkedin_contacts.length} LinkedIn contact(s)
                            </span>
                          ) : (
                            'No LinkedIn contacts'
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {filteredAndSortedLPs.length === 0 && (
            <div className="text-center py-12">
              {lps.length === 0 ? (
                <div>
                  <p className="text-gray-500 mb-4">No LP data found.</p>
                  <p className="text-sm text-gray-400">
                    You need to create an 'lps' or 'limited_partners' table in your Supabase database.
                  </p>
                  <div className="mt-4 p-4 bg-blue-50 rounded-lg text-left">
                    <p className="text-sm font-medium text-blue-900 mb-2">Required table structure:</p>
                    <pre className="text-xs text-blue-800 bg-blue-100 p-2 rounded overflow-x-auto">
{`CREATE TABLE limited_partners (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  organization_id UUID,
  name VARCHAR NOT NULL,
  lp_type VARCHAR,
  contact_name VARCHAR,
  contact_email VARCHAR,
  contact_phone VARCHAR,
  relationship_start_date DATE,
  investment_capacity_usd INTEGER,
  investment_focus JSONB,
  lpc_member BOOLEAN DEFAULT FALSE,
  lpc_role VARCHAR,
  status VARCHAR,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);`}
                    </pre>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500">No LPs found matching your criteria.</p>
              )}
            </div>
          )}
        </div>

        {/* Summary Statistics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">LP Distribution</h4>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Active LPs</span>
                <span className="text-sm font-medium text-green-600">
                  {lps.filter(lp => lp.status?.toLowerCase() === 'active').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Prospect LPs</span>
                <span className="text-sm font-medium text-blue-600">
                  {lps.filter(lp => lp.status?.toLowerCase() === 'prospect').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Inactive LPs</span>
                <span className="text-sm font-medium text-gray-600">
                  {lps.filter(lp => lp.status?.toLowerCase() === 'inactive').length}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">Type Distribution</h4>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Institutional</span>
                <span className="text-sm font-medium text-blue-600">
                  {lps.filter(lp => lp.lp_type?.toLowerCase() === 'institution').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Family Offices</span>
                <span className="text-sm font-medium text-purple-600">
                  {lps.filter(lp => lp.lp_type?.toLowerCase() === 'family_office').length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Individuals</span>
                <span className="text-sm font-medium text-green-600">
                  {lps.filter(lp => lp.lp_type?.toLowerCase() === 'individual').length}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">Investment Capacity</h4>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Total Capacity</span>
                <span className="text-sm font-medium text-gray-900">
                  {formatCurrency(lps.reduce((sum, lp) => sum + (lp.investment_capacity_usd || 0), 0))}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Average Capacity</span>
                <span className="text-sm font-medium text-gray-900">
                  {lps.length > 0 
                    ? formatCurrency(lps.reduce((sum, lp) => sum + (lp.investment_capacity_usd || 0), 0) / lps.length)
                    : '-'
                  }
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">LPC Members</span>
                <span className="text-sm font-medium text-blue-600">
                  {lps.filter(lp => lp.lpc_member).length}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 