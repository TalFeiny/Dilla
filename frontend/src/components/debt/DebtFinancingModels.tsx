'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Calculator,
  DollarSign,
  Percent,
  Calendar,
  FileText,
  BarChart3,
  Shield,
  Lock,
  Unlock,
  AlertCircle,
  ChevronRight,
  ChevronDown,
  Plus,
  Minus,
  Download,
  Upload,
  RefreshCw,
  Settings,
  Database,
  GitBranch,
  Layers,
  Target,
  Activity,
  PieChart,
  CreditCard,
  Building,
  Briefcase,
  Scale,
  FileCheck,
  ShieldAlert,
  Zap
} from 'lucide-react';

// Types for different debt structures
interface DebtMetrics {
  principal: number;
  interestRate: number;
  term: number; // in months
  amortization: 'bullet' | 'linear' | 'custom';
  covenants: Covenant[];
  fees: {
    origination: number;
    commitment: number;
    prepayment: number;
    administrative: number;
  };
}

interface Covenant {
  id: string;
  type: 'financial' | 'operational' | 'reporting';
  name: string;
  description: string;
  metric: string;
  threshold: number;
  operator: '<' | '>' | '<=' | '>=' | '=' | '!=';
  frequency: 'monthly' | 'quarterly' | 'annually';
  status: 'compliant' | 'breach' | 'waived' | 'cured';
  testDate?: string;
  actualValue?: number;
  consequences?: string;
}

interface CoverageRatio {
  name: string;
  value: number;
  threshold: number;
  status: 'healthy' | 'warning' | 'critical';
  formula: string;
  components: Record<string, number>;
}

interface LBOModel {
  targetCompany: string;
  purchasePrice: number;
  equity: number;
  seniorDebt: number;
  mezzanineDebt: number;
  workingCapital: number;
  transactionFees: number;
  exitMultiple: number;
  holdPeriod: number; // years
  irr?: number;
  moic?: number; // Multiple on Invested Capital
}

interface CLOTranche {
  id: string;
  name: string;
  rating: string;
  size: number;
  spread: number; // basis points over LIBOR/SOFR
  subordination: number; // % of deal subordinate to this tranche
  overcollateralization: number;
  interestCoverage: number;
  defaults?: number;
  recoveries?: number;
}

interface ABFacility {
  borrowingBase: {
    eligibleReceivables: number;
    eligibleInventory: number;
    advanceRates: {
      receivables: number; // percentage
      inventory: number; // percentage
    };
  };
  currentDrawn: number;
  availability: number;
  excessAvailability: number;
  minimumAvailability: number;
  springing?: boolean;
  sprintingThreshold?: number;
}

export default function DebtFinancingModels() {
  const [activeModel, setActiveModel] = useState<'private-credit' | 'abf' | 'clo' | 'lbo' | 'covenants' | 'coverage'>('private-credit');
  const [isCalculating, setIsCalculating] = useState(false);
  
  // Private Credit State
  const [privateCredit, setPrivateCredit] = useState<DebtMetrics>({
    principal: 50000000,
    interestRate: 0.12, // 12%
    term: 60, // 5 years
    amortization: 'bullet',
    covenants: [],
    fees: {
      origination: 0.02,
      commitment: 0.005,
      prepayment: 0.03,
      administrative: 0.001
    }
  });

  // LBO Model State
  const [lboModel, setLboModel] = useState<LBOModel>({
    targetCompany: 'Target Corp',
    purchasePrice: 500000000,
    equity: 175000000,
    seniorDebt: 250000000,
    mezzanineDebt: 75000000,
    workingCapital: 10000000,
    transactionFees: 15000000,
    exitMultiple: 10,
    holdPeriod: 5
  });

  // CLO Structure State
  const [cloTranches, setCloTranches] = useState<CLOTranche[]>([
    { id: 'aaa', name: 'Class A', rating: 'AAA', size: 250000000, spread: 150, subordination: 35, overcollateralization: 1.35, interestCoverage: 1.5 },
    { id: 'aa', name: 'Class B', rating: 'AA', size: 50000000, spread: 200, subordination: 25, overcollateralization: 1.25, interestCoverage: 1.4 },
    { id: 'a', name: 'Class C', rating: 'A', size: 40000000, spread: 275, subordination: 17, overcollateralization: 1.17, interestCoverage: 1.3 },
    { id: 'bbb', name: 'Class D', rating: 'BBB', size: 30000000, spread: 400, subordination: 11, overcollateralization: 1.11, interestCoverage: 1.2 },
    { id: 'bb', name: 'Class E', rating: 'BB', size: 25000000, spread: 700, subordination: 6, overcollateralization: 1.06, interestCoverage: 1.1 },
    { id: 'equity', name: 'Equity', rating: 'NR', size: 30000000, spread: 0, subordination: 0, overcollateralization: 1, interestCoverage: 1 }
  ]);

  // ABF State
  const [abFacility, setAbFacility] = useState<ABFacility>({
    borrowingBase: {
      eligibleReceivables: 75000000,
      eligibleInventory: 50000000,
      advanceRates: {
        receivables: 0.85,
        inventory: 0.65
      }
    },
    currentDrawn: 45000000,
    availability: 0,
    excessAvailability: 0,
    minimumAvailability: 10000000,
    springing: true,
    sprintingThreshold: 15000000
  });

  // Covenants State
  const [covenants, setCovenants] = useState<Covenant[]>([
    {
      id: 'dscr',
      type: 'financial',
      name: 'Debt Service Coverage Ratio',
      description: 'EBITDA / (Interest + Principal)',
      metric: 'DSCR',
      threshold: 1.25,
      operator: '>=',
      frequency: 'quarterly',
      status: 'compliant',
      actualValue: 1.45,
      testDate: '2025-06-30'
    },
    {
      id: 'leverage',
      type: 'financial',
      name: 'Total Leverage Ratio',
      description: 'Total Debt / EBITDA',
      metric: 'Leverage',
      threshold: 4.5,
      operator: '<=',
      frequency: 'quarterly',
      status: 'compliant',
      actualValue: 3.8,
      testDate: '2025-06-30'
    },
    {
      id: 'fixed-charge',
      type: 'financial',
      name: 'Fixed Charge Coverage Ratio',
      description: '(EBITDA - CapEx - Taxes) / Fixed Charges',
      metric: 'FCCR',
      threshold: 1.1,
      operator: '>=',
      frequency: 'quarterly',
      status: 'warning',
      actualValue: 1.15,
      testDate: '2025-06-30'
    },
    {
      id: 'minimum-ebitda',
      type: 'financial',
      name: 'Minimum EBITDA',
      description: 'Trailing 12-month EBITDA',
      metric: 'EBITDA',
      threshold: 50000000,
      operator: '>=',
      frequency: 'monthly',
      status: 'compliant',
      actualValue: 62000000,
      testDate: '2025-07-31'
    },
    {
      id: 'capex',
      type: 'operational',
      name: 'Maximum CapEx',
      description: 'Annual capital expenditures limit',
      metric: 'CapEx',
      threshold: 15000000,
      operator: '<=',
      frequency: 'annually',
      status: 'compliant',
      actualValue: 12500000,
      testDate: '2025-12-31'
    }
  ]);

  // Coverage Ratios State
  const [coverageRatios, setCoverageRatios] = useState<CoverageRatio[]>([
    {
      name: 'Interest Coverage Ratio',
      value: 3.2,
      threshold: 2.0,
      status: 'healthy',
      formula: 'EBITDA / Interest Expense',
      components: { ebitda: 62000000, interestExpense: 19375000 }
    },
    {
      name: 'Debt Service Coverage Ratio',
      value: 1.45,
      threshold: 1.25,
      status: 'healthy',
      formula: 'EBITDA / (Interest + Principal)',
      components: { ebitda: 62000000, debtService: 42758620 }
    },
    {
      name: 'Fixed Charge Coverage Ratio',
      value: 1.15,
      threshold: 1.1,
      status: 'warning',
      formula: '(EBITDA - CapEx - Taxes) / Fixed Charges',
      components: { ebitdaLessCapex: 49500000, fixedCharges: 43043478 }
    },
    {
      name: 'Asset Coverage Ratio',
      value: 2.1,
      threshold: 1.5,
      status: 'healthy',
      formula: '(Total Assets - Current Liabilities) / Total Debt',
      components: { netAssets: 683000000, totalDebt: 325000000 }
    },
    {
      name: 'Cash Coverage Ratio',
      value: 0.85,
      threshold: 0.5,
      status: 'healthy',
      formula: '(EBITDA + Depreciation) / Interest Expense',
      components: { ebitdaPlusDA: 68000000, interestExpense: 19375000 }
    }
  ]);

  // Calculate ABF availability
  useEffect(() => {
    const receivablesAvailable = abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables;
    const inventoryAvailable = abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory;
    const totalAvailable = receivablesAvailable + inventoryAvailable;
    const availability = totalAvailable - abFacility.currentDrawn;
    const excessAvailability = availability - abFacility.minimumAvailability;
    
    setAbFacility(prev => ({
      ...prev,
      availability,
      excessAvailability
    }));
  }, [abFacility.borrowingBase, abFacility.currentDrawn, abFacility.minimumAvailability]);

  // Calculate LBO returns
  const calculateLBOReturns = useCallback(() => {
    setIsCalculating(true);
    
    // Simple LBO return calculation
    const totalInvestment = lboModel.equity + lboModel.transactionFees;
    const entryEBITDA = lboModel.purchasePrice / 10; // Assume 10x entry multiple
    const exitEBITDA = entryEBITDA * Math.pow(1.1, lboModel.holdPeriod); // 10% EBITDA growth
    const exitValue = exitEBITDA * lboModel.exitMultiple;
    const debtPaydown = lboModel.seniorDebt * 0.3; // Assume 30% debt paydown
    const equityValue = exitValue - (lboModel.seniorDebt - debtPaydown) - lboModel.mezzanineDebt;
    
    const moic = equityValue / totalInvestment;
    const irr = Math.pow(moic, 1 / lboModel.holdPeriod) - 1;
    
    setLboModel(prev => ({
      ...prev,
      moic,
      irr
    }));
    
    setTimeout(() => setIsCalculating(false), 500);
  }, Array.from(Model));

  // Test covenant compliance
  const testCovenant = (covenant: Covenant): boolean => {
    if (!covenant.actualValue) return true;
    
    switch (covenant.operator) {
      case '<': return covenant.actualValue < covenant.threshold;
      case '>': return covenant.actualValue > covenant.threshold;
      case '<=': return covenant.actualValue <= covenant.threshold;
      case '>=': return covenant.actualValue >= covenant.threshold;
      case '=': return covenant.actualValue === covenant.threshold;
      case '!=': return covenant.actualValue !== covenant.threshold;
      default: return true;
    }
  };

  // Render Private Credit Model
  const renderPrivateCredit = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Loan Terms */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <CreditCard className="w-5 h-5" />
            Loan Terms
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Principal Amount</label>
              <div className="mt-1 relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={privateCredit.principal}
                  onChange={(e) => setPrivateCredit(prev => ({ ...prev, principal: Number(e.target.value) }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Interest Rate (Annual)</label>
              <div className="mt-1 relative">
                <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={privateCredit.interestRate * 100}
                  onChange={(e) => setPrivateCredit(prev => ({ ...prev, interestRate: Number(e.target.value) / 100 }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                  step="0.1"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Term (Months)</label>
              <input
                type="number"
                value={privateCredit.term}
                onChange={(e) => setPrivateCredit(prev => ({ ...prev, term: Number(e.target.value) }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Amortization</label>
              <select
                value={privateCredit.amortization}
                onChange={(e) => setPrivateCredit(prev => ({ ...prev, amortization: e.target.value as any }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg"
              >
                <option value="bullet">Bullet (Interest Only)</option>
                <option value="linear">Linear Amortization</option>
                <option value="custom">Custom Schedule</option>
              </select>
            </div>
          </div>
        </div>

        {/* Fees Structure */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Fee Structure
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Origination Fee</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={privateCredit.fees.origination * 100}
                  onChange={(e) => setPrivateCredit(prev => ({ 
                    ...prev, 
                    fees: { ...prev.fees, origination: Number(e.target.value) / 100 }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="0.1"
                />
                <span className="text-sm text-gray-600">%</span>
                <span className="text-sm font-medium">${((privateCredit.principal * privateCredit.fees.origination) / 1000000).toFixed(2)}M</span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Commitment Fee</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={privateCredit.fees.commitment * 100}
                  onChange={(e) => setPrivateCredit(prev => ({ 
                    ...prev, 
                    fees: { ...prev.fees, commitment: Number(e.target.value) / 100 }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="0.1"
                />
                <span className="text-sm text-gray-600">%</span>
                <span className="text-sm font-medium">${((privateCredit.principal * privateCredit.fees.commitment) / 1000000).toFixed(2)}M</span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Prepayment Penalty</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={privateCredit.fees.prepayment * 100}
                  onChange={(e) => setPrivateCredit(prev => ({ 
                    ...prev, 
                    fees: { ...prev.fees, prepayment: Number(e.target.value) / 100 }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="0.1"
                />
                <span className="text-sm text-gray-600">%</span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Administrative Fee (Annual)</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={privateCredit.fees.administrative * 100}
                  onChange={(e) => setPrivateCredit(prev => ({ 
                    ...prev, 
                    fees: { ...prev.fees, administrative: Number(e.target.value) / 100 }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="0.01"
                />
                <span className="text-sm text-gray-600">%</span>
                <span className="text-sm font-medium">${((privateCredit.principal * privateCredit.fees.administrative) / 1000).toFixed(0)}K/yr</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-lg p-6 text-white">
        <h3 className="text-lg font-semibold mb-4">Summary Metrics</h3>
        <div className="grid grid-cols-4 gap-6">
          <div>
            <div className="text-sm text-gray-300">Total Facility</div>
            <div className="text-2xl font-bold">${(privateCredit.principal / 1000000).toFixed(1)}M</div>
          </div>
          <div>
            <div className="text-sm text-gray-300">All-in Rate</div>
            <div className="text-2xl font-bold">
              {((privateCredit.interestRate + privateCredit.fees.origination / (privateCredit.term / 12)) * 100).toFixed(2)}%
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-300">Monthly Payment</div>
            <div className="text-2xl font-bold">
              ${((privateCredit.principal * privateCredit.interestRate / 12) / 1000000).toFixed(2)}M
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-300">Total Interest</div>
            <div className="text-2xl font-bold">
              ${((privateCredit.principal * privateCredit.interestRate * (privateCredit.term / 12)) / 1000000).toFixed(1)}M
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render ABF Model
  const renderABF = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Borrowing Base */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Database className="w-5 h-5" />
            Borrowing Base Calculation
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Eligible Receivables</label>
              <div className="mt-1 relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={abFacility.borrowingBase.eligibleReceivables}
                  onChange={(e) => setAbFacility(prev => ({
                    ...prev,
                    borrowingBase: {
                      ...prev.borrowingBase,
                      eligibleReceivables: Number(e.target.value)
                    }
                  }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Advance Rate on Receivables</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={abFacility.borrowingBase.advanceRates.receivables * 100}
                  onChange={(e) => setAbFacility(prev => ({
                    ...prev,
                    borrowingBase: {
                      ...prev.borrowingBase,
                      advanceRates: {
                        ...prev.borrowingBase.advanceRates,
                        receivables: Number(e.target.value) / 100
                      }
                    }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="1"
                />
                <span className="text-sm text-gray-600">%</span>
              </div>
            </div>
            
            <div className="pt-2 border-t">
              <div className="flex justify-between text-sm">
                <span>Receivables Availability</span>
                <span className="font-medium">
                  ${((abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables) / 1000000).toFixed(2)}M
                </span>
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Eligible Inventory</label>
              <div className="mt-1 relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={abFacility.borrowingBase.eligibleInventory}
                  onChange={(e) => setAbFacility(prev => ({
                    ...prev,
                    borrowingBase: {
                      ...prev.borrowingBase,
                      eligibleInventory: Number(e.target.value)
                    }
                  }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Advance Rate on Inventory</label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="number"
                  value={abFacility.borrowingBase.advanceRates.inventory * 100}
                  onChange={(e) => setAbFacility(prev => ({
                    ...prev,
                    borrowingBase: {
                      ...prev.borrowingBase,
                      advanceRates: {
                        ...prev.borrowingBase.advanceRates,
                        inventory: Number(e.target.value) / 100
                      }
                    }
                  }))}
                  className="flex-1 px-3 py-2 border border-gray-200 rounded-lg"
                  step="1"
                />
                <span className="text-sm text-gray-600">%</span>
              </div>
            </div>
            
            <div className="pt-2 border-t">
              <div className="flex justify-between text-sm">
                <span>Inventory Availability</span>
                <span className="font-medium">
                  ${((abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory) / 1000000).toFixed(2)}M
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Facility Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Facility Status
          </h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Current Drawn Amount</label>
              <div className="mt-1 relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={abFacility.currentDrawn}
                  onChange={(e) => setAbFacility(prev => ({ ...prev, currentDrawn: Number(e.target.value) }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                />
              </div>
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Minimum Availability Requirement</label>
              <div className="mt-1 relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={abFacility.minimumAvailability}
                  onChange={(e) => setAbFacility(prev => ({ ...prev, minimumAvailability: Number(e.target.value) }))}
                  className="w-full pl-10 pr-3 py-2 border border-gray-200 rounded-lg"
                />
              </div>
            </div>
            
            <div className="space-y-3 pt-4 border-t">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Total Borrowing Base</span>
                <span className="font-medium">
                  ${((abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables + 
                      abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory) / 1000000).toFixed(2)}M
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Current Outstanding</span>
                <span className="font-medium text-red-600">
                  -${(abFacility.currentDrawn / 1000000).toFixed(2)}M
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t">
                <span className="text-sm font-medium">Total Availability</span>
                <span className="font-bold text-green-600">
                  ${(abFacility.availability / 1000000).toFixed(2)}M
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Minimum Required</span>
                <span className="font-medium">
                  -${(abFacility.minimumAvailability / 1000000).toFixed(2)}M
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t">
                <span className="text-sm font-medium">Excess Availability</span>
                <span className={cn(
                  "font-bold",
                  abFacility.excessAvailability >= 0 ? "text-green-600" : "text-red-600"
                )}>
                  ${(abFacility.excessAvailability / 1000000).toFixed(2)}M
                </span>
              </div>
            </div>
            
            <div className="pt-4 border-t">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={abFacility.springing}
                  onChange={(e) => setAbFacility(prev => ({ ...prev, springing: e.target.checked }))}
                  className="rounded"
                />
                <span className="text-sm font-medium">Springing Covenant</span>
              </label>
              {abFacility.springing && (
                <div className="mt-2">
                  <label className="text-xs text-gray-600">Trigger Threshold</label>
                  <div className="mt-1 relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400" />
                    <input
                      type="number"
                      value={abFacility.sprintingThreshold}
                      onChange={(e) => setAbFacility(prev => ({ ...prev, sprintingThreshold: Number(e.target.value) }))}
                      className="w-full pl-8 pr-3 py-1 text-sm border border-gray-200 rounded"
                    />
                  </div>
                  {abFacility.excessAvailability < (abFacility.sprintingThreshold || 0) && (
                    <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      Covenant triggered - Below threshold
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Utilization Chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Facility Utilization</h3>
        <div className="space-y-4">
          <div className="relative h-12 bg-gray-100 rounded-lg overflow-hidden">
            <div 
              className="absolute left-0 top-0 h-full bg-red-500"
              style={{ width: `${(abFacility.currentDrawn / (abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables + abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory)) * 100}%` }}
            />
            <div 
              className="absolute top-0 h-full bg-yellow-500"
              style={{ 
                left: `${(abFacility.currentDrawn / (abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables + abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory)) * 100}%`,
                width: `${(abFacility.minimumAvailability / (abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables + abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory)) * 100}%`
              }}
            />
            <div className="absolute inset-0 flex items-center justify-center text-sm font-medium">
              {((abFacility.currentDrawn / (abFacility.borrowingBase.eligibleReceivables * abFacility.borrowingBase.advanceRates.receivables + abFacility.borrowingBase.eligibleInventory * abFacility.borrowingBase.advanceRates.inventory)) * 100).toFixed(1)}% Utilized
            </div>
          </div>
          <div className="flex items-center justify-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded" />
              <span>Drawn</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-yellow-500 rounded" />
              <span>Min. Required</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded" />
              <span>Available</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render CLO Structure
  const renderCLO = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Layers className="w-5 h-5" />
          CLO Capital Structure
        </h3>
        
        {/* Waterfall Visualization */}
        <div className="mb-6">
          <div className="space-y-2">
            {cloTranches.map((tranche, index) => (
              <div key={tranche.id} className="relative">
                <div className="flex items-center gap-4">
                  <div className="w-20 text-sm font-medium">{tranche.name}</div>
                  <div className={cn(
                    "w-16 px-2 py-1 rounded text-xs font-medium text-center",
                    tranche.rating === 'AAA' && "bg-blue-100 text-blue-800",
                    tranche.rating === 'AA' && "bg-blue-50 text-blue-700",
                    tranche.rating === 'A' && "bg-green-50 text-green-700",
                    tranche.rating === 'BBB' && "bg-yellow-50 text-yellow-700",
                    tranche.rating === 'BB' && "bg-orange-50 text-orange-700",
                    tranche.rating === 'NR' && "bg-gray-100 text-gray-700"
                  )}>
                    {tranche.rating}
                  </div>
                  <div className="flex-1">
                    <div className="relative h-10 bg-gray-100 rounded overflow-hidden">
                      <div 
                        className={cn(
                          "absolute left-0 top-0 h-full",
                          index === 0 && "bg-blue-500",
                          index === 1 && "bg-blue-400",
                          index === 2 && "bg-green-400",
                          index === 3 && "bg-yellow-400",
                          index === 4 && "bg-orange-400",
                          index === 5 && "bg-gray-400"
                        )}
                        style={{ width: `${(tranche.size / cloTranches.reduce((sum, t) => sum + t.size, 0)) * 100}%` }}
                      />
                      <div className="absolute inset-0 flex items-center justify-between px-3 text-xs">
                        <span className="font-medium">${(tranche.size / 1000000).toFixed(0)}M</span>
                        <span className="text-gray-600">
                          {((tranche.size / cloTranches.reduce((sum, t) => sum + t.size, 0)) * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="w-24 text-right">
                    <span className="text-sm font-medium">
                      {tranche.spread > 0 ? `L+${tranche.spread}` : 'Residual'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Total Deal Size */}
        <div className="pt-4 border-t">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Total Deal Size</span>
            <span className="text-xl font-bold">
              ${(cloTranches.reduce((sum, t) => sum + t.size, 0) / 1000000).toFixed(0)}M
            </span>
          </div>
        </div>
      </div>

      {/* Coverage Tests */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Overcollateralization Tests
          </h3>
          <div className="space-y-3">
            {cloTranches.filter(t => t.rating !== 'NR').map(tranche => (
              <div key={tranche.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{tranche.name} O/C</span>
                  {tranche.overcollateralization >= 1.1 ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{(tranche.overcollateralization * 100).toFixed(1)}%</div>
                  <div className="text-xs text-gray-500">Min: {((tranche.overcollateralization - 0.05) * 100).toFixed(1)}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Interest Coverage Tests
          </h3>
          <div className="space-y-3">
            {cloTranches.filter(t => t.rating !== 'NR').map(tranche => (
              <div key={tranche.id} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{tranche.name} I/C</span>
                  {tranche.interestCoverage >= 1.2 ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">{tranche.interestCoverage.toFixed(2)}x</div>
                  <div className="text-xs text-gray-500">Min: {(tranche.interestCoverage - 0.1).toFixed(2)}x</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // Render LBO Model
  const renderLBO = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        {/* Sources & Uses */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Briefcase className="w-5 h-5" />
            Sources & Uses
          </h3>
          
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">Sources of Funds</div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm">Sponsor Equity</span>
                  <input
                    type="number"
                    value={lboModel.equity}
                    onChange={(e) => setLboModel(prev => ({ ...prev, equity: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Senior Debt</span>
                  <input
                    type="number"
                    value={lboModel.seniorDebt}
                    onChange={(e) => setLboModel(prev => ({ ...prev, seniorDebt: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Mezzanine Debt</span>
                  <input
                    type="number"
                    value={lboModel.mezzanineDebt}
                    onChange={(e) => setLboModel(prev => ({ ...prev, mezzanineDebt: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center pt-2 border-t">
                  <span className="text-sm font-medium">Total Sources</span>
                  <span className="font-medium">
                    ${((lboModel.equity + lboModel.seniorDebt + lboModel.mezzanineDebt) / 1000000).toFixed(0)}M
                  </span>
                </div>
              </div>
            </div>
            
            <div>
              <div className="text-sm font-medium text-gray-700 mb-2">Uses of Funds</div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm">Purchase Price</span>
                  <input
                    type="number"
                    value={lboModel.purchasePrice}
                    onChange={(e) => setLboModel(prev => ({ ...prev, purchasePrice: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Transaction Fees</span>
                  <input
                    type="number"
                    value={lboModel.transactionFees}
                    onChange={(e) => setLboModel(prev => ({ ...prev, transactionFees: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm">Working Capital</span>
                  <input
                    type="number"
                    value={lboModel.workingCapital}
                    onChange={(e) => setLboModel(prev => ({ ...prev, workingCapital: Number(e.target.value) }))}
                    className="w-32 px-2 py-1 text-sm border border-gray-200 rounded text-right"
                  />
                </div>
                <div className="flex justify-between items-center pt-2 border-t">
                  <span className="text-sm font-medium">Total Uses</span>
                  <span className="font-medium">
                    ${((lboModel.purchasePrice + lboModel.transactionFees + lboModel.workingCapital) / 1000000).toFixed(0)}M
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Return Analysis */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Return Analysis
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Exit Multiple</label>
              <input
                type="number"
                value={lboModel.exitMultiple}
                onChange={(e) => setLboModel(prev => ({ ...prev, exitMultiple: Number(e.target.value) }))}
                className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg"
                step="0.5"
              />
            </div>
            
            <div>
              <label className="text-sm font-medium text-gray-700">Hold Period (Years)</label>
              <input
                type="number"
                value={lboModel.holdPeriod}
                onChange={(e) => setLboModel(prev => ({ ...prev, holdPeriod: Number(e.target.value) }))}
                className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg"
              />
            </div>
            
            <button
              onClick={calculateLBOReturns}
              disabled={isCalculating}
              className="w-full px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isCalculating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Calculating...
                </>
              ) : (
                <>
                  <Calculator className="w-4 h-4" />
                  Calculate Returns
                </>
              )}
            </button>
            
            {lboModel.irr && lboModel.moic && (
              <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                <div className="text-center p-4 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {(lboModel.irr * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-600">IRR</div>
                </div>
                <div className="text-center p-4 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-600">
                    {lboModel.moic.toFixed(2)}x
                  </div>
                  <div className="text-sm text-gray-600">MOIC</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Leverage Metrics */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Leverage Structure</h3>
        <div className="grid grid-cols-4 gap-6">
          <div>
            <div className="text-sm text-gray-600">Total Debt</div>
            <div className="text-xl font-bold">
              ${((lboModel.seniorDebt + lboModel.mezzanineDebt) / 1000000).toFixed(0)}M
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {((lboModel.seniorDebt + lboModel.mezzanineDebt) / lboModel.purchasePrice * 100).toFixed(1)}% of EV
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Equity Check</div>
            <div className="text-xl font-bold">
              ${(lboModel.equity / 1000000).toFixed(0)}M
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {(lboModel.equity / lboModel.purchasePrice * 100).toFixed(1)}% of EV
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Debt/EBITDA</div>
            <div className="text-xl font-bold">
              {((lboModel.seniorDebt + lboModel.mezzanineDebt) / (lboModel.purchasePrice / 10)).toFixed(1)}x
            </div>
            <div className="text-xs text-gray-500 mt-1">At entry</div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Senior/Total</div>
            <div className="text-xl font-bold">
              {(lboModel.seniorDebt / (lboModel.seniorDebt + lboModel.mezzanineDebt) * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-gray-500 mt-1">Debt composition</div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render Covenants
  const renderCovenants = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <FileCheck className="w-5 h-5" />
            Covenant Compliance Dashboard
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Last Updated:</span>
            <span className="text-sm font-medium">Aug 15, 2025</span>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 text-sm font-medium text-gray-700">Covenant</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Type</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Threshold</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Actual</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Headroom</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Status</th>
                <th className="text-center py-2 text-sm font-medium text-gray-700">Test Date</th>
              </tr>
            </thead>
            <tbody>
              {covenants.map(covenant => {
                const isCompliant = testCovenant(covenant);
                const headroom = covenant.actualValue && covenant.threshold
                  ? covenant.operator.includes('>') 
                    ? ((covenant.actualValue / covenant.threshold - 1) * 100)
                    : ((1 - covenant.actualValue / covenant.threshold) * 100)
                  : 0;
                
                return (
                  <tr key={covenant.id} className="border-b hover:bg-gray-50">
                    <td className="py-3">
                      <div>
                        <div className="text-sm font-medium">{covenant.name}</div>
                        <div className="text-xs text-gray-500">{covenant.description}</div>
                      </div>
                    </td>
                    <td className="text-center py-3">
                      <span className={cn(
                        "px-2 py-1 rounded text-xs font-medium",
                        covenant.type === 'financial' && "bg-blue-100 text-blue-700",
                        covenant.type === 'operational' && "bg-purple-100 text-purple-700",
                        covenant.type === 'reporting' && "bg-gray-100 text-gray-700"
                      )}>
                        {covenant.type}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className="text-sm font-mono">
                        {covenant.operator} {typeof covenant.threshold === 'number' && covenant.metric === 'EBITDA' 
                          ? `$${(covenant.threshold / 1000000).toFixed(0)}M`
                          : covenant.threshold}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className="text-sm font-mono font-medium">
                        {covenant.actualValue 
                          ? covenant.metric === 'EBITDA'
                            ? `$${(covenant.actualValue / 1000000).toFixed(0)}M`
                            : covenant.actualValue.toFixed(2)
                          : '—'}
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <span className={cn(
                        "text-sm font-medium",
                        headroom > 20 && "text-green-600",
                        headroom > 10 && headroom <= 20 && "text-yellow-600",
                        headroom <= 10 && "text-red-600"
                      )}>
                        {headroom.toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-center py-3">
                      <div className="flex items-center justify-center gap-1">
                        {covenant.status === 'compliant' && (
                          <>
                            <CheckCircle className="w-4 h-4 text-green-500" />
                            <span className="text-xs font-medium text-green-600">Compliant</span>
                          </>
                        )}
                        {covenant.status === 'warning' && (
                          <>
                            <AlertTriangle className="w-4 h-4 text-yellow-500" />
                            <span className="text-xs font-medium text-yellow-600">Warning</span>
                          </>
                        )}
                        {covenant.status === 'breach' && (
                          <>
                            <XCircle className="w-4 h-4 text-red-500" />
                            <span className="text-xs font-medium text-red-600">Breach</span>
                          </>
                        )}
                        {covenant.status === 'waived' && (
                          <>
                            <ShieldAlert className="w-4 h-4 text-blue-500" />
                            <span className="text-xs font-medium text-blue-600">Waived</span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="text-center py-3">
                      <span className="text-xs text-gray-600">{covenant.testDate}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Covenant Trends */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Covenant Headroom Trends</h3>
          <div className="space-y-3">
            {covenants.filter(c => c.type === 'financial').map(covenant => {
              const headroom = covenant.actualValue && covenant.threshold
                ? covenant.operator.includes('>') 
                  ? ((covenant.actualValue / covenant.threshold - 1) * 100)
                  : ((1 - covenant.actualValue / covenant.threshold) * 100)
                : 0;
              
              return (
                <div key={covenant.id}>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{covenant.name}</span>
                    <span className="font-medium">{headroom.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={cn(
                        "h-full transition-all",
                        headroom > 20 && "bg-green-500",
                        headroom > 10 && headroom <= 20 && "bg-yellow-500",
                        headroom <= 10 && "bg-red-500"
                      )}
                      style={{ width: `${Math.min(100, Math.max(0, headroom))}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold mb-4">Compliance Summary</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-3xl font-bold text-green-600">
                {covenants.filter(c => c.status === 'compliant').length}
              </div>
              <div className="text-sm text-gray-600">Compliant</div>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <div className="text-3xl font-bold text-yellow-600">
                {covenants.filter(c => c.status === 'warning').length}
              </div>
              <div className="text-sm text-gray-600">Warning</div>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-3xl font-bold text-red-600">
                {covenants.filter(c => c.status === 'breach').length}
              </div>
              <div className="text-sm text-gray-600">Breach</div>
            </div>
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <div className="text-3xl font-bold text-blue-600">
                {covenants.filter(c => c.status === 'waived').length}
              </div>
              <div className="text-sm text-gray-600">Waived</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render Coverage Ratios
  const renderCoverageRatios = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-6">
        {coverageRatios.map(ratio => (
          <div key={ratio.name} className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h4 className="text-sm font-medium text-gray-700">{ratio.name}</h4>
                <p className="text-xs text-gray-500 mt-1">{ratio.formula}</p>
              </div>
              <div className={cn(
                "p-1 rounded",
                ratio.status === 'healthy' && "bg-green-100",
                ratio.status === 'warning' && "bg-yellow-100",
                ratio.status === 'critical' && "bg-red-100"
              )}>
                {ratio.status === 'healthy' && <CheckCircle className="w-4 h-4 text-green-600" />}
                {ratio.status === 'warning' && <AlertTriangle className="w-4 h-4 text-yellow-600" />}
                {ratio.status === 'critical' && <XCircle className="w-4 h-4 text-red-600" />}
              </div>
            </div>
            
            <div className="mb-4">
              <div className="text-3xl font-bold">{ratio.value.toFixed(2)}x</div>
              <div className="text-xs text-gray-500">Minimum: {ratio.threshold.toFixed(2)}x</div>
            </div>
            
            <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className={cn(
                  "absolute left-0 top-0 h-full",
                  ratio.status === 'healthy' && "bg-green-500",
                  ratio.status === 'warning' && "bg-yellow-500",
                  ratio.status === 'critical' && "bg-red-500"
                )}
                style={{ width: `${Math.min(100, (ratio.value / (ratio.threshold * 2)) * 100)}%` }}
              />
              <div 
                className="absolute top-0 w-0.5 h-full bg-gray-600"
                style={{ left: `${(ratio.threshold / (ratio.threshold * 2)) * 100}%` }}
              />
            </div>
            
            <div className="mt-4 pt-4 border-t space-y-1">
              {Object.entries(ratio.components).map(([key, value]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-gray-600 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                  <span className="font-mono">${(value / 1000000).toFixed(1)}M</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Coverage Ratio Analysis */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-lg font-semibold mb-4">Coverage Analysis Summary</h3>
        <div className="grid grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-sm text-gray-600 mb-2">Overall Health</div>
            <div className={cn(
              "text-2xl font-bold",
              coverageRatios.every(r => r.status === 'healthy') && "text-green-600",
              coverageRatios.some(r => r.status === 'warning') && "text-yellow-600",
              coverageRatios.some(r => r.status === 'critical') && "text-red-600"
            )}>
              {coverageRatios.every(r => r.status === 'healthy') ? 'Strong' :
               coverageRatios.some(r => r.status === 'critical') ? 'Critical' : 'Moderate'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600 mb-2">Avg Coverage</div>
            <div className="text-2xl font-bold">
              {(coverageRatios.reduce((sum, r) => sum + r.value, 0) / coverageRatios.length).toFixed(2)}x
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600 mb-2">Min Coverage</div>
            <div className="text-2xl font-bold">
              {Math.min(...coverageRatios.map(r => r.value)).toFixed(2)}x
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-600 mb-2">At Risk</div>
            <div className="text-2xl font-bold text-red-600">
              {coverageRatios.filter(r => r.value < r.threshold * 1.2).length}
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Debt Financing Models</h1>
            <div className="flex items-center gap-2">
              <button className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                <Download className="w-4 h-4" />
                Export
              </button>
              <button className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-2">
                <Settings className="w-4 h-4" />
                Settings
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-6">
            <button
              onClick={() => setActiveModel('private-credit')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'private-credit'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              Private Credit
            </button>
            <button
              onClick={() => setActiveModel('abf')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'abf'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              Asset-Based Financing
            </button>
            <button
              onClick={() => setActiveModel('clo')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'clo'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              CLO Structure
            </button>
            <button
              onClick={() => setActiveModel('lbo')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'lbo'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              LBO Model
            </button>
            <button
              onClick={() => setActiveModel('covenants')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'covenants'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              Covenant Tracking
            </button>
            <button
              onClick={() => setActiveModel('coverage')}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm transition-colors",
                activeModel === 'coverage'
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              Coverage Ratios
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {activeModel === 'private-credit' && renderPrivateCredit()}
        {activeModel === 'abf' && renderABF()}
        {activeModel === 'clo' && renderCLO()}
        {activeModel === 'lbo' && renderLBO()}
        {activeModel === 'covenants' && renderCovenants()}
        {activeModel === 'coverage' && renderCoverageRatios()}
      </div>
    </div>
  );
}