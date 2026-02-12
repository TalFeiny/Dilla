'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  PieChart, Pie, Cell, Sankey, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Treemap, RadialBarChart, RadialBar, LabelList, ComposedChart, Line, Area
} from 'recharts';
import { cn } from '@/lib/utils';
import {
  TrendingUp, DollarSign, Users, Building2, Percent,
  GitBranch, Layers, Calculator, Bot, Sparkles,
  ChevronRight, Settings, Download, Eye, Plus, X,
  ArrowUpRight, ArrowDownRight, PieChart as PieChartIcon,
  FileText, Shield, Coins, Briefcase, Target
} from 'lucide-react';

// Financial color schemes
const FINANCIAL_COLORS = {
  equity: ['#1e40af', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#dbeafe'],
  debt: ['#dc2626', '#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2'],
  preferred: ['#7c3aed', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#ede9fe'],
  common: ['#059669', '#10b981', '#34d399', '#6ee7b7', '#a7f3d0', '#d1fae5'],
  mixed: ['#0891b2', '#06b6d4', '#22d3ee', '#67e8f9', '#a5f3fc', '#cffafe']
};

// Fund Waterfall Component - Shows distribution cascade
const FundWaterfallChart = ({ data }: { data: any }) => {
  const { distributions, lpInvestment, carried, hurdle } = data;
  
  const waterfallSteps = useMemo(() => {
    let cumulative = lpInvestment;
    const steps: Array<{
      name: string;
      value: number;
      cumulative: number;
      type: string;
      details?: any;
    }> = [
      { name: 'LP Capital', value: lpInvestment, cumulative: lpInvestment, type: 'initial' }
    ];
    
    distributions.forEach((dist: any, index: number) => {
      const lpShare = dist.amount * (1 - carried);
      const gpCarry = dist.amount * carried;
      
      cumulative += lpShare;
      steps.push({
        name: `Distribution ${index + 1} - LP`,
        value: lpShare,
        cumulative,
        type: 'lp',
        details: dist
      });
      
      if (cumulative > lpInvestment * (1 + hurdle)) {
        cumulative += gpCarry;
        steps.push({
          name: `Distribution ${index + 1} - Carry`,
          value: gpCarry,
          cumulative,
          type: 'carry',
          details: dist
        });
      }
    });
    
    return steps;
  }, [distributions, lpInvestment, carried, hurdle]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-blue-600" />
          Fund Waterfall Analysis
        </h3>
        <div className="flex gap-4 text-sm">
          <span>Hurdle: {(hurdle * 100).toFixed(0)}%</span>
          <span>Carry: {(carried * 100).toFixed(0)}%</span>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={waterfallSteps}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} fontSize={11} />
          <YAxis tickFormatter={(value) => `$${(value / 1000000).toFixed(1)}M`} />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload[0]) {
                const data = payload[0].payload;
                return (
                  <div className="bg-white p-4 rounded-lg shadow-lg border">
                    <p className="font-semibold">{data.name}</p>
                    <p className="text-lg font-bold text-blue-600">
                      ${(data.value / 1000000).toFixed(2)}M
                    </p>
                    <p className="text-sm text-gray-600">
                      Total: ${(data.cumulative / 1000000).toFixed(2)}M
                    </p>
                    {data.details && (
                      <div className="mt-2 pt-2 border-t text-xs">
                        <p>Exit: {data.details.company}</p>
                        <p>Multiple: {data.details.multiple}x</p>
                      </div>
                    )}
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {waterfallSteps.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={
                  entry.type === 'initial' ? '#1e40af' :
                  entry.type === 'lp' ? '#10b981' :
                  entry.type === 'carry' ? '#f59e0b' : '#6b7280'
                } 
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

// Cap Table Dilution Sankey - Shows ownership flow through rounds
const CapTableSankey = ({ data }: { data: any }) => {
  const { rounds, founders, employees } = data;
  
  const sankeyData = useMemo(() => {
    const nodes: any[] = [];
    const links: any[] = [];
    let nodeIndex = 0;
    
    // Add initial shareholders
    nodes.push({ name: 'Founders (Initial)', id: nodeIndex++ });
    nodes.push({ name: 'Employees (Initial)', id: nodeIndex++ });
    
    // Add nodes for each round
    rounds.forEach((round: any, roundIndex: number) => {
      nodes.push({ name: `${round.name} Investors`, id: nodeIndex++ });
      nodes.push({ name: `Post-${round.name} Founders`, id: nodeIndex++ });
      nodes.push({ name: `Post-${round.name} Employees`, id: nodeIndex++ });
      if (roundIndex > 0) {
        nodes.push({ name: `Post-${round.name} Previous Investors`, id: nodeIndex++ });
      }
    });
    
    // Create links showing dilution
    let currentFoundersOwnership = founders.initial;
    let currentEmployeesOwnership = employees.initial;
    let investorOwnerships: any[] = [];
    
    rounds.forEach((round: any, roundIndex: number) => {
      const dilution = 1 - round.dilution;
      const newInvestorOwnership = round.dilution;
      
      // Dilute existing shareholders
      currentFoundersOwnership *= dilution;
      currentEmployeesOwnership *= dilution;
      investorOwnerships = investorOwnerships.map(io => ({ ...io, ownership: io.ownership * dilution }));
      
      // Add links for this round
      const roundInvestorIndex = 2 + roundIndex * 4;
      const roundFoundersIndex = roundInvestorIndex + 1;
      const roundEmployeesIndex = roundInvestorIndex + 2;
      const roundPreviousIndex = roundInvestorIndex + 3;
      
      if (roundIndex === 0) {
        // First round - from initial to post-round
        links.push({
          source: 0, // Initial founders
          target: roundFoundersIndex,
          value: currentFoundersOwnership * 100
        });
        links.push({
          source: 1, // Initial employees
          target: roundEmployeesIndex,
          value: currentEmployeesOwnership * 100
        });
      } else {
        // Subsequent rounds - from previous round to current
        const prevFoundersIndex = 2 + (roundIndex - 1) * 4 + 1;
        const prevEmployeesIndex = 2 + (roundIndex - 1) * 4 + 2;
        
        links.push({
          source: prevFoundersIndex,
          target: roundFoundersIndex,
          value: currentFoundersOwnership * 100
        });
        links.push({
          source: prevEmployeesIndex,
          target: roundEmployeesIndex,
          value: currentEmployeesOwnership * 100
        });
        
        // Previous investors
        investorOwnerships.forEach((io, idx) => {
          const prevInvestorIndex = 2 + idx * 4;
          links.push({
            source: prevInvestorIndex,
            target: roundPreviousIndex,
            value: io.ownership * 100
          });
        });
      }
      
      // New investor gets their share
      links.push({
        source: roundInvestorIndex,
        target: roundInvestorIndex, // Self-loop for visualization
        value: newInvestorOwnership * 100
      });
      
      investorOwnerships.push({ round: round.name, ownership: newInvestorOwnership });
    });
    
    return { nodes, links };
  }, [rounds, founders, employees]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-purple-600" />
          Cap Table Dilution Flow
        </h3>
      </div>
      
      <ResponsiveContainer width="100%" height={500}>
        <Sankey
          data={sankeyData}
          nodePadding={50}
          nodeWidth={15}
          margin={{ top: 20, right: 200, bottom: 20, left: 20 }}
        >
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload[0]) {
                const data = payload[0].payload;
                if (data.source !== undefined && data.target !== undefined) {
                  return (
                    <div className="bg-white p-3 rounded-lg shadow-lg border">
                      <p className="text-sm font-semibold">Ownership Transfer</p>
                      <p className="text-lg font-bold text-purple-600">
                        {data.value?.toFixed(2)}%
                      </p>
                    </div>
                  );
                }
                return (
                  <div className="bg-white p-3 rounded-lg shadow-lg border">
                    <p className="font-semibold">{data.name}</p>
                  </div>
                );
              }
              return null;
            }}
          />
        </Sankey>
      </ResponsiveContainer>
      
      {/* Summary Table */}
      <div className="grid grid-cols-4 gap-4 mt-6">
        {rounds.map((round: any, index: number) => (
          <div key={round.name} className="bg-gray-50 p-4 rounded-lg">
            <h4 className="font-semibold text-sm mb-2">{round.name}</h4>
            <div className="space-y-1 text-xs">
              <p>Valuation: ${(round.valuation / 1000000).toFixed(0)}M</p>
              <p>Raised: ${(round.raised / 1000000).toFixed(0)}M</p>
              <p>Dilution: {(round.dilution * 100).toFixed(1)}%</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// Multi-Scenario Cap Table Pie Charts
const MultiCapTablePies = ({ scenarios }: { scenarios: any[] }) => {
  const COLORS = FINANCIAL_COLORS.mixed;
  
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <PieChartIcon className="w-5 h-5 text-green-600" />
        Cap Table Scenarios
      </h3>
      
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-6">
        {scenarios.map((scenario, scenarioIndex) => (
          <div key={scenarioIndex} className="bg-white p-4 rounded-lg border">
            <h4 className="font-semibold text-sm mb-2">{scenario.name}</h4>
            <p className="text-xs text-gray-600 mb-3">{scenario.description}</p>
            
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={scenario.ownership}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(props: any) => {
                    const { name, percent } = props;
                    return `${name}: ${(percent * 100).toFixed(1)}%`;
                  }}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {scenario.ownership.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            
            <div className="mt-3 pt-3 border-t">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="text-gray-500">Valuation</p>
                  <p className="font-semibold">${(scenario.valuation / 1000000).toFixed(0)}M</p>
                </div>
                <div>
                  <p className="text-gray-500">Exit Multiple</p>
                  <p className="font-semibold">{scenario.multiple}x</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// LP/GP Split Analysis
const LPGPSplitAnalysis = ({ data }: { data: any }) => {
  const { fundSize, managementFee, carry, hurdle, projectedReturns } = data;
  
  const splitData = useMemo(() => {
    return projectedReturns.map((returns: number) => {
      const totalReturns = fundSize * returns;
      const profits = totalReturns - fundSize;
      const hurdleAmount = fundSize * hurdle;
      
      let lpReturns = fundSize;
      let gpCarry = 0;
      
      if (profits > 0) {
        if (profits <= hurdleAmount) {
          lpReturns += profits;
        } else {
          lpReturns += hurdleAmount;
          const excessProfits = profits - hurdleAmount;
          gpCarry = excessProfits * carry;
          lpReturns += excessProfits * (1 - carry);
        }
      }
      
      const gpManagementFees = fundSize * managementFee * 10; // Assuming 10-year fund
      
      return {
        multiple: returns,
        lpReturns: lpReturns / fundSize,
        gpCarry: gpCarry / fundSize,
        gpFees: gpManagementFees / fundSize,
        totalGP: (gpCarry + gpManagementFees) / fundSize
      };
    });
  }, [fundSize, managementFee, carry, hurdle, projectedReturns]);

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <Coins className="w-5 h-5 text-yellow-600" />
        LP/GP Economics Analysis
      </h3>
      
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={splitData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="multiple" label={{ value: 'Fund Multiple', position: 'insideBottom', offset: -5 }} />
          <YAxis label={{ value: 'Returns Multiple', angle: -90, position: 'insideLeft' }} />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload[0]) {
                const data = payload[0].payload;
                return (
                  <div className="bg-white p-4 rounded-lg shadow-lg border">
                    <p className="font-semibold mb-2">At {data.multiple}x Returns</p>
                    <div className="space-y-1 text-sm">
                      <p className="text-blue-600">LP Returns: {data.lpReturns.toFixed(2)}x</p>
                      <p className="text-orange-600">GP Carry: {data.gpCarry.toFixed(2)}x</p>
                      <p className="text-purple-600">GP Fees: {data.gpFees.toFixed(2)}x</p>
                      <p className="font-semibold border-t pt-1">Total GP: {data.totalGP.toFixed(2)}x</p>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Legend />
          <Bar dataKey="lpReturns" stackId="a" fill="#3b82f6" name="LP Returns" />
          <Bar dataKey="gpCarry" stackId="a" fill="#f59e0b" name="GP Carry" />
          <Bar dataKey="gpFees" stackId="a" fill="#8b5cf6" name="GP Management Fees" />
          <Line type="monotone" dataKey="totalGP" stroke="#dc2626" strokeWidth={2} name="Total GP Share" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};

interface FinancialChartStudioProps {
  cells?: Record<string, any>;
  onClose?: () => void;
  onInsert?: (chart: any) => void;
}

export default function FinancialChartStudio({ cells, onClose, onInsert }: FinancialChartStudioProps) {
  const [chartType, setChartType] = useState<string>('waterfall');
  const [agentMode, setAgentMode] = useState(false);
  const [agentCommand, setAgentCommand] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Sample data for demonstration
  const [fundData, setFundData] = useState({
    lpInvestment: 100000000,
    carried: 0.20,
    hurdle: 0.08,
    distributions: [
      { company: 'Portfolio Co A', amount: 30000000, multiple: 3 },
      { company: 'Portfolio Co B', amount: 50000000, multiple: 5 },
      { company: 'Portfolio Co C', amount: 80000000, multiple: 8 },
      { company: 'Portfolio Co D', amount: 20000000, multiple: 2 },
      { company: 'Portfolio Co E', amount: 120000000, multiple: 12 }
    ]
  });
  
  const [capTableData, setCapTableData] = useState({
    founders: { initial: 0.60 },
    employees: { initial: 0.10 },
    rounds: [
      { name: 'Seed', valuation: 5000000, raised: 1000000, dilution: 0.20 },
      { name: 'Series A', valuation: 20000000, raised: 5000000, dilution: 0.25 },
      { name: 'Series B', valuation: 100000000, raised: 20000000, dilution: 0.20 },
      { name: 'Series C', valuation: 500000000, raised: 100000000, dilution: 0.20 }
    ]
  });
  
  const [scenarios] = useState([
    {
      name: 'Conservative Exit',
      description: '$500M valuation',
      valuation: 500000000,
      multiple: 5,
      ownership: [
        { name: 'Founders', value: 25 },
        { name: 'Employees', value: 15 },
        { name: 'Seed', value: 10 },
        { name: 'Series A', value: 15 },
        { name: 'Series B', value: 20 },
        { name: 'Series C', value: 15 }
      ]
    },
    {
      name: 'Base Case Exit',
      description: '$1B valuation',
      valuation: 1000000000,
      multiple: 10,
      ownership: [
        { name: 'Founders', value: 22 },
        { name: 'Employees', value: 18 },
        { name: 'Seed', value: 8 },
        { name: 'Series A', value: 12 },
        { name: 'Series B', value: 22 },
        { name: 'Series C', value: 18 }
      ]
    },
    {
      name: 'Optimistic Exit',
      description: '$2B valuation',
      valuation: 2000000000,
      multiple: 20,
      ownership: [
        { name: 'Founders', value: 20 },
        { name: 'Employees', value: 20 },
        { name: 'Seed', value: 5 },
        { name: 'Series A', value: 10 },
        { name: 'Series B', value: 20 },
        { name: 'Series C', value: 25 }
      ]
    }
  ]);
  
  const [lpData] = useState({
    fundSize: 500000000,
    managementFee: 0.02,
    carry: 0.20,
    hurdle: 0.08,
    projectedReturns: [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
  });

  // Agent command processing
  const processAgentCommand = async () => {
    setIsProcessing(true);
    
    // Parse natural language commands
    const command = agentCommand.toLowerCase();
    
    if (command.includes('waterfall')) {
      setChartType('waterfall');
      if (command.includes('carry')) {
        const carryMatch = command.match(/(\d+)%?\s*carry/);
        if (carryMatch) {
          setFundData(prev => ({ ...prev, carried: parseInt(carryMatch[1]) / 100 }));
        }
      }
    } else if (command.includes('cap table') || command.includes('dilution')) {
      setChartType('captable');
      if (command.includes('series')) {
        // Parse series information
        const seriesMatch = command.match(/series\s+([a-z])/i);
        if (seriesMatch) {
          // Add logic to update cap table rounds
        }
      }
    } else if (command.includes('scenario')) {
      setChartType('scenarios');
    } else if (command.includes('lp') || command.includes('gp')) {
      setChartType('lpgp');
    }
    
    setIsProcessing(false);
    setAgentCommand('');
  };

  const chartTypes = [
    { id: 'waterfall', label: 'Fund Waterfall', icon: TrendingUp, description: 'LP distributions & carry' },
    { id: 'captable', label: 'Cap Table Flow', icon: GitBranch, description: 'Dilution through rounds' },
    { id: 'scenarios', label: 'Exit Scenarios', icon: Target, description: 'Multiple cap tables' },
    { id: 'lpgp', label: 'LP/GP Split', icon: Coins, description: 'Economics analysis' }
  ];

  const renderChart = () => {
    switch (chartType) {
      case 'waterfall':
        return <FundWaterfallChart data={fundData} />;
      case 'captable':
        return <CapTableSankey data={capTableData} />;
      case 'scenarios':
        return <MultiCapTablePies scenarios={scenarios} />;
      case 'lpgp':
        return <LPGPSplitAnalysis data={lpData} />;
      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-11/12 max-w-7xl h-5/6 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <DollarSign className="w-6 h-6 text-green-600" />
            <h2 className="text-2xl font-bold">Financial Chart Studio</h2>
            <span className="px-2 py-1 bg-gradient-to-r from-green-500 to-blue-500 text-white text-xs rounded-full font-semibold">
              VC/PE Edition
            </span>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-80 border-r p-6 overflow-y-auto bg-gray-50">
            <div className="space-y-6">
              {/* Chart Type Selection */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-3 block">
                  Financial Visualizations
                </label>
                <div className="space-y-2">
                  {chartTypes.map(type => (
                    <button
                      key={type.id}
                      onClick={() => setChartType(type.id)}
                      className={cn(
                        "w-full flex items-start gap-3 p-3 rounded-lg border transition-all",
                        chartType === type.id
                          ? "border-blue-500 bg-blue-50"
                          : "border-gray-200 hover:bg-white"
                      )}
                    >
                      <type.icon className={cn(
                        "w-5 h-5 mt-0.5",
                        chartType === type.id ? "text-blue-600" : "text-gray-500"
                      )} />
                      <div className="text-left">
                        <p className="font-medium text-sm">{type.label}</p>
                        <p className="text-xs text-gray-500">{type.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Agent Builder */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-3 block flex items-center gap-2">
                  <Bot className="w-4 h-4" />
                  AI Chart Builder
                </label>
                <div className="space-y-3">
                  <textarea
                    value={agentCommand}
                    onChange={(e) => setAgentCommand(e.target.value)}
                    placeholder="Describe what you want to visualize...&#10;e.g., 'Show fund waterfall with 25% carry and 10% hurdle'&#10;or 'Create cap table showing dilution through Series C'"
                    className="w-full h-24 px-3 py-2 border rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    onClick={processAgentCommand}
                    disabled={isProcessing || !agentCommand}
                    className="w-full px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isProcessing ? (
                      <>
                        <Sparkles className="w-4 h-4 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate Chart
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Quick Examples */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-3 block">
                  Quick Examples
                </label>
                <div className="space-y-2">
                  <button
                    onClick={() => setAgentCommand('Create a fund waterfall with 20% carry and 8% hurdle')}
                    className="w-full text-left px-3 py-2 bg-white rounded-lg border hover:bg-gray-50 text-xs"
                  >
                    Standard 2/20 fund waterfall
                  </button>
                  <button
                    onClick={() => setAgentCommand('Show cap table dilution from seed to Series C')}
                    className="w-full text-left px-3 py-2 bg-white rounded-lg border hover:bg-gray-50 text-xs"
                  >
                    Multi-round dilution analysis
                  </button>
                  <button
                    onClick={() => setAgentCommand('Compare exit scenarios at 500M, 1B, and 2B valuations')}
                    className="w-full text-left px-3 py-2 bg-white rounded-lg border hover:bg-gray-50 text-xs"
                  >
                    Exit scenario comparison
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Chart Display */}
          <div className="flex-1 p-8 overflow-auto">
            {renderChart()}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t bg-gray-50">
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span className="flex items-center gap-1">
              <Shield className="w-4 h-4" />
              SEC Compliant
            </span>
            <span className="flex items-center gap-1">
              <FileText className="w-4 h-4" />
              LP Reporting Ready
            </span>
          </div>
          <div className="flex gap-3">
            <button className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2">
              <Download className="w-4 h-4" />
              Export
            </button>
            <button
              onClick={() => onInsert && onInsert({ type: chartType, data: { fundData, capTableData, scenarios, lpData } })}
              className="px-6 py-2 bg-gradient-to-r from-green-600 to-blue-600 text-white rounded-lg hover:from-green-700 hover:to-blue-700 flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Insert Chart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}