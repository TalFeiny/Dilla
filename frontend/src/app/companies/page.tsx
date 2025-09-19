'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Building2, TrendingUp, Users, Filter } from 'lucide-react';
import Link from 'next/link';

interface Company {
  id: string;
  name: string;
  sector: string;
  status: string;
  current_arr_usd: number | null;
  current_mrr_usd: number | null;
  revenue_growth_monthly_pct: number | null;
  revenue_growth_annual_pct: number | null;
  burn_rate_monthly_usd: number | null;
  runway_months: number | null;
  total_invested_usd: number | null;
  fund_id: string | null;
  location: {
    geography: string;
    amount_raised_usd: number;
    comparable_company: string | null;
    comparable_multiple_bps: number | null;
    comparable_growth_rate_pct: number | null;
  } | null;
  amount_raised: number | null;
  thesis_match_score: number | null;
  has_pwerm_model: boolean;
  pwerm_scenarios_count: number;
  funnel_status: string;
  organization_id: string;
  website: string | null;
  revenue_model: string | null;
  kpi_framework: string | null;
  current_option_pool_bps: number | null;
  round_size: number | null;
  quarter_raised: string | null;
  recommendation_reason: any;
  added_to_watchlist_at: string | null;
  watchlist_priority: string;
  term_sheet_sent_at: string | null;
  term_sheet_status: string | null;
  term_sheet_expiry_date: string | null;
  first_investment_date: string | null;
  latest_investment_date: string | null;
  ownership_percentage: number | null;
  exit_date: string | null;
  exit_type: string | null;
  exit_value_usd: number | null;
  exit_multiple: number | null;
  customer_segment_enterprise_pct: number;
  customer_segment_midmarket_pct: number;
  customer_segment_sme_pct: number;
  latest_update: string | null;
  latest_update_date: string | null;
  update_frequency_days: number;
  latest_pwerm_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [filteredCompanies, setFilteredCompanies] = useState<Company[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [growthFilter, setGrowthFilter] = useState('any');
  const [thesisFilter, setThesisFilter] = useState('any');
  const [isLoading, setIsLoading] = useState(true);
  const [displayLimit, setDisplayLimit] = useState(50); // Start with 50 for faster initial load

  const sectors = [
    'AI', 'Adtech', 'B2B Fintech', 'B2C Fintech', 'B2C', 'Capital Markets',
    'Climate Deep', 'Climate Software', 'Crypto', 'Cyber', 'Deep', 'Dev Tool',
    'E-com', 'Edtech', 'Fintech', 'HR', 'Health', 'Insurtech', 'Marketplace',
    'Renewables', 'SaaS', 'Supply-Chain', 'Technology', 'Travel'
  ];

  const statuses = ['prospect', 'active', 'inactive', 'exited'];

  useEffect(() => {
    loadCompanies();
  }, []);

  useEffect(() => {
    filterCompanies();
  }, [companies, searchTerm, sectorFilter, statusFilter, growthFilter, thesisFilter]);

  const loadCompanies = async () => {
    try {
      // Directly call FastAPI backend with increased limit
      const response = await fetch('http://localhost:8000/api/companies/?limit=1000');
      if (response.ok) {
        const data = await response.json();
        setCompanies(data);
        console.log(`Loaded ${data.length} companies`);
      } else {
        console.error('Failed to fetch companies:', response.status);
      }
    } catch (error) {
      console.error('Error loading companies:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filterCompanies = () => {
    let filtered = companies;

    if (searchTerm) {
      filtered = filtered.filter(company =>
        company.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (sectorFilter && sectorFilter !== 'all') {
      filtered = filtered.filter(company => company.sector === sectorFilter);
    }

    if (statusFilter && statusFilter !== 'all') {
      filtered = filtered.filter(company => company.status === statusFilter);
    }

    if (growthFilter && growthFilter !== 'any') {
      const minGrowth = parseInt(growthFilter);
      filtered = filtered.filter(company => 
        company.revenue_growth_annual_pct && company.revenue_growth_annual_pct >= minGrowth
      );
    }

    if (thesisFilter && thesisFilter !== 'any') {
      const minThesis = parseInt(thesisFilter);
      filtered = filtered.filter(company => 
        company.thesis_match_score && company.thesis_match_score >= minThesis
      );
    }

    setFilteredCompanies(filtered);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'prospect': return 'bg-blue-100 text-blue-800';
      case 'inactive': return 'bg-gray-100 text-gray-800';
      case 'exited': return 'bg-purple-100 text-purple-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getSectorColor = (sector: string) => {
    const colors = [
      'bg-red-100 text-red-800', 'bg-blue-100 text-blue-800', 'bg-green-100 text-green-800',
      'bg-yellow-100 text-yellow-800', 'bg-purple-100 text-purple-800', 'bg-pink-100 text-pink-800',
      'bg-indigo-100 text-indigo-800', 'bg-orange-100 text-orange-800'
    ];
    return colors[sectors.indexOf(sector) % colors.length];
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  const displayedCompanies = filteredCompanies.slice(0, displayLimit);
  const hasMoreCompanies = filteredCompanies.length > displayLimit;

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Companies</h1>
          <p className="text-gray-600">Manage and analyze your portfolio companies</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Building2 className="w-4 h-4 mr-2" />
            Add Company
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="w-5 h-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            <div>
              <label className="text-sm font-medium mb-2 block text-gray-700">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search companies..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block text-gray-700">Sector</label>
              <Select value={sectorFilter} onValueChange={setSectorFilter}>
                <SelectTrigger className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 bg-white">
                  <SelectValue placeholder="All sectors" className="text-gray-600" />
                </SelectTrigger>
                <SelectContent className="max-h-60 bg-white border-gray-200">
                  <SelectItem value="all" className="text-gray-600">All sectors</SelectItem>
                  {sectors.map(sector => (
                    <SelectItem key={sector} value={sector} className="text-gray-700 hover:bg-gray-50">
                      {sector}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block text-gray-700">Status</label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 bg-white">
                  <SelectValue placeholder="All statuses" className="text-gray-600" />
                </SelectTrigger>
                <SelectContent className="max-h-60 bg-white border-gray-200">
                  <SelectItem value="all" className="text-gray-600">All statuses</SelectItem>
                  {statuses.map(status => (
                    <SelectItem key={status} value={status} className="text-gray-700 hover:bg-gray-50">
                      {status}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block text-gray-700">Min Growth %</label>
              <Select value={growthFilter} onValueChange={setGrowthFilter}>
                <SelectTrigger className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 bg-white">
                  <SelectValue placeholder="Any growth" className="text-gray-600" />
                </SelectTrigger>
                <SelectContent className="max-h-60 bg-white border-gray-200">
                  <SelectItem value="any" className="text-gray-600">Any growth</SelectItem>
                  <SelectItem value="25" className="text-gray-700">25%+</SelectItem>
                  <SelectItem value="50" className="text-gray-700">50%+</SelectItem>
                  <SelectItem value="100" className="text-gray-700">100%+</SelectItem>
                  <SelectItem value="200" className="text-gray-700">200%+</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block text-gray-700">Min Thesis %</label>
              <Select value={thesisFilter} onValueChange={setThesisFilter}>
                <SelectTrigger className="border-gray-300 focus:border-blue-500 focus:ring-blue-500 bg-white">
                  <SelectValue placeholder="Any thesis" className="text-gray-600" />
                </SelectTrigger>
                <SelectContent className="max-h-60 bg-white border-gray-200">
                  <SelectItem value="any" className="text-gray-600">Any thesis</SelectItem>
                  <SelectItem value="50" className="text-gray-700">50%+</SelectItem>
                  <SelectItem value="70" className="text-gray-700">70%+</SelectItem>
                  <SelectItem value="80" className="text-gray-700">80%+</SelectItem>
                  <SelectItem value="90" className="text-gray-700">90%+</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button 
                variant="outline" 
                onClick={() => {
                  setSearchTerm('');
                  setSectorFilter('all');
                  setStatusFilter('all');
                  setGrowthFilter('any');
                  setThesisFilter('any');
                }}
                className="w-full border-gray-300 hover:bg-gray-50"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center">
              <Building2 className="h-8 w-8 text-blue-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Total Companies</p>
                <p className="text-2xl font-bold">{filteredCompanies.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-green-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">High Growth (&gt;50% YoY)</p>
                <p className="text-2xl font-bold">
                  {filteredCompanies.filter(c => c.revenue_growth_annual_pct && c.revenue_growth_annual_pct > 50).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center">
              <Users className="h-8 w-8 text-purple-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">PWERM Models</p>
                <p className="text-2xl font-bold">
                  {filteredCompanies.filter(c => c.has_pwerm_model).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center">
              <Building2 className="h-8 w-8 text-orange-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">High Thesis Match (&gt;70%)</p>
                <p className="text-2xl font-bold">
                  {filteredCompanies.filter(c => c.thesis_match_score && c.thesis_match_score > 70).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Companies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {displayedCompanies.map((company) => (
          <Link key={company.id} href={`/companies/${company.id}`}>
            <Card className="hover:shadow-lg transition-shadow cursor-pointer border-gray-200">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <CardTitle className="text-lg font-semibold text-gray-900 mb-2">
                      {company.name}
                    </CardTitle>
                    <div className="flex flex-wrap gap-2">
                      <Badge className={getSectorColor(company.sector)}>
                        {company.sector}
                      </Badge>
                      <Badge className={getStatusColor(company.status)}>
                        {company.status}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {/* Revenue Metrics */}
                  {company.current_arr_usd && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">ARR:</span>
                      <span className="text-sm font-medium">
                        ${((company.current_arr_usd || 0) / 1000000).toFixed(1)}M
                      </span>
                    </div>
                  )}
                  {company.current_mrr_usd && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">MRR:</span>
                      <span className="text-sm font-medium">
                        ${((company.current_mrr_usd || 0) / 1000).toFixed(0)}K
                      </span>
                    </div>
                  )}
                  
                  {/* Growth Metrics */}
                  {company.revenue_growth_annual_pct && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">YoY Growth:</span>
                      <span className={`text-sm font-medium ${company.revenue_growth_annual_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {company.revenue_growth_annual_pct > 0 ? '+' : ''}{(company.revenue_growth_annual_pct || 0).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {company.revenue_growth_monthly_pct && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">MoM Growth:</span>
                      <span className={`text-sm font-medium ${company.revenue_growth_monthly_pct > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {company.revenue_growth_monthly_pct > 0 ? '+' : ''}{(company.revenue_growth_monthly_pct || 0).toFixed(1)}%
                      </span>
                    </div>
                  )}
                  
                  {/* Financial Metrics */}
                  {company.burn_rate_monthly_usd && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Burn Rate:</span>
                      <span className="text-sm font-medium text-red-600">
                        ${((company.burn_rate_monthly_usd || 0) / 1000).toFixed(0)}K/mo
                      </span>
                    </div>
                  )}
                  {company.runway_months && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Runway:</span>
                      <span className="text-sm font-medium">
                        {(company.runway_months || 0).toFixed(1)} months
                      </span>
                    </div>
                  )}
                  
                  {/* Investment Metrics */}
                  {company.total_invested_usd && company.total_invested_usd > 0 && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Invested:</span>
                      <span className="text-sm font-medium">
                        ${((company.total_invested_usd || 0) / 1000000).toFixed(1)}M
                      </span>
                    </div>
                  )}
                  {company.amount_raised && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Total Raised:</span>
                      <span className="text-sm font-medium">
                        ${((company.amount_raised || 0) / 1000000).toFixed(1)}M
                      </span>
                    </div>
                  )}
                  {company.quarter_raised && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Funding Date:</span>
                      <span className="text-sm font-medium text-blue-600">
                        {company.quarter_raised}
                      </span>
                    </div>
                  )}
                  
                  {/* Comparable Metrics */}
                  {company.location?.comparable_company && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Comparable:</span>
                      <span className="text-sm font-medium text-blue-600">
                        {company.location.comparable_company}
                      </span>
                    </div>
                  )}
                  {company.location?.comparable_multiple_bps && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Multiple:</span>
                      <span className="text-sm font-medium">
                        {((company.location?.comparable_multiple_bps || 0) / 100).toFixed(1)}x
                      </span>
                    </div>
                  )}
                  
                  {/* Thesis Match */}
                  {company.thesis_match_score && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Thesis Match:</span>
                      <span className={`text-sm font-medium ${company.thesis_match_score > 70 ? 'text-green-600' : company.thesis_match_score > 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {(company.thesis_match_score || 0).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  
                  {/* PWERM Model */}
                  {company.has_pwerm_model && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">PWERM Scenarios:</span>
                      <span className="text-sm font-medium text-purple-600">
                        {company.pwerm_scenarios_count}
                      </span>
                    </div>
                  )}
                  
                  {/* Portfolio Status */}
                  {company.fund_id && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">In Portfolio:</span>
                      <span className="text-sm font-medium text-green-600">Yes</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Load More Button */}
      {hasMoreCompanies && (
        <div className="flex justify-center mb-6">
          <Button 
            onClick={() => setDisplayLimit(prev => prev + 100)}
            variant="outline"
            className="px-8 py-2"
          >
            Load More Companies ({displayedCompanies.length} of {filteredCompanies.length})
          </Button>
        </div>
      )}

      {filteredCompanies.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <p className="text-gray-500">No companies found matching your filters.</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}