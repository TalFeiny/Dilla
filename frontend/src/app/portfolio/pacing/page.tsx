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
  const [funds, setFunds] = useState<Fund[]>([
    {
      id: 'fund-1',
      name: 'Fund I',
      startDate: '2018-08-01',  // Changed to August 2018
      vintageYear: 2018,
      firstClose: '2018-08-01',
      finalClose: '2019-02-01',
      size: 50000000, // $50M
      targetCompanies: 15,
      targetOwnership: 18,
      color: '#3B82F6', // blue
      deploymentPeriodYears: 3,
      fundLifeYears: 10,
      extensionYears: 2,
      initialManagementFee: 2.0,
      managementFeeReduction: 0.25,
      carriedInterest: 20,
      preferredReturn: 8,
      recyclingRate: 0.15,
      reserveRatio: 0.5,
      targetCheckSize: 1500000,
      targetFollowOnMultiple: 2.0
    },
    {
      id: 'fund-2', 
      name: 'Fund II',
      startDate: '2023-01-01',
      vintageYear: 2023,
      firstClose: '2023-01-01',
      finalClose: '2023-06-01',
      size: 100000000, // $100M
      targetCompanies: 20,
      targetOwnership: 15,
      color: '#10B981', // green
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
    },
    {
      id: 'fund-3',
      name: 'Fund III',
      startDate: '2024-06-01',
      vintageYear: 2024,
      firstClose: '2024-06-01',
      finalClose: '2024-12-01',
      size: 150000000, // $150M
      targetCompanies: 25,
      targetOwnership: 12,
      color: '#F59E0B', // amber
      deploymentPeriodYears: 5,
      fundLifeYears: 10,
      extensionYears: 2,
      initialManagementFee: 2.0,
      managementFeeReduction: 0.25,
      carriedInterest: 20,
      preferredReturn: 8,
      recyclingRate: 0.15,
      reserveRatio: 0.45,
      targetCheckSize: 3000000,
      targetFollowOnMultiple: 2.5
    }
  ]);
  const [pacingData, setPacingData] = useState<PacingData[]>([]);
  const [selectedFunds, setSelectedFunds] = useState<string[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');

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
          // Convert portfolio to fund format for compatibility
          const portfolioFunds = data.map((p: any, index: number) => ({
            id: p.id,
            name: p.name,
            startDate: new Date(p.companies[0]?.investmentDate || Date.now()).toISOString().split('T')[0],
            vintageYear: new Date().getFullYear(),
            firstClose: new Date(p.companies[0]?.investmentDate || Date.now()).toISOString().split('T')[0],
            finalClose: new Date().toISOString().split('T')[0],
            size: p.fundSize || 100000000,
            targetCompanies: 20,
            targetOwnership: 15,
            color: COLORS[index % COLORS.length],
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
          }));
          setFunds(portfolioFunds);
          setSelectedFunds(portfolioFunds.map((f: any) => f.id));
          
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

  useEffect(() => {
    fetchPortfolios();
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

  const regressionPoints = React.useMemo(() => {
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
  }, Array.from(pacingData));

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
                  { id: 'deployment', label: 'Deployment', icon: '💰' },
                  { id: 'companies', label: 'Companies', icon: '🏢' },
                  { id: 'sectors', label: 'Sectors', icon: '📊' }
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
                    <span className="mr-2">{chart.icon}</span>
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
                      label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
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

          {/* Fund Configuration Panel */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-gray-900">Fund Configuration</h3>
                <p className="text-sm text-gray-600">Sophisticated fund lifecycle parameters</p>
              </div>
            </div>
            
            <div className="space-y-4 max-h-Array.from(px) overflow-y-auto">
              {funds.map(fund => (
                <div key={fund.id} className="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center mb-4">
                    <div 
                      className="w-4 h-4 rounded-full mr-3" 
                      style={{ backgroundColor: fund.color }}
                    ></div>
                    <h4 className="text-lg font-semibold text-gray-900">{fund.name}</h4>
                    <span className="ml-auto text-sm text-gray-500">
                      {calculateManagementFee(fund, new Date().getFullYear() - new Date(fund.startDate).getFullYear()).toFixed(2)}% fee
                    </span>
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
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {portfolioCompanies.map((company) => (
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
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
} 