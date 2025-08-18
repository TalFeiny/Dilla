'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { cn } from '@/lib/utils';
import {
  Calculator,
  FileSpreadsheet,
  CreditCard,
  Briefcase,
  PieChart,
  BarChart3,
  LineChart,
  TrendingUp,
  Building2,
  DollarSign,
  Shield,
  Layers,
  GitBranch,
  Database,
  Globe,
  Zap,
  Brain,
  Target,
  Scale,
  ChevronRight,
  ArrowRight,
  Sparkles,
  Lock,
  Activity,
  FileText,
  Settings,
  Grid3x3,
  Package,
  Coins,
  Landmark,
  Wallet,
  HandCoins,
  PiggyBank,
  Receipt,
  ScrollText,
  FileBarChart
} from 'lucide-react';

// Dynamically import components to avoid SSR issues
const EnhancedSpreadsheet = dynamic(() => import('@/components/accounts/EnhancedSpreadsheet'), { ssr: false });
const DebtFinancingModels = dynamic(() => import('@/components/debt/DebtFinancingModels'), { ssr: false });
const PortfolioConstructionModels = dynamic(() => import('@/components/portfolio/PortfolioConstructionModels'), { ssr: false });
const DynamicDataMatrix = dynamic(() => import('@/components/accounts/DynamicDataMatrix'), { ssr: false });

interface ModelCard {
  id: string;
  title: string;
  description: string;
  icon: any;
  category: 'spreadsheet' | 'debt' | 'portfolio' | 'valuation' | 'data';
  features: string[];
  badge?: string;
  color: string;
}

const models: ModelCard[] = [
  {
    id: 'enhanced-spreadsheet',
    title: 'Advanced Spreadsheet',
    description: 'Excel-like spreadsheet with formulas, charts, and pivot tables',
    icon: FileSpreadsheet,
    category: 'spreadsheet',
    features: [
      'Full formula support (SUM, AVERAGE, IF, etc.)',
      'Conditional formatting',
      'Charts and visualizations',
      'Import/Export CSV',
      'Undo/Redo functionality',
      'Cell references (A1, B2, etc.)',
      'Keyboard shortcuts',
      'Multi-cell selection'
    ],
    badge: 'Excel-Compatible',
    color: 'green'
  },
  {
    id: 'debt-financing',
    title: 'Debt Financing Models',
    description: 'Comprehensive debt structures for mature companies',
    icon: CreditCard,
    category: 'debt',
    features: [
      'Private Credit facilities',
      'Asset-Based Financing (ABF)',
      'CLO structures',
      'LBO models',
      'Covenant tracking',
      'Coverage ratio analysis',
      'Interest rate modeling',
      'Amortization schedules'
    ],
    badge: 'Institutional',
    color: 'blue'
  },
  {
    id: 'portfolio-construction',
    title: 'Portfolio Construction',
    description: 'Modern portfolio theory and optimization tools',
    icon: PieChart,
    category: 'portfolio',
    features: [
      'Mean-variance optimization',
      'Efficient frontier analysis',
      'Risk factor decomposition',
      'Stress testing scenarios',
      'Performance attribution',
      'Rebalancing strategies',
      'Asset allocation models',
      'Correlation matrices'
    ],
    badge: 'Quantitative',
    color: 'purple'
  },
  {
    id: 'data-matrix',
    title: 'Dynamic Data Matrix',
    description: 'Real-time data with citations and AI-powered insights',
    icon: Database,
    category: 'data',
    features: [
      'Live data feeds',
      'Source citations',
      'Multi-format support',
      'Agent API access',
      'Data validation',
      'Custom queries',
      'Export capabilities',
      'Confidence scoring'
    ],
    badge: 'AI-Powered',
    color: 'indigo'
  },
  {
    id: 'dcf-valuation',
    title: 'DCF Valuation',
    description: 'Discounted cash flow models with sensitivity analysis',
    icon: TrendingUp,
    category: 'valuation',
    features: [
      'Revenue projections',
      'WACC calculation',
      'Terminal value',
      'Sensitivity tables',
      'Scenario analysis',
      'Monte Carlo simulation',
      'Comparable analysis',
      'Football field charts'
    ],
    badge: 'Coming Soon',
    color: 'orange'
  },
  {
    id: 'merger-model',
    title: 'M&A Models',
    description: 'Merger models, accretion/dilution, and synergy analysis',
    icon: GitBranch,
    category: 'valuation',
    features: [
      'Purchase price allocation',
      'Accretion/dilution analysis',
      'Synergy modeling',
      'Pro forma statements',
      'Goodwill calculation',
      'Integration costs',
      'Earnout structures',
      'Tax implications'
    ],
    badge: 'Coming Soon',
    color: 'red'
  }
];

export default function FinancialModelsPage() {
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories = [
    { id: 'all', label: 'All Models', icon: Grid3x3 },
    { id: 'spreadsheet', label: 'Spreadsheets', icon: FileSpreadsheet },
    { id: 'debt', label: 'Debt Finance', icon: CreditCard },
    { id: 'portfolio', label: 'Portfolio', icon: PieChart },
    { id: 'valuation', label: 'Valuation', icon: TrendingUp },
    { id: 'data', label: 'Data Tools', icon: Database }
  ];

  const filteredModels = selectedCategory === 'all' 
    ? models 
    : models.filter(m => m.category === selectedCategory);

  // Render the active model component
  const renderActiveModel = () => {
    switch (activeModel) {
      case 'enhanced-spreadsheet':
        return <EnhancedSpreadsheet />;
      case 'debt-financing':
        return <DebtFinancingModels />;
      case 'portfolio-construction':
        return <PortfolioConstructionModels />;
      case 'data-matrix':
        return <DynamicDataMatrix />;
      default:
        return null;
    }
  };

  if (activeModel) {
    return (
      <div className="h-screen flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setActiveModel(null)}
                className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                ← Back to Models
              </button>
              <h2 className="text-lg font-semibold">
                {models.find(m => m.id === activeModel)?.title}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-2 hover:bg-gray-100 rounded-lg">
                <Settings className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
        
        {/* Model Component */}
        <div className="flex-1 overflow-auto bg-gray-50">
          {renderActiveModel()}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Financial Models Suite</h1>
              <p className="text-gray-600 mt-2">
                Professional-grade financial modeling tools for debt, equity, and portfolio analysis
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                AI Assistant
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Category Filter */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-6 py-3">
            {categories.map(cat => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={cn(
                  "px-4 py-2 rounded-lg font-medium text-sm transition-colors flex items-center gap-2",
                  selectedCategory === cat.id
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-100"
                )}
              >
                <cat.icon className="w-4 h-4" />
                {cat.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Models Grid */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredModels.map(model => {
            const Icon = model.icon;
            const isComingSoon = model.badge === 'Coming Soon';
            
            return (
              <div
                key={model.id}
                className={cn(
                  "bg-white rounded-xl border border-gray-200 overflow-hidden transition-all",
                  !isComingSoon && "hover:shadow-lg hover:border-gray-300 cursor-pointer",
                  isComingSoon && "opacity-75"
                )}
                onClick={() => !isComingSoon && setActiveModel(model.id)}
              >
                {/* Card Header */}
                <div className={cn(
                  "p-6 border-b border-gray-100",
                  model.color === 'green' && "bg-gradient-to-br from-green-50 to-emerald-50",
                  model.color === 'blue' && "bg-gradient-to-br from-blue-50 to-cyan-50",
                  model.color === 'purple' && "bg-gradient-to-br from-purple-50 to-pink-50",
                  model.color === 'indigo' && "bg-gradient-to-br from-indigo-50 to-blue-50",
                  model.color === 'orange' && "bg-gradient-to-br from-orange-50 to-yellow-50",
                  model.color === 'red' && "bg-gradient-to-br from-red-50 to-pink-50"
                )}>
                  <div className="flex items-start justify-between">
                    <div className={cn(
                      "p-3 rounded-lg",
                      model.color === 'green' && "bg-green-100",
                      model.color === 'blue' && "bg-blue-100",
                      model.color === 'purple' && "bg-purple-100",
                      model.color === 'indigo' && "bg-indigo-100",
                      model.color === 'orange' && "bg-orange-100",
                      model.color === 'red' && "bg-red-100"
                    )}>
                      <Icon className={cn(
                        "w-6 h-6",
                        model.color === 'green' && "text-green-600",
                        model.color === 'blue' && "text-blue-600",
                        model.color === 'purple' && "text-purple-600",
                        model.color === 'indigo' && "text-indigo-600",
                        model.color === 'orange' && "text-orange-600",
                        model.color === 'red' && "text-red-600"
                      )} />
                    </div>
                    {model.badge && (
                      <span className={cn(
                        "px-2 py-1 rounded-full text-xs font-medium",
                        model.badge === 'Coming Soon' && "bg-gray-100 text-gray-600",
                        model.badge === 'Excel-Compatible' && "bg-green-100 text-green-700",
                        model.badge === 'Institutional' && "bg-blue-100 text-blue-700",
                        model.badge === 'Quantitative' && "bg-purple-100 text-purple-700",
                        model.badge === 'AI-Powered' && "bg-indigo-100 text-indigo-700"
                      )}>
                        {model.badge}
                      </span>
                    )}
                  </div>
                  <h3 className="text-lg font-semibold mt-4">{model.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{model.description}</p>
                </div>
                
                {/* Features List */}
                <div className="p-6">
                  <div className="space-y-2">
                    {model.features.slice(0, 4).map((feature, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <ChevronRight className="w-3 h-3 text-gray-400 mt-0.5 flex-shrink-0" />
                        <span className="text-xs text-gray-600">{feature}</span>
                      </div>
                    ))}
                    {model.features.length > 4 && (
                      <div className="text-xs text-gray-500 pl-5">
                        +{model.features.length - 4} more features
                      </div>
                    )}
                  </div>
                  
                  {!isComingSoon && (
                    <button className="w-full mt-4 px-4 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-800 flex items-center justify-center gap-2">
                      Open Model
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quick Stats */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-xl p-8 text-white">
          <h2 className="text-2xl font-bold mb-6">Platform Capabilities</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <div className="text-3xl font-bold">15+</div>
              <div className="text-sm text-gray-300">Financial Models</div>
            </div>
            <div>
              <div className="text-3xl font-bold">500+</div>
              <div className="text-sm text-gray-300">Excel Functions</div>
            </div>
            <div>
              <div className="text-3xl font-bold">Real-time</div>
              <div className="text-sm text-gray-300">Data Integration</div>
            </div>
            <div>
              <div className="text-3xl font-bold">AI-Powered</div>
              <div className="text-sm text-gray-300">Analysis Engine</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}