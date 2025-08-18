'use client';

import { useState, useEffect } from 'react';

interface MarketData {
  market_size: {
    tam: string;
    sam: string;
    som: string;
  };
  market_segments: {
    enterprise: {
      size: string;
      percentage: number;
      definition: string;
      characteristics: string;
      sales_cycle: string;
      acv_range: string;
      retention: string;
      approach: string;
    };
    mid_market: {
      size: string;
      percentage: number;
      definition: string;
      characteristics: string;
      sales_cycle: string;
      acv_range: string;
      retention: string;
      approach: string;
    };
    sme: {
      size: string;
      percentage: number;
      definition: string;
      characteristics: string;
      sales_cycle: string;
      acv_range: string;
      retention: string;
      approach: string;
    };
  };
  competitors: Array<{
    name: string;
    market_share: string;
    strengths: string[];
    weaknesses: string[];
    positioning: string;
  }>;
  market_trends: string[];
  opportunities: string[];
  threats: string[];
}

interface MarketMapperProps {
  marketData: MarketData;
  isLoading?: boolean;
}

export default function MarketMapper({ marketData, isLoading = false }: MarketMapperProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedCompetitor, setSelectedCompetitor] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded w-5/6"></div>
            <div className="h-4 bg-gray-200 rounded w-4/6"></div>
          </div>
        </div>
      </div>
    );
  }

  const renderMarketSizeChart = () => (
    <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Market Size Pyramid (TAM SAM SOM)</h3>
      
      {/* Market Size Pyramid Visualization */}
      <div className="space-y-6">
        {/* TAM - Total Addressable Market */}
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">TAM (Total Addressable Market)</span>
            <span className="text-lg font-bold text-gray-700">{marketData.market_size.tam}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 relative overflow-hidden">
            <div className="bg-gradient-to-r from-gray-500 to-gray-600 h-4 rounded-full transition-all duration-500" style={{ width: '100%' }}>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-pulse"></div>
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-600">
            The total market demand for your product/service category
          </div>
        </div>
        
        {/* SAM - Serviceable Addressable Market */}
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">SAM (Serviceable Addressable Market)</span>
            <span className="text-lg font-bold text-gray-600">{marketData.market_size.sam}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 relative overflow-hidden">
            <div className="bg-gradient-to-r from-gray-600 to-gray-700 h-4 rounded-full transition-all duration-500" style={{ width: '60%' }}>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-pulse"></div>
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-600">
            The portion of TAM that your business model can realistically serve
          </div>
        </div>
        
        {/* SOM - Serviceable Obtainable Market */}
        <div className="relative">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">SOM (Serviceable Obtainable Market)</span>
            <span className="text-lg font-bold text-gray-700">{marketData.market_size.som}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 relative overflow-hidden">
            <div className="bg-gradient-to-r from-gray-700 to-gray-800 h-4 rounded-full transition-all duration-500" style={{ width: '20%' }}>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-pulse"></div>
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-600">
            The realistic market share you can capture in 3-5 years
          </div>
        </div>
      </div>



      {/* Market Size Metrics */}
      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-600">{marketData.market_size.tam}</div>
            <div className="text-sm text-gray-600">TAM</div>
            <div className="text-xs text-gray-500 mt-1">Total Market</div>
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-600">{marketData.market_size.sam}</div>
            <div className="text-sm text-gray-600">SAM</div>
            <div className="text-xs text-gray-500 mt-1">Serviceable Market</div>
          </div>
        </div>
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-700">{marketData.market_size.som}</div>
            <div className="text-sm text-gray-600">SOM</div>
            <div className="text-xs text-gray-500 mt-1">Obtainable Market</div>
          </div>
        </div>
      </div>

      {/* Market Penetration Analysis */}
      <div className="mt-6 bg-white rounded-lg p-4 border border-gray-200">
        <h4 className="font-semibold text-gray-900 mb-3">Market Penetration Analysis</h4>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">SAM/TAM Ratio:</span>
            <span className="font-medium text-gray-600">60%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">SOM/SAM Ratio:</span>
            <span className="font-medium text-gray-600">33%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">SOM/TAM Ratio:</span>
            <span className="font-medium text-gray-700">20%</span>
          </div>
        </div>
        <div className="mt-3 p-3 bg-yellow-50 rounded-lg">
          <div className="text-sm text-yellow-800">
            <strong>Insight:</strong> Your SOM represents 20% of the total market, indicating strong market opportunity with realistic growth potential.
          </div>
        </div>
      </div>
    </div>
  );

  const renderCompetitiveLandscape = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Competitive Landscape</h3>
      
      {/* Competitor Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {marketData.competitors.map((competitor, index) => (
          <div
            key={index}
            className={`bg-white border-2 rounded-lg p-4 cursor-pointer transition-all ${
              selectedCompetitor === competitor.name
                ? 'border-gray-500 shadow-lg'
                : 'border-gray-200 hover:border-gray-300'
            }`}
            onClick={() => setSelectedCompetitor(competitor.name)}
          >
            <h4 className="font-semibold text-gray-900 mb-2">{competitor.name}</h4>
            <div className="text-sm text-gray-600 mb-3">
              Market Share: <span className="font-medium">{competitor.market_share}</span>
            </div>
            <div className="text-xs text-gray-500 mb-2">
              <strong>Positioning:</strong> {competitor.positioning}
            </div>
            
            {/* Quick Stats */}
            <div className="flex justify-between text-xs">
              <span className="text-green-600">✓ {competitor.strengths.length} strengths</span>
              <span className="text-red-600">✗ {competitor.weaknesses.length} weaknesses</span>
            </div>
          </div>
        ))}
      </div>

      {/* Selected Competitor Details */}
      {selectedCompetitor && (
        <div className="bg-gray-50 rounded-lg p-6 mt-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-4">
            {selectedCompetitor} - Detailed Analysis
          </h4>
          {(() => {
            const competitor = marketData.competitors.find(c => c.name === selectedCompetitor);
            if (!competitor) return null;
            
            return (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h5 className="font-medium text-green-700 mb-2">Strengths</h5>
                  <ul className="space-y-1">
                    {competitor.strengths.map((strength, index) => (
                      <li key={index} className="text-sm text-gray-700 flex items-start">
                        <span className="text-green-500 mr-2">✓</span>
                        {strength}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h5 className="font-medium text-red-700 mb-2">Weaknesses</h5>
                  <ul className="space-y-1">
                    {competitor.weaknesses.map((weakness, index) => (
                      <li key={index} className="text-sm text-gray-700 flex items-start">
                        <span className="text-red-500 mr-2">✗</span>
                        {weakness}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );

  const renderMarketTrends = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Market Trends & Analysis</h3>
      
      {/* Market Trends */}
      <div className="bg-blue-50 rounded-lg p-6">
        <h4 className="font-semibold text-blue-900 mb-3">Key Market Trends</h4>
        <div className="space-y-2">
          {marketData.market_trends.map((trend, index) => (
            <div key={index} className="flex items-start">
              <span className="text-blue-500 mr-2 mt-1">→</span>
              <span className="text-sm text-blue-800">{trend}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Opportunities & Threats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-green-50 rounded-lg p-6">
          <h4 className="font-semibold text-green-900 mb-3">Market Opportunities</h4>
          <div className="space-y-2">
            {marketData.opportunities.map((opportunity, index) => (
              <div key={index} className="flex items-start">
                <span className="text-green-500 mr-2 mt-1">💡</span>
                <span className="text-sm text-green-800">{opportunity}</span>
              </div>
            ))}
          </div>
        </div>
        
        <div className="bg-red-50 rounded-lg p-6">
          <h4 className="font-semibold text-red-900 mb-3">Market Threats</h4>
          <div className="space-y-2">
            {marketData.threats.map((threat, index) => (
              <div key={index} className="flex items-start">
                <span className="text-red-500 mr-2 mt-1">⚠️</span>
                <span className="text-sm text-red-800">{threat}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderMarketSegments = () => (
    <div className="space-y-6">
      {/* Market Segments Overview */}
      <div className="bg-white rounded-lg p-6 border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Market Segments by Company Size</h3>
        
        <div className="space-y-6">
          {/* Enterprise Segment */}
          <div className="border-l-4 border-red-500 pl-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h5 className="font-medium text-gray-900">Enterprise</h5>
                <p className="text-sm text-gray-600">{marketData.market_segments?.enterprise?.definition || '$1B+ revenue, 1000+ employees'}</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-red-600">{marketData.market_segments?.enterprise?.size || '$15B'}</div>
                <div className="text-xs text-gray-500">{marketData.market_segments?.enterprise?.percentage || 30}% of TAM</div>
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-red-500 h-2 rounded-full" style={{ width: `${marketData.market_segments?.enterprise?.percentage || 30}%` }}></div>
            </div>
            <div className="mt-1 text-xs text-gray-500">
              {marketData.market_segments?.enterprise?.characteristics || 'Fortune 500, Global 2000 companies with complex procurement processes'}
            </div>
          </div>

          {/* Mid-Market Segment */}
          <div className="border-l-4 border-orange-500 pl-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h5 className="font-medium text-gray-900">Mid-Market</h5>
                <p className="text-sm text-gray-600">{marketData.market_segments?.mid_market?.definition || '$50M-$1B revenue, 100-1000 employees'}</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-orange-600">{marketData.market_segments?.mid_market?.size || '$20B'}</div>
                <div className="text-xs text-gray-500">{marketData.market_segments?.mid_market?.percentage || 40}% of TAM</div>
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-orange-500 h-2 rounded-full" style={{ width: `${marketData.market_segments?.mid_market?.percentage || 40}%` }}></div>
            </div>
            <div className="mt-1 text-xs text-gray-500">
              {marketData.market_segments?.mid_market?.characteristics || 'Growing companies with established processes but need efficiency gains'}
            </div>
          </div>

          {/* SME Segment */}
          <div className="border-l-4 border-green-500 pl-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h5 className="font-medium text-gray-900">SME (Small & Medium Enterprise)</h5>
                <p className="text-sm text-gray-600">{marketData.market_segments?.sme?.definition || '$1M-$50M revenue, 10-100 employees'}</p>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-green-600">{marketData.market_segments?.sme?.size || '$15B'}</div>
                <div className="text-xs text-gray-500">{marketData.market_segments?.sme?.percentage || 30}% of TAM</div>
              </div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-green-500 h-2 rounded-full" style={{ width: `${marketData.market_segments?.sme?.percentage || 30}%` }}></div>
            </div>
            <div className="mt-1 text-xs text-gray-500">
              {marketData.market_segments?.sme?.characteristics || 'Small businesses seeking cost-effective solutions and automation'}
            </div>
          </div>
        </div>
      </div>

      {/* Segment Targeting Strategy */}
      <div className="bg-white rounded-lg p-6 border border-gray-200">
        <h4 className="font-semibold text-gray-900 mb-4">Targeting Strategy by Segment</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-4 border border-red-200 rounded-lg bg-red-50">
            <div className="font-medium text-red-600 mb-3">Enterprise</div>
            <div className="space-y-2 text-sm text-gray-700">
              <div><strong>Sales Cycle:</strong> {marketData.market_segments?.enterprise?.sales_cycle || '6-18 months'}</div>
              <div><strong>ACV Range:</strong> {marketData.market_segments?.enterprise?.acv_range || '$100K+'}</div>
              <div><strong>Retention:</strong> {marketData.market_segments?.enterprise?.retention || '90%+'}</div>
              <div><strong>Approach:</strong> {marketData.market_segments?.enterprise?.approach || 'High-touch sales with custom integrations'}</div>
            </div>
          </div>
          <div className="p-4 border border-orange-200 rounded-lg bg-orange-50">
            <div className="font-medium text-orange-600 mb-3">Mid-Market</div>
            <div className="space-y-2 text-sm text-gray-700">
              <div><strong>Sales Cycle:</strong> {marketData.market_segments?.mid_market?.sales_cycle || '3-9 months'}</div>
              <div><strong>ACV Range:</strong> {marketData.market_segments?.mid_market?.acv_range || '$25K-$100K'}</div>
              <div><strong>Retention:</strong> {marketData.market_segments?.mid_market?.retention || '85%+'}</div>
              <div><strong>Approach:</strong> {marketData.market_segments?.mid_market?.approach || 'Medium-touch sales with standard + some customization'}</div>
            </div>
          </div>
          <div className="p-4 border border-green-200 rounded-lg bg-green-50">
            <div className="font-medium text-green-600 mb-3">SME</div>
            <div className="space-y-2 text-sm text-gray-700">
              <div><strong>Sales Cycle:</strong> {marketData.market_segments?.sme?.sales_cycle || '1-3 months'}</div>
              <div><strong>ACV Range:</strong> {marketData.market_segments?.sme?.acv_range || '$5K-$25K'}</div>
              <div><strong>Retention:</strong> {marketData.market_segments?.sme?.retention || '80%+'}</div>
              <div><strong>Approach:</strong> {marketData.market_segments?.sme?.approach || 'Self-service + light touch with standard product offering'}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Segment Opportunity Analysis */}
      <div className="bg-white rounded-lg p-6 border border-gray-200">
        <h4 className="font-semibold text-gray-900 mb-4">Segment Opportunity Analysis</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h5 className="font-medium text-gray-900 mb-3">Market Penetration by Segment</h5>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Enterprise</span>
                <div className="flex items-center space-x-2">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div className="bg-red-500 h-2 rounded-full" style={{ width: '15%' }}></div>
                  </div>
                  <span className="text-sm font-medium">15%</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Mid-Market</span>
                <div className="flex items-center space-x-2">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div className="bg-orange-500 h-2 rounded-full" style={{ width: '8%' }}></div>
                  </div>
                  <span className="text-sm font-medium">8%</span>
                </div>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">SME</span>
                <div className="flex items-center space-x-2">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div className="bg-green-500 h-2 rounded-full" style={{ width: '5%' }}></div>
                  </div>
                  <span className="text-sm font-medium">5%</span>
                </div>
              </div>
            </div>
          </div>
          <div>
            <h5 className="font-medium text-gray-900 mb-3">Growth Opportunities</h5>
            <div className="space-y-2 text-sm">
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0"></div>
                <div>
                  <strong>Enterprise:</strong> Focus on legacy system replacement and digital transformation
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full mt-2 flex-shrink-0"></div>
                <div>
                  <strong>Mid-Market:</strong> Largest untapped opportunity with 40% of TAM
                </div>
              </div>
              <div className="flex items-start space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                <div>
                  <strong>SME:</strong> Digital transformation wave creating new demand
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Navigation Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'overview'
                ? 'border-gray-500 text-gray-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Market Overview
          </button>
          <button
            onClick={() => setActiveTab('segments')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'segments'
                ? 'border-gray-500 text-gray-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Market Segments
          </button>
          <button
            onClick={() => setActiveTab('competitors')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'competitors'
                ? 'border-gray-500 text-gray-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Competitive Landscape
          </button>
          <button
            onClick={() => setActiveTab('trends')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'trends'
                ? 'border-gray-500 text-gray-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Market Trends
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="p-6">
        {activeTab === 'overview' && renderMarketSizeChart()}
        {activeTab === 'segments' && renderMarketSegments()}
        {activeTab === 'competitors' && renderCompetitiveLandscape()}
        {activeTab === 'trends' && renderMarketTrends()}
      </div>
    </div>
  );
} 