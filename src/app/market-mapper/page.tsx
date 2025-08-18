'use client';

import { useState, useEffect } from 'react';
import MarketMapper from '@/components/MarketMapper';

// Sample market data for demonstration
const sampleMarketData = {
  market_size: {
    tam: '$50B',
    sam: '$30B',
    som: '$10B'
  },
  market_segments: {
    enterprise: {
      size: '$15B',
      percentage: 30,
      definition: '$1B+ revenue, 1000+ employees',
      characteristics: 'Fortune 500, Global 2000 companies with complex procurement processes',
      sales_cycle: '6-18 months',
      acv_range: '$100K+',
      retention: '90%+',
      approach: 'High-touch sales with custom integrations'
    },
    mid_market: {
      size: '$20B',
      percentage: 40,
      definition: '$50M-$1B revenue, 100-1000 employees',
      characteristics: 'Growing companies with established processes but need efficiency gains',
      sales_cycle: '3-9 months',
      acv_range: '$25K-$100K',
      retention: '85%+',
      approach: 'Medium-touch sales with standard + some customization'
    },
    sme: {
      size: '$15B',
      percentage: 30,
      definition: '$1M-$50M revenue, 10-100 employees',
      characteristics: 'Small businesses seeking cost-effective solutions and automation',
      sales_cycle: '1-3 months',
      acv_range: '$5K-$25K',
      retention: '80%+',
      approach: 'Self-service + light touch with standard product offering'
    }
  },
  competitors: [
    {
      name: 'Competitor A',
      market_share: '15%',
      strengths: ['Strong enterprise presence', 'Global reach', 'Established brand'],
      weaknesses: ['Limited mid-market focus', 'High pricing', 'Slow innovation'],
      positioning: 'Enterprise-focused premium solution'
    },
    {
      name: 'Competitor B',
      market_share: '12%',
      strengths: ['Mid-market expertise', 'Good customer support', 'Flexible pricing'],
      weaknesses: ['High customer churn', 'Limited enterprise features', 'Regional focus'],
      positioning: 'Mid-market specialist with good value'
    },
    {
      name: 'Competitor C',
      market_share: '8%',
      strengths: ['SME-friendly pricing', 'Easy onboarding', 'Quick implementation'],
      weaknesses: ['Limited scalability', 'Basic features', 'Low retention'],
      positioning: 'SME-focused budget solution'
    }
  ],
  market_trends: [
    'Increasing adoption of cloud-based solutions',
    'Growing demand for automation in procurement',
    'Rising focus on cost optimization',
    'Integration with existing ERP systems',
    'AI-powered analytics becoming standard',
    'Mobile-first approach gaining traction'
  ],
  opportunities: [
    'Untapped mid-market segment with 40% of TAM',
    'Growing SME digital transformation needs',
    'Enterprise modernization and legacy system replacement',
    'Cross-segment product expansion opportunities',
    'Emerging markets showing strong growth potential',
    'Integration partnerships with major platforms'
  ],
  threats: [
    'Large tech companies entering the space',
    'Economic downturn affecting purchasing decisions',
    'Regulatory changes in key markets',
    'Rapid technological changes requiring constant adaptation',
    'Increasing customer acquisition costs',
    'Competition from open-source alternatives'
  ]
};

export default function MarketMapperPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredData, setFilteredData] = useState(sampleMarketData);

  // Simulate loading for demo purposes
  useEffect(() => {
    setIsLoading(true);
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setFilteredData(sampleMarketData);
      return;
    }

    // Filter competitors based on search query
    const filtered = {
      ...sampleMarketData,
      competitors: sampleMarketData.competitors.filter(comp =>
        comp.name.toLowerCase().includes(query.toLowerCase()) ||
        comp.positioning.toLowerCase().includes(query.toLowerCase())
      )
    };
    setFilteredData(filtered);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  Market Mapper
                </h1>
                <p className="mt-2 text-gray-600">
                  Interactive market analysis and competitive landscape visualization
                </p>
              </div>
              <div className="flex items-center space-x-4">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search competitors..."
                    value={searchQuery}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="w-64 px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                  />
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                    <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </div>
                </div>
                <button
                  onClick={() => setIsLoading(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  Refresh Data
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Market Overview Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">$50B</div>
              <div className="text-sm text-gray-600">Total Addressable Market</div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">5</div>
              <div className="text-sm text-gray-600">Major Competitors</div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">45%</div>
              <div className="text-sm text-gray-600">Market Leader Share</div>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-orange-600">5</div>
              <div className="text-sm text-gray-600">Key Trends</div>
            </div>
          </div>
        </div>

        {/* Market Mapper Component */}
        <MarketMapper marketData={filteredData} isLoading={isLoading} />

        {/* Additional Insights */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Market Insights</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Market Concentration</span>
                <span className="text-sm font-medium text-blue-600">High (Top 3: 90%)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Growth Rate</span>
                <span className="text-sm font-medium text-green-600">15% YoY</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Regulatory Risk</span>
                <span className="text-sm font-medium text-yellow-600">Medium</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Technology Disruption</span>
                <span className="text-sm font-medium text-red-600">High</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Competitive Analysis</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Price Competition</span>
                <span className="text-sm font-medium text-red-600">Intense</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Feature Differentiation</span>
                <span className="text-sm font-medium text-green-600">High</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Customer Switching Costs</span>
                <span className="text-sm font-medium text-yellow-600">Medium</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Barriers to Entry</span>
                <span className="text-sm font-medium text-red-600">High</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 