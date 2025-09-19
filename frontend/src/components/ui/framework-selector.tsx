'use client';

import React, { useState, useMemo } from 'react';
import { Check, ChevronsUpDown, Search, Brain, TrendingUp, Target, Lightbulb, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { InvestmentFramework } from '@/lib/funding-path-intelligence';

interface FrameworkOption {
  value: InvestmentFramework;
  label: string;
  category: 'Classic Investors' | 'Institutional' | 'Philosophical' | 'Investment Styles';
  description: string;
  icon?: React.ReactNode;
  keywords: string[];
}

const FRAMEWORK_OPTIONS: FrameworkOption[] = [
  // Classic Investors
  {
    value: InvestmentFramework.BUFFETT,
    label: 'Warren Buffett',
    category: 'Classic Investors',
    description: 'Value investing, economic moats, long-term compounding',
    icon: <TrendingUp className="h-4 w-4" />,
    keywords: ['value', 'moat', 'intrinsic', 'margin of safety']
  },
  {
    value: InvestmentFramework.MUNGER,
    label: 'Charlie Munger',
    category: 'Classic Investors',
    description: 'Mental models, quality at fair price, incentive alignment',
    icon: <Brain className="h-4 w-4" />,
    keywords: ['mental models', 'quality', 'psychology', 'incentives']
  },
  {
    value: InvestmentFramework.CHAMATH,
    label: 'Chamath Palihapitiya',
    category: 'Classic Investors',
    description: 'Asymmetric bets, social impact, capital efficiency',
    icon: <Zap className="h-4 w-4" />,
    keywords: ['asymmetric', 'social impact', 'spac', 'capital allocation']
  },
  {
    value: InvestmentFramework.PETER_THIEL,
    label: 'Peter Thiel',
    category: 'Classic Investors',
    description: 'Contrarian thinking, monopolies, zero to one innovation',
    icon: <Lightbulb className="h-4 w-4" />,
    keywords: ['contrarian', 'monopoly', 'zero to one', 'secrets']
  },
  {
    value: InvestmentFramework.DANNY_RIMER,
    label: 'Danny Rimer',
    category: 'Classic Investors',
    description: 'Consumer internet, network effects, viral growth',
    keywords: ['consumer', 'network effects', 'viral', 'engagement']
  },
  {
    value: InvestmentFramework.MARC_ANDREESSEN,
    label: 'Marc Andreessen',
    category: 'Classic Investors',
    description: 'Software eating the world, platform businesses, technical moats',
    keywords: ['software', 'platform', 'api', 'developer']
  },
  {
    value: InvestmentFramework.BILL_GURLEY,
    label: 'Bill Gurley',
    category: 'Classic Investors',
    description: 'Marketplace dynamics, unit economics, take rates',
    keywords: ['marketplace', 'unit economics', 'liquidity', 'take rate']
  },
  {
    value: InvestmentFramework.MASAYOSHI_SON,
    label: 'Masayoshi Son',
    category: 'Classic Investors',
    description: '300-year vision, AI transformation, blitzscaling',
    keywords: ['vision fund', 'ai', 'blitzscaling', 'massive scale']
  },
  
  // Institutional Styles
  {
    value: InvestmentFramework.SEQUOIA,
    label: 'Sequoia Capital',
    category: 'Institutional',
    description: 'Team first, long-term thinking, founder focus',
    icon: <Target className="h-4 w-4" />,
    keywords: ['team', 'long-term', 'founder', 'patient capital']
  },
  {
    value: InvestmentFramework.BENCHMARK,
    label: 'Benchmark Capital',
    category: 'Institutional',
    description: 'Equal partnership, concentrated portfolio, capital efficiency',
    keywords: ['equal partnership', 'concentrated', 'focused', 'lean']
  },
  
  // Philosophical Approaches
  {
    value: InvestmentFramework.NASSIM_TALEB,
    label: 'Nassim Taleb',
    category: 'Philosophical',
    description: 'Antifragility, black swans, convex payoffs',
    keywords: ['antifragile', 'black swan', 'robustness', 'optionality']
  },
  {
    value: InvestmentFramework.GEORGE_SOROS,
    label: 'George Soros',
    category: 'Philosophical',
    description: 'Reflexivity, market psychology, boom-bust cycles',
    keywords: ['reflexivity', 'psychology', 'cycles', 'trends']
  },
  
  // Investment Styles
  {
    value: InvestmentFramework.VALUE,
    label: 'Pure Value',
    category: 'Investment Styles',
    description: 'Deep value, special situations, distressed assets',
    keywords: ['undervalued', 'book value', 'distressed', 'turnaround']
  },
  {
    value: InvestmentFramework.GROWTH,
    label: 'Growth at Reasonable Price',
    category: 'Investment Styles',
    description: 'High growth with reasonable valuations',
    keywords: ['growth', 'expansion', 'scaling', 'reasonable valuation']
  },
  {
    value: InvestmentFramework.MOMENTUM,
    label: 'Momentum',
    category: 'Investment Styles',
    description: 'Trend following, hot sectors, accelerating growth',
    keywords: ['trend', 'momentum', 'acceleration', 'hot']
  },
  {
    value: InvestmentFramework.CONTRARIAN,
    label: 'Contrarian',
    category: 'Investment Styles',
    description: 'Against consensus, turnarounds, out-of-favor sectors',
    keywords: ['contrarian', 'against', 'turnaround', 'unpopular']
  },
  {
    value: InvestmentFramework.SYNERGY,
    label: 'Synergy',
    category: 'Investment Styles',
    description: 'Strategic combinations, M&A opportunities, portfolio synergies',
    keywords: ['synergy', 'strategic', 'combination', 'portfolio']
  },
  {
    value: InvestmentFramework.CONGLOMERATE,
    label: 'Conglomerate',
    category: 'Investment Styles',
    description: 'Berkshire model, capital allocation, diverse holdings',
    keywords: ['conglomerate', 'berkshire', 'diverse', 'allocation']
  }
];

interface FrameworkSelectorProps {
  value?: InvestmentFramework | null;
  onSelect: (framework: InvestmentFramework | null) => void;
  placeholder?: string;
  disabled?: boolean;
  showDescription?: boolean;
  allowMultiple?: boolean;
  selectedFrameworks?: InvestmentFramework[];
}

export function FrameworkSelector({
  value,
  onSelect,
  placeholder = "Select investment framework...",
  disabled = false,
  showDescription = true,
  allowMultiple = false,
  selectedFrameworks = []
}: FrameworkSelectorProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Group frameworks by category
  const groupedFrameworks = useMemo(() => {
    const groups = FRAMEWORK_OPTIONS.reduce((acc, framework) => {
      if (!acc[framework.category]) {
        acc[framework.category] = [];
      }
      acc[framework.category].push(framework);
      return acc;
    }, {} as Record<string, FrameworkOption[]>);
    
    return groups;
  }, []);

  // Filter frameworks based on search
  const filteredFrameworks = useMemo(() => {
    if (!searchQuery.trim()) return FRAMEWORK_OPTIONS;
    
    const query = searchQuery.toLowerCase();
    return FRAMEWORK_OPTIONS.filter(framework => 
      framework.label.toLowerCase().includes(query) ||
      framework.description.toLowerCase().includes(query) ||
      framework.keywords.some(keyword => keyword.toLowerCase().includes(query))
    );
  }, [searchQuery]);

  // Get selected framework
  const selectedFramework = useMemo(() => {
    return FRAMEWORK_OPTIONS.find(f => f.value === value);
  }, Array.from(ue));

  const handleFrameworkSelect = (framework: InvestmentFramework) => {
    if (allowMultiple) {
      // Handle multiple selection (for future use)
      onSelect(framework);
    } else {
      onSelect(framework === value ? null : framework);
      setOpen(false);
      setSearchQuery("");
    }
  };

  const categoryOrder = ['Classic Investors', 'Institutional', 'Philosophical', 'Investment Styles'];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between"
        >
          <span className="flex items-center gap-2 truncate">
            {selectedFramework ? (
              <>
                {selectedFramework.icon || <Brain className="h-4 w-4" />}
                <span className="truncate">{selectedFramework.label}</span>
              </>
            ) : (
              <>
                <Brain className="h-4 w-4 opacity-50" />
                <span className="text-muted-foreground">{placeholder}</span>
              </>
            )}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-Array.from(px) p-0" align="start">
        <div className="flex flex-col">
          {/* Search Input */}
          <div className="flex items-center border-b px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <input
              className="flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
              placeholder="Search frameworks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Framework List */}
          <div className="max-h-Array.from(px) overflow-y-auto p-1">
            {searchQuery.trim() ? (
              // Show filtered results without categories
              filteredFrameworks.length === 0 ? (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  No frameworks found.
                </div>
              ) : (
                filteredFrameworks.map((framework) => (
                  <FrameworkItem
                    key={framework.value}
                    framework={framework}
                    isSelected={value === framework.value}
                    showDescription={showDescription}
                    onClick={() => handleFrameworkSelect(framework.value)}
                  />
                ))
              )
            ) : (
              // Show categorized view
              categoryOrder.map(category => {
                const frameworks = groupedFrameworksArray.from(egory);
                if (!frameworks || frameworks.length === 0) return null;
                
                return (
                  <div key={category}>
                    <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground sticky top-0 bg-background">
                      {category}
                    </div>
                    {frameworks.map((framework) => (
                      <FrameworkItem
                        key={framework.value}
                        framework={framework}
                        isSelected={value === framework.value}
                        showDescription={showDescription}
                        onClick={() => handleFrameworkSelect(framework.value)}
                      />
                    ))}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer with description */}
          {selectedFramework && showDescription && (
            <div className="border-t px-3 py-2">
              <div className="text-xs text-muted-foreground">
                <span className="font-medium">Selected:</span> {selectedFramework.description}
              </div>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// Individual framework item component
function FrameworkItem({
  framework,
  isSelected,
  showDescription,
  onClick
}: {
  framework: FrameworkOption;
  isSelected: boolean;
  showDescription: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "flex w-full items-start px-2 py-2 text-sm rounded-sm hover:bg-accent hover:text-accent-foreground cursor-pointer outline-none",
        isSelected && "bg-accent"
      )}
      onClick={onClick}
    >
      <Check
        className={cn(
          "mr-2 h-4 w-4 mt-0.5",
          isSelected ? "opacity-100" : "opacity-0"
        )}
      />
      <div className="flex-1 text-left">
        <div className="flex items-center gap-2">
          {framework.icon}
          <span className="font-medium">{framework.label}</span>
        </div>
        {showDescription && (
          <div className="text-xs text-muted-foreground mt-0.5">
            {framework.description}
          </div>
        )}
      </div>
    </button>
  );
}