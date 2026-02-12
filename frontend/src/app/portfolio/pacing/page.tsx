'use client';

import React, { useState, useEffect, useMemo } from 'react';
import supabase from '@/lib/supabase';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Area, AreaChart, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { format, addMonths, subMonths } from 'date-fns';

interface Company {
  id: string;
  name: string;
  website?: string;
  sector?: string;
  revenue_model?: string;
  current_arr_usd?: number;
  current_mrr_usd?: number;
  revenue_growth_monthly_pct?: number;
  revenue_growth_annual_pct?: number;
  burn_rate_monthly_usd?: number;
  runway_months?: number;
  current_option_pool_bps?: number;
  location?: Record<string, any>;
  status: string;
  created_at: string;
  updated_at: string;
  round_size?: Record<string, any>;
  amount_raised?: Record<string, any>;
  quarter_raised?: any;
  funnel_status: string;
  thesis_match_score?: number;
  recommendation_reason?: Record<string, any>;
  added_to_watchlist_at?: string;
  watchlist_priority?: string;
  term_sheet_sent_at?: string;
  term_sheet_status?: string;
  term_sheet_expiry_date?: string;
  first_investment_date?: string;
  latest_investment_date?: string;
  total_invested_usd?: number;
  ownership_percentage?: number;
  exit_date?: string;
  exit_type?: string;
  exit_value_usd?: number;
  exit_multiple?: number;
  customer_segment_enterprise_pct?: number;
  customer_segment_midmarket_pct?: number;
  customer_segment_sme_pct?: number;
  latest_update?: string;
  latest_update_date?: string;
  update_frequency_days?: number;
  has_pwerm_model?: boolean;
  latest_pwerm_run_at?: string;
  pwerm_scenarios_count?: number;
}

interface Fund {
  id: string;
  name: string;
  startDate: string;
  vintageYear: number; // Year the fund was established
  firstClose: string; // Date of first close
  finalClose: string; // Date of final close
  size: number;
  targetCompanies: number;
  targetOwnership: number;
  color: string;
  // New sophisticated fund parameters
  deploymentPeriodYears: number; // Typically 3-5 years
  fundLifeYears: number; // Typically 10 years
  extensionYears: number; // Typically 2 years possible
  initialManagementFee: number; // e.g., 2.0 for 2%
  managementFeeReduction: number; // e.g., 0.25 for 0.25% per year
  carriedInterest: number; // e.g., 20 for 20%
  preferredReturn: number; // e.g., 8 for 8%
  recyclingRate: number; // e.g., 0.15 for 15% recycling
  reserveRatio: number; // e.g., 0.5 for 50% reserved for follow-ons
  targetCheckSize: number; // Average initial check size
  targetFollowOnMultiple: number; // e.g., 2.0 for 2x initial check in follow-ons
}

interface PacingData {
  month: string;
  funds: {
    [fundId: string]: {
      plannedCompanies: number;
      actualCompanies: number;
      plannedOwnership: number;
      actualOwnership: number;
      plannedInvestment: number;
      actualInvestment: number;
      managementFee?: number;
      deploymentProgress?: number;
    };
  };
}

// Linear regression utility
function linearRegression(x: number[], y: number[]) {
  const n = x.length;
  if (n === 0) return { slope: 0, intercept: 0 };
  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
  const sumXX = x.reduce((sum, xi) => sum + xi * xi, 0);
  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX || 1);
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

// Calculate management fee for a given year in the fund lifecycle
function calculateManagementFee(fund: Fund, yearsSinceStart: number): number {
  const { initialManagementFee, managementFeeReduction, deploymentPeriodYears } = fund;
  
  // During deployment period: full management fee
  if (yearsSinceStart <= deploymentPeriodYears) {
    return initialManagementFee;
  }
  
  // After deployment: reduce by 0.25% per year
  const yearsPostDeployment = yearsSinceStart - deploymentPeriodYears;
  const reducedFee = initialManagementFee - (managementFeeReduction * yearsPostDeployment);
  
  // Minimum fee is typically 1%
  return Math.max(reducedFee, 1.0);
}

// Calculate capital available for deployment (considering reserves and recycling)
function calculateDeployableCapital(fund: Fund): {
  initialDeployment: number;
  reserves: number;
  recyclable: number;
  total: number;
} {
  const { size, reserveRatio, recyclingRate } = fund;
  
  const reserves = size * reserveRatio;
  const initialDeployment = size - reserves;
  const recyclable = size * recyclingRate; // From early exits
  const total = initialDeployment + recyclable;
  
  return { initialDeployment, reserves, recyclable, total };
}

// Calculate deployment curve (J-curve modeling)
function calculateDeploymentCurve(fund: Fund, monthsSinceStart: number): number {
  const { deploymentPeriodYears } = fund;
  const deploymentMonths = deploymentPeriodYears * 12;
  
  if (monthsSinceStart >= deploymentMonths) {
    return 1.0; // Fully deployed
  }
  
  // S-curve deployment: slow start, accelerate, then slow down
  // Using logistic function for realistic deployment curve
  const midpoint = deploymentMonths / 2;
  const steepness = 0.15;
  const progress = 1 / (1 + Math.exp(-steepness * (monthsSinceStart - midpoint)));
  
  return progress;
}

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16', '#F97316'];

export default function FundPacingPage() {
  const [portfolioCompanies, setPortfolioCompanies] = useState<Company[]>([]);
  const [portfolios, setPortfolios] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedChart, setSelectedChart] = useState('deployment');
  const [timeRange, setTimeRange] = useState('all');  // Default to showing full timeline
  const [funds, setFunds] = useState<Fund[]>([]);
  const [pacingData, setPacingData] = useState<PacingData[]>([]);
  const [selectedFunds, setSelectedFunds] = useState<string[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingFund, setEditingFund] = useState<Fund | null>(null);
  const [regressionEnabled, setRegressionEnabled] = useState(true);
  const [regressionSlope, setRegressionSlope] = useState<number | null>(null);
  const [regressionIntercept, setRegressionIntercept] = useState<number | null>(null);
  const [ledgerData, setLedgerData] = useState<any>(null);
  const [loadingLedger, setLoadingLedger] = useState(false);

  // Helper function to map database fund to Fund interface
  const mapDbFundToFund = (dbFund: any, index: number): Fund => {
    return {
      id: dbFund.id,
      name: dbFund.name || `Fund ${index + 1}`,
      startDate: dbFund.start_date || dbFund.first_close || new Date().toISOString().split('T')[0],
      vintageYear: dbFund.vintage_year || new Date(dbFund.start_date || dbFund.first_close || Date.now()).getFullYear(),
      firstClose: dbFund.first_close || dbFund.start_date || new Date().toISOString().split('T')[0],
      finalClose: dbFund.final_close || new Date().toISOString().split('T')[0],
      size: dbFund.fund_size_usd || dbFund.size || 100000000,
      targetCompanies: dbFund.target_companies || 20,
      targetOwnership: dbFund.target_ownership || 15,
      color: dbFund.color || COLORS[index % COLORS.length],
      deploymentPeriodYears: dbFund.deployment_period_years || 4,
      fundLifeYears: dbFund.fund_life_years || 10,
      extensionYears: dbFund.extension_years || 2,
      initialManagementFee: dbFund.initial_management_fee || 2.0,
      managementFeeReduction: dbFund.management_fee_reduction || 0.25,
      carriedInterest: dbFund.carried_interest || 20,
      preferredReturn: dbFund.preferred_return || 8,
      recyclingRate: dbFund.recycling_rate || 0.15,
      reserveRatio: dbFund.reserve_ratio || 0.5,
      targetCheckSize: dbFund.target_check_size || 2500000,
      targetFollowOnMultiple: dbFund.target_follow_on_multiple || 2.0
    };
  };

  // Fetch funds from API
  const fetchFunds = async () => {
    try {
      const response = await fetch('/api/funds');
      if (response.ok) {
        const data = await response.json();
        const fetchedFunds = (data.funds || []).map((f: any, index: number) => mapDbFundToFund(f, index));
        setFunds(fetchedFunds);
        if (fetchedFunds.length > 0 && selectedFunds.length === 0) {
          setSelectedFunds(fetchedFunds.map((f: Fund) => f.id));
        }
      }
    } catch (error) {
      console.error('Error fetching funds:', error);
    }
  };

  // Create a new fund
  const createFund = async (fundData: Partial<Fund>) => {
    try {
      const dbData = {
        name: fundData.name,
        start_date: fundData.startDate,
        vintage_year: fundData.vintageYear,
        first_close: fundData.firstClose,
        final_close: fundData.finalClose,
        fund_size_usd: fundData.size,
        target_companies: fundData.targetCompanies,
        target_ownership: fundData.targetOwnership,
        color: fundData.color || COLORS[funds.length % COLORS.length],
        deployment_period_years: fundData.deploymentPeriodYears,
        fund_life_years: fundData.fundLifeYears,
        extension_years: fundData.extensionYears,
        initial_management_fee: fundData.initialManagementFee,
        management_fee_reduction: fundData.managementFeeReduction,
        carried_interest: fundData.carriedInterest,
        preferred_return: fundData.preferredReturn,
        recycling_rate: fundData.recyclingRate,
        reserve_ratio: fundData.reserveRatio,
        target_check_size: fundData.targetCheckSize,
        target_follow_on_multiple: fundData.targetFollowOnMultiple
      };

      const response = await fetch('/api/funds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'fund', data: dbData })
      });

      if (response.ok) {
        const newFund = await response.json();
        await fetchFunds();
        setShowCreateModal(false);
        return newFund;
      } else {
        throw new Error('Failed to create fund');
      }
    } catch (error) {
      console.error('Error creating fund:', error);
      throw error;
    }
  };

  // Update an existing fund
  const updateFund = async (fundId: string, fundData: Partial<Fund>) => {
    try {
      const dbData: any = {};
      if (fundData.name !== undefined) dbData.name = fundData.name;
      if (fundData.startDate !== undefined) dbData.start_date = fundData.startDate;
      if (fundData.vintageYear !== undefined) dbData.vintage_year = fundData.vintageYear;
      if (fundData.firstClose !== undefined) dbData.first_close = fundData.firstClose;
      if (fundData.finalClose !== undefined) dbData.final_close = fundData.finalClose;
      if (fundData.size !== undefined) dbData.fund_size_usd = fundData.size;
      if (fundData.targetCompanies !== undefined) dbData.target_companies = fundData.targetCompanies;
      if (fundData.targetOwnership !== undefined) dbData.target_ownership = fundData.targetOwnership;
      if (fundData.color !== undefined) dbData.color = fundData.color;
      if (fundData.deploymentPeriodYears !== undefined) dbData.deployment_period_years = fundData.deploymentPeriodYears;
      if (fundData.fundLifeYears !== undefined) dbData.fund_life_years = fundData.fundLifeYears;
      if (fundData.extensionYears !== undefined) dbData.extension_years = fundData.extensionYears;
      if (fundData.initialManagementFee !== undefined) dbData.initial_management_fee = fundData.initialManagementFee;
      if (fundData.managementFeeReduction !== undefined) dbData.management_fee_reduction = fundData.managementFeeReduction;
      if (fundData.carriedInterest !== undefined) dbData.carried_interest = fundData.carriedInterest;
      if (fundData.preferredReturn !== undefined) dbData.preferred_return = fundData.preferredReturn;
      if (fundData.recyclingRate !== undefined) dbData.recycling_rate = fundData.recyclingRate;
      if (fundData.reserveRatio !== undefined) dbData.reserve_ratio = fundData.reserveRatio;
      if (fundData.targetCheckSize !== undefined) dbData.target_check_size = fundData.targetCheckSize;
      if (fundData.targetFollowOnMultiple !== undefined) dbData.target_follow_on_multiple = fundData.targetFollowOnMultiple;

      const response = await fetch(`/api/funds/${fundId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dbData)
      });

      if (response.ok) {
        await fetchFunds();
        setEditingFund(null);
        return await response.json();
      } else {
        throw new Error('Failed to update fund');
      }
    } catch (error) {
      console.error('Error updating fund:', error);
      throw error;
    }
  };

  // Delete a fund
  const deleteFund = async (fundId: string) => {
    try {
      const response = await fetch(`/api/funds/${fundId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        await fetchFunds();
        setSelectedFunds(prev => prev.filter(id => id !== fundId));
      } else {
        throw new Error('Failed to delete fund');
      }
    } catch (error) {
      console.error('Error deleting fund:', error);
      throw error;
    }
  };

  // Fetch portfolios from the portfolio API
  const fetchPortfolios = async () => {
    try {
      const response = await fetch('/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolios(data);
        
        // Auto-select first portfolio if available
        if (data.length > 0 && !selectedPortfolioId) {
          setSelectedPortfolioId(data[0].id);
          
          // Set portfolio companies from selected portfolio
          const selectedPortfolio = data[0];
          setPortfolioCompanies(selectedPortfolio.companies || []);
        }
      }
    } catch (error) {
      console.error('Error fetching portfolios:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch ledger data (revenue time-series)
  const fetchLedgerData = async (fundId?: string) => {
    if (!fundId && selectedFunds.length === 0) return;
    
    setLoadingLedger(true);
    try {
      const fundIdParam = fundId || selectedFunds[0];
      const response = await fetch(`/api/portfolio/ledger?fund_id=${fundIdParam}`);
      if (response.ok) {
        const data = await response.json();
        setLedgerData(data);
      }
    } catch (error) {
      console.error('Error fetching ledger data:', error);
    } finally {
      setLoadingLedger(false);
    }
  };

  useEffect(() => {
    fetchPortfolios();
    fetchFunds();
  }, []);
  
  // Update companies when portfolio selection changes
  useEffect(() => {
    if (selectedPortfolioId && portfolios.length > 0) {
      const selectedPortfolio = portfolios.find(p => p.id === selectedPortfolioId);
      if (selectedPortfolio) {
        setPortfolioCompanies(selectedPortfolio.companies || []);
      }
    }
  }, [selectedPortfolioId, portfolios]);

  useEffect(() => {
    if (portfolioCompanies.length > 0) {
      calculatePacingData();
    }
  }, [portfolioCompanies, funds, selectedFunds]);

  // Fetch ledger data when funds are selected
  useEffect(() => {
    if (selectedFunds.length > 0) {
      fetchLedgerData();
    }
  }, [selectedFunds]);

  const regressionPoints = React.useMemo(() => {
    if (!regressionEnabled) return null;
    
    // Use manual inputs if provided, otherwise calculate
    if (regressionSlope !== null && regressionIntercept !== null) {
      return pacingData.map((_, i) => regressionIntercept + regressionSlope * i);
    }
    
    const points = pacingData
      .map((data, i) => {
        const totalActual = Object.values(data.funds).reduce((sum, fundData) => sum + fundData.actualInvestment, 0);
        return { x: i, y: totalActual };
      })
      .filter(point => point.y > 0);
    if (points.length < 2) return null;
    const x = points.map(p => p.x);
    const y = points.map(p => p.y);
    const { slope, intercept } = linearRegression(x, y);
    return pacingData.map((_, i) => intercept + slope * i);
  }, [pacingData, regressionEnabled, regressionSlope, regressionIntercept]);

  const earliestFundStart = React.useMemo(() => {
    return funds.length > 0 ? funds.reduce((min, fund) =>
      new Date(fund.startDate) < new Date(min.startDate) ? fund : min, funds[0]).startDate : '2020-01-01';
  }, [funds]);

  const getTimeRangeMonths = () => {
    switch (timeRange) {
      case '1y': return 12;
      case '2y': return 24;
      case '3y': return 36;
      case '5y': return 60;
      case '10y': return 120;
      case 'all': return 204;  // Aug 2018 to Aug 2035 = 17 years = 204 months
      default: return 204;  // Default to showing full timeline
    }
  };

  const timeRangeMonths = getTimeRangeMonths();
  const tenYearMonths = React.useMemo(() => {
    const start = new Date(earliestFundStart);
    return Array.from({ length: timeRangeMonths }, (_, i) => format(addMonths(start, i), 'MMM yyyy'));
  }, [earliestFundStart, timeRangeMonths]);

  const paddedPacingData = React.useMemo(() => {
    const pacingDict = pacingData.reduce((acc, d) => { acc[d.month] = d; return acc; }, {} as Record<string, typeof pacingData[0]>);
    const start = new Date(earliestFundStart);
    return Array.from({ length: timeRangeMonths }, (_, i) => {
      const monthKey = format(addMonths(start, i), 'yyyy-MM');
      return pacingDict[monthKey] || { month: monthKey, funds: {} };
    });
  }, [pacingData, earliestFundStart, timeRangeMonths]);

  const paddedRegressionPoints = React.useMemo(() => {
    if (!regressionPoints) return null;
    if (regressionPoints.length >= timeRangeMonths) return regressionPoints.slice(0, timeRangeMonths);
    return [
      ...regressionPoints,
      ...Array(timeRangeMonths - regressionPoints.length).fill(regressionPoints[regressionPoints.length - 1] || 0)
    ];
  }, [regressionPoints, timeRangeMonths]);

  // Calculate sector distribution for pie chart
  const sectorData = useMemo(() => {
    const sectorCounts: { [key: string]: number } = {};
    portfolioCompanies.forEach(company => {
      const sector = company.sector || 'Unknown';
      sectorCounts[sector] = (sectorCounts[sector] || 0) + 1;
    });
    return Object.entries(sectorCounts || {}).map(([name, value], index) => ({
      name,
      value,
      color: COLORS[index % COLORS.length]
    }));
  }, [portfolioCompanies]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-lg text-gray-600">Loading portfolio data...</p>
        </div>
      </div>
    );
  }

  const calculatePacingData = () => {
    const selectedFundsData = funds.filter(fund => selectedFunds.includes(fund.id));
    const startDates = selectedFundsData.map(fund => new Date(fund.startDate));
    const earliestStart = new Date(Math.min(...startDates.map(d => d.getTime())));
    const latestStart = new Date(Math.max(...startDates.map(d => d.getTime())));
    
    // Calculate end date based on fund life + extensions
    const maxFundLife = Math.max(...selectedFundsData.map(f => f.fundLifeYears + f.extensionYears));
    const endDate = new Date(latestStart);
    endDate.setFullYear(endDate.getFullYear() + maxFundLife);

    const monthlyData: PacingData[] = [];
    const currentDate = new Date(earliestStart);

    while (currentDate <= endDate) {
      const monthKey = currentDate.toISOString().slice(0, 7);
      const monthData: PacingData = {
        month: monthKey,
        funds: {}
      };

      selectedFundsData.forEach(fund => {
        const fundStartDate = new Date(fund.startDate);
        const fundEndDate = new Date(fundStartDate);
        fundEndDate.setFullYear(fundEndDate.getFullYear() + fund.fundLifeYears + fund.extensionYears);

        if (currentDate >= fundStartDate && currentDate <= fundEndDate) {
          const monthsSinceStart = (currentDate.getFullYear() - fundStartDate.getFullYear()) * 12 + 
                                  (currentDate.getMonth() - fundStartDate.getMonth());
          const yearsSinceStart = monthsSinceStart / 12;
          
          // Use deployment curve for more realistic pacing
          const deploymentProgress = calculateDeploymentCurve(fund, monthsSinceStart);
          const deployableCapital = calculateDeployableCapital(fund);
          
          // Calculate planned values using deployment curve
          const plannedDeployment = deployableCapital.initialDeployment * deploymentProgress;
          
          // For follow-ons, start after initial deployment period
          let plannedFollowOns = 0;
          if (monthsSinceStart > fund.deploymentPeriodYears * 12 * 0.5) {
            const followOnProgress = Math.min(1, (monthsSinceStart - fund.deploymentPeriodYears * 12 * 0.5) / (fund.deploymentPeriodYears * 12));
            plannedFollowOns = deployableCapital.reserves * followOnProgress;
          }
          
          const totalPlannedInvestment = plannedDeployment + plannedFollowOns;
          
          // Calculate planned companies based on check sizes
          const initialCompanies = Math.floor(plannedDeployment / fund.targetCheckSize);
          const cumulativePlannedCompanies = Math.min(initialCompanies, fund.targetCompanies * deploymentProgress);
          
          // Calculate management fee for current year
          const currentManagementFee = calculateManagementFee(fund, yearsSinceStart);
          
          // Get actual portfolio data
          const actualCompanies = portfolioCompanies.filter(company => {
            if (!company.first_investment_date) return false;
            const investmentDate = new Date(company.first_investment_date);
            return investmentDate >= fundStartDate && investmentDate <= currentDate;
          });

          const actualInvestment = actualCompanies.reduce((sum, company) => 
            sum + (company.total_invested_usd || 0), 0
          );

          const actualOwnership = actualCompanies.reduce((sum, company) => 
            sum + (company.ownership_percentage || 0), 0
          );

          monthData.funds[fund.id] = {
            plannedCompanies: Math.round(cumulativePlannedCompanies * 100) / 100,
            actualCompanies: actualCompanies.length,
            plannedOwnership: Math.round((fund.targetOwnership * deploymentProgress) * 100) / 100,
            actualOwnership: Math.round(actualOwnership * 100) / 100,
            plannedInvestment: Math.round(totalPlannedInvestment),
            actualInvestment: Math.round(actualInvestment),
            managementFee: currentManagementFee, // Add management fee to data
            deploymentProgress: Math.round(deploymentProgress * 100) // Add deployment progress percentage
          };
        }
      });

      monthlyData.push(monthData);
      currentDate.setMonth(currentDate.getMonth() + 1);
    }

    setPacingData(monthlyData);
  };

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

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-4 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ color: entry.color }} className="text-sm">
              {entry.name}: {entry.value ? formatCurrency(entry.value) : entry.value}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-black">
      {/* Enhanced Header */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 shadow-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-12">
            <h1 className="text-5xl font-bold text-white tracking-tight mb-2">Fund Pacing Analysis</h1>
            <p className="text-xl text-gray-200">Portfolio deployment tracking and strategic insights</p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Enhanced Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-gray-900 rounded-2xl shadow-lg border border-gray-700/50 p-6 transform hover:scale-105 transition-transform duration-200">
            <div className="flex items-center">
              <div className="p-3 bg-gray-800/30 rounded-xl">
                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-300">Portfolio Companies</p>
                <p className="text-2xl font-bold text-white">{portfolioCompanies.length}</p>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 rounded-2xl shadow-lg border border-gray-700/50 p-6 transform hover:scale-105 transition-transform duration-200">
            <div className="flex items-center">
              <div className="p-3 bg-gray-800/30 rounded-xl">
                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-300">Total Invested</p>
                <p className="text-2xl font-bold text-white">
                  {formatCurrency(portfolioCompanies.reduce((sum, c) => sum + (c.total_invested_usd || 0), 0))}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 rounded-2xl shadow-lg border border-gray-700/50 p-6 transform hover:scale-105 transition-transform duration-200">
            <div className="flex items-center">
              <div className="p-3 bg-gray-800/30 rounded-xl">
                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-300">Avg Ownership</p>
                <p className="text-2xl font-bold text-white">
                  {portfolioCompanies.length > 0 
                    ? formatPercentage(portfolioCompanies.reduce((sum, c) => sum + (c.ownership_percentage || 0), 0) / portfolioCompanies.length)
                    : '0%'
                  }
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 rounded-2xl shadow-lg border border-gray-700/50 p-6 transform hover:scale-105 transition-transform duration-200">
            <div className="flex items-center">
              <div className="p-3 bg-gray-800/30 rounded-xl">
                <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-300">Deployment Progress</p>
                <p className="text-2xl font-bold text-white">
                  {Math.round((portfolioCompanies.reduce((sum, c) => sum + (c.total_invested_usd || 0), 0) / 
                    selectedFunds.reduce((sum, fundId) => {
                      const fund = funds.find(f => f.id === fundId);
                      return sum + (fund?.size || 0);
                    }, 0)) * 100)}%
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio Selector */}
        <div className="bg-gray-900 rounded-2xl shadow-lg border border-gray-700/50 p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">Select Portfolio</h3>
              <p className="text-sm text-gray-300">Choose a portfolio to view its pacing</p>
            </div>
            <select
              value={selectedPortfolioId}
              onChange={(e) => setSelectedPortfolioId(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a portfolio</option>
              {portfolios.map((portfolio) => (
                <option key={portfolio.id} value={portfolio.id}>
                  {portfolio.name} ({portfolio.companies?.length || 0} companies)
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Chart Controls */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Analytics Dashboard</h2>
              <p className="text-gray-600">Track your fund performance across multiple dimensions</p>
            </div>
            
            <div className="flex flex-wrap gap-4">
              {/* Chart Type Selector */}
              <div className="flex bg-gray-100 rounded-lg p-1">
                {[
                  { id: 'deployment', label: 'Deployment' },
                  { id: 'companies', label: 'Companies' },
                  { id: 'sectors', label: 'Sectors' },
                  { id: 'stacked', label: 'Stacked' }
                ].map(chart => (
                  <button
                    key={chart.id}
                    onClick={() => setSelectedChart(chart.id)}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                      selectedChart === chart.id
                        ? 'bg-white text-blue-600 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    {chart.label}
                  </button>
                ))}
              </div>

              {/* Time Range Selector */}
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="1y">1 Year</option>
                <option value="2y">2 Years</option>
                <option value="3y">3 Years</option>
                <option value="5y">5 Years</option>
                <option value="10y">10 Years</option>
                <option value="all">All (2018-2035)</option>
              </select>
            </div>
          </div>
          
          {/* Regression Input UI */}
          {selectedChart === 'deployment' && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={regressionEnabled}
                    onChange={(e) => setRegressionEnabled(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm font-medium text-gray-700">Enable Regression Line</span>
                </label>
                {regressionEnabled && (
                  <>
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-gray-600">Slope:</label>
                      <input
                        type="number"
                        value={regressionSlope ?? ''}
                        onChange={(e) => setRegressionSlope(e.target.value ? Number(e.target.value) : null)}
                        placeholder="Auto"
                        step="0.01"
                        className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-gray-600">Intercept:</label>
                      <input
                        type="number"
                        value={regressionIntercept ?? ''}
                        onChange={(e) => setRegressionIntercept(e.target.value ? Number(e.target.value) : null)}
                        placeholder="Auto"
                        step="0.01"
                        className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                      />
                    </div>
                    <button
                      onClick={() => {
                        setRegressionSlope(null);
                        setRegressionIntercept(null);
                      }}
                      className="px-3 py-1 text-sm text-blue-600 hover:text-blue-700 underline"
                    >
                      Reset to Auto
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Enhanced Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Capital Deployment Chart */}
          {selectedChart === 'deployment' && (
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">Capital Deployment</h3>
                  <p className="text-sm text-gray-600">Actual vs planned investment over time</p>
                </div>
              </div>
              <div className="h-96 w-full overflow-x-auto">
                <div style={{ width: timeRange === 'all' ? '8000px' : '100%', height: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={paddedPacingData.map((data, i) => {
                        const actual = Object.values(data.funds).reduce((sum, fundData) => sum + fundData.actualInvestment, 0);
                        const planned = Object.values(data.funds).reduce((sum, fundData) => sum + fundData.plannedInvestment, 0);
                        return {
                          month: tenYearMonths[i],
                          actual,
                          planned,
                          regression: paddedRegressionPoints ? paddedRegressionPoints[i] : null,
                        };
                      })}
                      margin={{ top: 20, right: 30, left: 20, bottom: 40 }}
                  >
                    <defs>
                      <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="plannedGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis 
                      dataKey="month" 
                      minTickGap={0} 
                      interval={timeRange === 'all' ? 2 : 0}  // Show every other month for 'all', every month otherwise
                      angle={-45}
                      textAnchor="end"
                      height={80}
                      stroke="#6b7280" 
                      fontSize={9} 
                    />
                    <YAxis 
                      tickFormatter={formatCurrency} 
                      width={100} 
                      stroke="#6b7280" 
                      fontSize={12} 
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Area 
                      type="monotone" 
                      dataKey="actual" 
                      stroke="#3B82F6" 
                      strokeWidth={3} 
                      fill="url(#actualGradient)" 
                      name="Actual Investment" 
                    />
                    <Area 
                      type="monotone" 
                      dataKey="planned" 
                      stroke="#10B981" 
                      strokeWidth={3} 
                      fill="url(#plannedGradient)" 
                      name="Planned Investment" 
                    />
                    {paddedRegressionPoints && (
                      <Line 
                        type="monotone" 
                        dataKey="regression" 
                        stroke="#6366f1" 
                        strokeWidth={3} 
                        name="Linear Pacing Trend" 
                        dot={false} 
                        strokeDasharray="8 4" 
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Companies Chart */}
          {selectedChart === 'companies' && (
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">Portfolio Companies</h3>
                  <p className="text-sm text-gray-600">Actual vs planned company count</p>
                </div>
              </div>
              <div className="h-96 w-full overflow-x-auto">
                <div style={{ width: timeRange === 'all' ? '8000px' : '100%', height: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                    data={paddedPacingData.map((data, i) => {
                      const actual = Object.values(data.funds).reduce((sum, fundData) => sum + fundData.actualCompanies, 0);
                      const planned = Object.values(data.funds).reduce((sum, fundData) => sum + fundData.plannedCompanies, 0);
                      return {
                        month: tenYearMonths[i],
                        actual,
                        planned,
                      };
                    })}
                    margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                    <XAxis 
                      dataKey="month" 
                      minTickGap={0} 
                      interval={timeRange === 'all' ? 2 : 0}  // Show every other month for 'all', every month otherwise
                      angle={-45}
                      textAnchor="end"
                      height={80}
                      stroke="#6b7280" 
                      fontSize={9} 
                    />
                    <YAxis width={60} stroke="#6b7280" fontSize={12} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend />
                    <Bar dataKey="actual" fill="#3B82F6" name="Actual Companies" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="planned" fill="#10B981" name="Planned Companies" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Sector Distribution Chart */}
          {selectedChart === 'sectors' && (
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">Sector Distribution</h3>
                  <p className="text-sm text-gray-600">Portfolio companies by sector</p>
                </div>
              </div>
              <div className="h-96 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sectorData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={(props: any) => {
                        const { name, percent } = props;
                        return `${name} ${((percent ?? 0) * 100).toFixed(0)}%`;
                      }}
                      outerRadius={120}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {sectorData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Stacked Bar Chart */}
          {selectedChart === 'stacked' && (
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">Stacked Investment by Fund</h3>
                  <p className="text-sm text-gray-600">Cumulative investment breakdown by fund</p>
                </div>
              </div>
              <div className="h-96 w-full overflow-x-auto">
                <div style={{ minWidth: timeRange === 'all' ? '8000px' : '100%', height: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={paddedPacingData.map((data, i) => {
                        const result: any = { month: tenYearMonths[i] };
                        funds.forEach(fund => {
                          if (selectedFunds.includes(fund.id) && data.funds[fund.id]) {
                            result[fund.name] = data.funds[fund.id].actualInvestment;
                          }
                        });
                        return result;
                      })}
                      margin={{ top: 20, right: 30, left: 20, bottom: 40 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                      <XAxis 
                        dataKey="month" 
                        minTickGap={0} 
                        interval={timeRange === 'all' ? 2 : 0}
                        angle={-45}
                        textAnchor="end"
                        height={80}
                        stroke="#6b7280" 
                        fontSize={9} 
                      />
                      <YAxis 
                        tickFormatter={formatCurrency} 
                        width={100} 
                        stroke="#6b7280" 
                        fontSize={12} 
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend />
                      {funds.filter(f => selectedFunds.includes(f.id)).map((fund, index) => (
                        <Bar 
                          key={fund.id} 
                          dataKey={fund.name} 
                          stackId="investment" 
                          fill={fund.color} 
                          name={fund.name}
                          radius={index === funds.filter(f => selectedFunds.includes(f.id)).length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* Fund Configuration Panel */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-gray-900">Fund Configuration</h3>
                <p className="text-sm text-gray-600">Sophisticated fund lifecycle parameters</p>
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors"
              >
                + Create Fund
              </button>
            </div>
            
            <div className="space-y-4 max-h-[400px] overflow-y-auto">
              {funds.map(fund => (
                <div key={fund.id} className="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center mb-4">
                    <div 
                      className="w-4 h-4 rounded-full mr-3" 
                      style={{ backgroundColor: fund.color }}
                    ></div>
                    <h4 className="text-lg font-semibold text-gray-900">{fund.name}</h4>
                    <span className="ml-auto text-sm text-gray-500 mr-4">
                      {calculateManagementFee(fund, new Date().getFullYear() - new Date(fund.startDate).getFullYear()).toFixed(2)}% fee
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={async () => {
                          try {
                            await updateFund(fund.id, fund);
                            alert('Fund updated successfully');
                          } catch (error) {
                            alert('Failed to update fund');
                          }
                        }}
                        className="px-3 py-1 text-sm text-green-600 hover:text-green-700 hover:bg-green-50 rounded transition-colors"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingFund(fund)}
                        className="px-3 py-1 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Are you sure you want to delete ${fund.name}?`)) {
                            deleteFund(fund.id);
                          }
                        }}
                        className="px-3 py-1 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  
                  {/* Core Parameters */}
                  <div className="mb-4">
                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Core Parameters</h5>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Fund Size</label>
                        <input
                          type="number"
                          value={fund.size}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, size: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Target Companies</label>
                        <input
                          type="number"
                          value={fund.targetCompanies}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, targetCompanies: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                  
                  {/* Deployment Strategy */}
                  <div className="mb-4">
                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Deployment Strategy</h5>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Deploy Period (yr)</label>
                        <input
                          type="number"
                          value={fund.deploymentPeriodYears}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, deploymentPeriodYears: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="2"
                          max="6"
                          step="0.5"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Reserve Ratio</label>
                        <input
                          type="number"
                          value={fund.reserveRatio * 100}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, reserveRatio: Number(e.target.value) / 100 } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="30"
                          max="60"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">%</span>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Recycling Rate</label>
                        <input
                          type="number"
                          value={fund.recyclingRate * 100}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, recyclingRate: Number(e.target.value) / 100 } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="0"
                          max="30"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">%</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Fee Structure */}
                  <div className="mb-4">
                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Fee Structure</h5>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Initial Mgmt Fee</label>
                        <input
                          type="number"
                          value={fund.initialManagementFee}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, initialManagementFee: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="1"
                          max="3"
                          step="0.25"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">%</span>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Annual Reduction</label>
                        <input
                          type="number"
                          value={fund.managementFeeReduction}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, managementFeeReduction: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="0"
                          max="0.5"
                          step="0.25"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">%</span>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Carry</label>
                        <input
                          type="number"
                          value={fund.carriedInterest}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, carriedInterest: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="15"
                          max="30"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">%</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Investment Strategy */}
                  <div>
                    <h5 className="text-sm font-semibold text-gray-700 mb-2">Investment Strategy</h5>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Target Check Size</label>
                        <input
                          type="number"
                          value={fund.targetCheckSize}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, targetCheckSize: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Follow-on Multiple</label>
                        <input
                          type="number"
                          value={fund.targetFollowOnMultiple}
                          onChange={(e) => {
                            const updatedFunds = funds.map(f => 
                              f.id === fund.id ? { ...f, targetFollowOnMultiple: Number(e.target.value) } : f
                            );
                            setFunds(updatedFunds);
                          }}
                          min="1"
                          max="5"
                          step="0.5"
                          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500"
                        />
                        <span className="text-xs text-gray-500">x</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Capital Breakdown */}
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <h5 className="text-xs font-semibold text-gray-700 mb-2">Capital Allocation</h5>
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Initial Deployment:</span>
                        <span className="font-medium">{formatCurrency(calculateDeployableCapital(fund).initialDeployment)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Reserves:</span>
                        <span className="font-medium">{formatCurrency(calculateDeployableCapital(fund).reserves)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Recyclable:</span>
                        <span className="font-medium">{formatCurrency(calculateDeployableCapital(fund).recyclable)}</span>
                      </div>
                      <div className="flex justify-between border-t pt-1">
                        <span className="text-gray-700 font-semibold">Total Deployable:</span>
                        <span className="font-semibold">{formatCurrency(calculateDeployableCapital(fund).total)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Portfolio Companies Table */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-xl font-bold text-gray-900">Portfolio Companies</h3>
              <p className="text-sm text-gray-600">Detailed view of all portfolio companies</p>
            </div>
            <button className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors">
              Export Data
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sector</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Investment Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount Invested</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ownership %</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Current ARR</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Revenue Over Time</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {portfolioCompanies.map((company) => {
                  // Get revenue time-series for this company
                  const companyRevenueData = ledgerData?.time_series?.filter((entry: any) => 
                    entry.company_id === company.id
                  ) || [];
                  
                  // Prepare data for sparkline
                  const sparklineData = companyRevenueData
                    .map((entry: any) => ({
                      date: entry.date,
                      revenue: entry.revenue
                    }))
                    .sort((a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime());

                  return (
                    <tr key={company.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{company.name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{company.sector || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {company.first_investment_date ? format(new Date(company.first_investment_date), 'MMM yyyy') : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {company.total_invested_usd ? formatCurrency(company.total_invested_usd) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {company.ownership_percentage ? formatPercentage(company.ownership_percentage) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {company.current_arr_usd ? formatCurrency(company.current_arr_usd) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {sparklineData.length > 0 ? (
                          <div className="w-32 h-8">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={sparklineData}>
                                <Line 
                                  type="monotone" 
                                  dataKey="revenue" 
                                  stroke="#3B82F6" 
                                  strokeWidth={2}
                                  dot={false}
                                />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">No data</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          company.funnel_status === 'portfolio' ? 'bg-green-100 text-green-800' :
                          company.funnel_status === 'exited' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {company.funnel_status ? 
                            company.funnel_status.charAt(0).toUpperCase() + company.funnel_status.slice(1) : 
                            'Unknown'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Create Fund Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Create New Fund</h2>
            <FundForm
              fund={null}
              onSave={async (fundData) => {
                await createFund(fundData);
              }}
              onCancel={() => setShowCreateModal(false)}
            />
          </div>
        </div>
      )}

      {/* Edit Fund Modal */}
      {editingFund && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Edit Fund: {editingFund.name}</h2>
            <FundForm
              fund={editingFund}
              onSave={async (fundData) => {
                await updateFund(editingFund.id, fundData);
              }}
              onCancel={() => setEditingFund(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Fund Form Component
function FundForm({ fund, onSave, onCancel }: { fund: Fund | null, onSave: (data: Partial<Fund>) => Promise<void>, onCancel: () => void }) {
  const [formData, setFormData] = useState<Partial<Fund>>(fund || {
    name: '',
    startDate: new Date().toISOString().split('T')[0],
    vintageYear: new Date().getFullYear(),
    firstClose: new Date().toISOString().split('T')[0],
    finalClose: new Date().toISOString().split('T')[0],
    size: 100000000,
    targetCompanies: 20,
    targetOwnership: 15,
    color: COLORS[0],
    deploymentPeriodYears: 4,
    fundLifeYears: 10,
    extensionYears: 2,
    initialManagementFee: 2.0,
    managementFeeReduction: 0.25,
    carriedInterest: 20,
    preferredReturn: 8,
    recyclingRate: 0.15,
    reserveRatio: 0.5,
    targetCheckSize: 2500000,
    targetFollowOnMultiple: 2.0
  });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(formData);
    } catch (error) {
      alert('Failed to save fund. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Fund Name *</label>
          <input
            type="text"
            required
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Vintage Year *</label>
          <input
            type="number"
            required
            value={formData.vintageYear}
            onChange={(e) => setFormData({ ...formData, vintageYear: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Start Date *</label>
          <input
            type="date"
            required
            value={formData.startDate}
            onChange={(e) => setFormData({ ...formData, startDate: e.target.value, firstClose: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Final Close</label>
          <input
            type="date"
            value={formData.finalClose}
            onChange={(e) => setFormData({ ...formData, finalClose: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Fund Size (USD) *</label>
          <input
            type="number"
            required
            value={formData.size}
            onChange={(e) => setFormData({ ...formData, size: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target Companies *</label>
          <input
            type="number"
            required
            value={formData.targetCompanies}
            onChange={(e) => setFormData({ ...formData, targetCompanies: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target Ownership %</label>
          <input
            type="number"
            value={formData.targetOwnership}
            onChange={(e) => setFormData({ ...formData, targetOwnership: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
          <input
            type="color"
            value={formData.color}
            onChange={(e) => setFormData({ ...formData, color: e.target.value })}
            className="w-full h-10 border border-gray-300 rounded-lg"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Deployment Period (Years)</label>
          <input
            type="number"
            step="0.5"
            value={formData.deploymentPeriodYears}
            onChange={(e) => setFormData({ ...formData, deploymentPeriodYears: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Fund Life (Years)</label>
          <input
            type="number"
            value={formData.fundLifeYears}
            onChange={(e) => setFormData({ ...formData, fundLifeYears: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Reserve Ratio</label>
          <input
            type="number"
            step="0.01"
            value={(formData.reserveRatio || 0) * 100}
            onChange={(e) => setFormData({ ...formData, reserveRatio: Number(e.target.value) / 100 })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-500">%</span>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Initial Management Fee %</label>
          <input
            type="number"
            step="0.25"
            value={formData.initialManagementFee}
            onChange={(e) => setFormData({ ...formData, initialManagementFee: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Carried Interest %</label>
          <input
            type="number"
            value={formData.carriedInterest}
            onChange={(e) => setFormData({ ...formData, carriedInterest: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target Check Size</label>
          <input
            type="number"
            value={formData.targetCheckSize}
            onChange={(e) => setFormData({ ...formData, targetCheckSize: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
      <div className="flex justify-end gap-3 pt-4 border-t">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Fund'}
        </button>
      </div>
    </form>
  );
} 