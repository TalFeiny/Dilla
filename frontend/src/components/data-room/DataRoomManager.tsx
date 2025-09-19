'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import {
  FileText,
  Upload,
  Search,
  Lock,
  Globe,
  DollarSign,
  TrendingUp,
  Shield,
  Eye,
  Download,
  Briefcase,
  MapPin,
  BarChart3,
  FileSearch,
  Highlighter,
  Code2,
  ChevronRight,
  Building2,
  CreditCard,
  AlertCircle,
  Target
} from 'lucide-react';

interface FileChunk {
  id: string;
  content: string;
  startLine: number;
  endLine: number;
  relevance: number;
  highlights: string[];
  context: string;
}

interface DataRoomFile {
  id: string;
  name: string;
  type: string;
  size: string;
  uploadDate: string;
  chunks?: FileChunk[];
  confidential: boolean;
  tags: string[];
}

interface HedgePosition {
  id: string;
  type: string;
  instrument: string;
  notional: number;
  currency: string;
  maturity: string;
  pnl: number;
}

interface CashPosition {
  jurisdiction: string;
  currency: string;
  balance: number;
  yield: number;
  restrictions: string[];
}

export default function DataRoomManager() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedFile, setSelectedFile] = useState<DataRoomFile | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showChunks, setShowChunks] = useState(false);

  // Sample data - would come from database
  const [dataRooms] = useState([
    {
      id: 1,
      name: 'NeuralStack Series B',
      stage: 'Due Diligence',
      value: 25000000,
      jurisdiction: 'Delaware, USA',
      currencies: ['USD', 'EUR'],
      progress: 75
    },
    {
      id: 2,
      name: 'AAPL Public Position',
      stage: 'Active',
      value: 5000000,
      jurisdiction: 'NASDAQ',
      currencies: ['USD'],
      progress: 100
    }
  ]);

  const [files] = useState<DataRoomFile[]>([
    {
      id: '1',
      name: 'Q3_Financials.pdf',
      type: 'financial_statements',
      size: '2.4 MB',
      uploadDate: '2024-01-15',
      confidential: true,
      tags: ['financials', 'q3', 'audited'],
      chunks: [
        {
          id: 'c1',
          content: 'Revenue for Q3 2024 reached $45.2M, representing a 187% YoY growth...',
          startLine: 42,
          endLine: 58,
          relevance: 0.95,
          highlights: ['$45.2M', '187% YoY'],
          context: 'Financial Performance Summary'
        },
        {
          id: 'c2',
          content: 'Gross margins improved to 72%, driven by economies of scale...',
          startLine: 112,
          endLine: 125,
          relevance: 0.88,
          highlights: ['72%', 'economies of scale'],
          context: 'Margin Analysis'
        }
      ]
    },
    {
      id: '2',
      name: 'Term_Sheet_v3.docx',
      type: 'term_sheet',
      size: '156 KB',
      uploadDate: '2024-01-20',
      confidential: true,
      tags: ['legal', 'terms', 'negotiation'],
      chunks: [
        {
          id: 'c3',
          content: 'Pre-money valuation: $180M with a 2x liquidation preference...',
          startLine: 15,
          endLine: 20,
          relevance: 0.98,
          highlights: ['$180M', '2x liquidation'],
          context: 'Economic Terms'
        }
      ]
    }
  ]);

  const [hedgePositions] = useState<HedgePosition[]>([
    {
      id: 'h1',
      type: 'Currency',
      instrument: 'EUR/USD Forward',
      notional: 5000000,
      currency: 'EUR',
      maturity: '2024-06-30',
      pnl: 125000
    },
    {
      id: 'h2',
      type: 'Equity',
      instrument: 'SPX Put Option',
      notional: 2000000,
      currency: 'USD',
      maturity: '2024-03-15',
      pnl: -45000
    }
  ]);

  const [cashPositions] = useState<CashPosition[]>([
    {
      jurisdiction: 'United States',
      currency: 'USD',
      balance: 45000000,
      yield: 5.25,
      restrictions: []
    },
    {
      jurisdiction: 'European Union',
      currency: 'EUR',
      balance: 12000000,
      yield: 3.75,
      restrictions: ['AIFMD compliance required']
    },
    {
      jurisdiction: 'Singapore',
      currency: 'SGD',
      balance: 8000000,
      yield: 4.10,
      restrictions: ['MAS approval for transfers > $5M']
    }
  ]);

  const [publicPositions] = useState([
    {
      ticker: 'NVDA',
      shares: 10000,
      avgCost: 450.25,
      currentPrice: 725.50,
      pnl: 2752500,
      pnlPercent: 61.1,
      aiRating: 'BUY',
      correlation: 0.82
    },
    {
      ticker: 'PLTR',
      shares: 25000,
      avgCost: 18.50,
      currentPrice: 45.75,
      pnl: 681250,
      pnlPercent: 147.3,
      aiRating: 'HOLD',
      correlation: 0.65
    }
  ]);

  const renderFileChunks = (file: DataRoomFile) => {
    if (!file.chunks) return null;

    return (
      <div className="space-y-3 mt-4">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <FileSearch className="h-4 w-4" />
          <span>Relevant sections found in document</span>
        </div>
        {file.chunks.map((chunk) => (
          <Card key={chunk.id} className="border-l-4 border-blue-500">
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-gray-500" />
                  <span className="text-xs text-gray-500">
                    Lines {chunk.startLine}-{chunk.endLine}
                  </span>
                  <Badge variant="outline" className="text-xs">
                    {chunk.context}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  <div className="text-xs text-gray-500">Relevance</div>
                  <Progress value={chunk.relevance * 100} className="w-20 h-2" />
                </div>
              </div>
              
              <div className="bg-gray-50 p-3 rounded text-sm font-mono">
                {chunk.content.split(' ').map((word, i) => (
                  <span key={i}>
                    {chunk.highlights.includes(word) ? (
                      <mark className="bg-yellow-200 px-1">{word}</mark>
                    ) : (
                      word
                    )}{' '}
                  </span>
                ))}
              </div>

              <div className="flex items-center gap-4 mt-3">
                <Button size="sm" variant="ghost">
                  <Eye className="h-3 w-3 mr-1" />
                  View Context
                </Button>
                <Button size="sm" variant="ghost">
                  <Highlighter className="h-3 w-3 mr-1" />
                  Highlight All
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Data Room & Deal Management</h2>
          <p className="text-gray-600">Manage deals, documents, and multi-jurisdiction transactions</p>
        </div>
        <div className="flex gap-2">
          <Button>
            <Upload className="h-4 w-4 mr-2" />
            Upload Documents
          </Button>
          <Button variant="outline">
            <Briefcase className="h-4 w-4 mr-2" />
            New Deal
          </Button>
        </div>
      </div>

      {/* Active Deals */}
      <div className="grid grid-cols-2 gap-4">
        {dataRooms.map((room) => (
          <Card key={room.id}>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-lg">{room.name}</CardTitle>
                  <CardDescription>{room.stage}</CardDescription>
                </div>
                <Badge className="bg-green-100 text-green-700">Active</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Deal Value</span>
                  <span className="font-semibold">${(room.value / 1000000).toFixed(1)}M</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Jurisdiction</span>
                  <div className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    <span>{room.jurisdiction}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Currencies</span>
                  <div className="flex gap-1">
                    {room.currencies.map(curr => (
                      <Badge key={curr} variant="outline" className="text-xs">
                        {curr}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600">Progress</span>
                    <span className="font-medium">{room.progress}%</span>
                  </div>
                  <Progress value={room.progress} className="h-2" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-6 w-full">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="mapping">Market Mapping</TabsTrigger>
          <TabsTrigger value="hedging">Hedging</TabsTrigger>
          <TabsTrigger value="cash">Cash Management</TabsTrigger>
          <TabsTrigger value="public">Public Markets</TabsTrigger>
        </TabsList>

        {/* Documents Tab with File Chunks */}
        <TabsContent value="documents" className="space-y-4">
          <div className="flex items-center gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search documents..."
                className="w-full pl-10 pr-4 py-2 border rounded-lg"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Button variant="outline" onClick={() => setShowChunks(!showChunks)}>
              <FileSearch className="h-4 w-4 mr-2" />
              {showChunks ? 'Hide' : 'Show'} Chunks
            </Button>
          </div>

          <div className="grid gap-4">
            {files.map((file) => (
              <Card 
                key={file.id} 
                className={`cursor-pointer transition-all ${
                  selectedFile?.id === file.id ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setSelectedFile(file)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <FileText className="h-5 w-5 text-gray-500 mt-1" />
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium">{file.name}</p>
                          {file.confidential && (
                            <Lock className="h-3 w-3 text-red-500" />
                          )}
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
                          <span>{file.size}</span>
                          <span>{file.uploadDate}</span>
                        </div>
                        <div className="flex gap-1 mt-2">
                          {file.tags.map(tag => (
                            <Badge key={tag} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="ghost">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {showChunks && selectedFile?.id === file.id && renderFileChunks(file)}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Market Mapping Tab */}
        <TabsContent value="mapping" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Live Market Mapping & Competitive Intelligence</CardTitle>
              <CardDescription>AI-powered market analysis and competitive positioning</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-6">
                {/* Market Map Visualization */}
                <div className="space-y-4">
                  <h3 className="font-semibold">AI Infrastructure Market Map</h3>
                  <div className="bg-gradient-to-br from-gray-50 to-gray-100 p-6 rounded-lg border">
                    <div className="grid grid-cols-2 gap-4">
                      {/* Quadrant 1: High Growth, High Maturity */}
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-green-700 mb-2">Leaders (High Growth + Mature)</div>
                        <div className="space-y-1">
                          <div className="bg-green-100 p-2 rounded text-xs border border-green-200">
                            <div className="font-medium">NVIDIA</div>
                            <div className="text-gray-600">GPU Infrastructure</div>
                            <div className="text-green-700 text-xs mt-1">$2.7T valuation • 200%+ growth</div>
                          </div>
                          <div className="bg-green-100 p-2 rounded text-xs border border-green-200">
                            <div className="font-medium">OpenAI</div>
                            <div className="text-gray-600">LLM Platform</div>
                            <div className="text-green-700 text-xs mt-1">$157B valuation • 1000%+ growth</div>
                          </div>
                        </div>
                      </div>

                      {/* Quadrant 2: High Growth, Low Maturity */}
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-blue-700 mb-2">Challengers (High Growth + Emerging)</div>
                        <div className="space-y-1">
                          <div className="bg-blue-100 p-2 rounded text-xs border border-blue-200">
                            <div className="font-medium">Anthropic</div>
                            <div className="text-gray-600">AI Safety & LLMs</div>
                            <div className="text-blue-700 text-xs mt-1">$41B valuation • 500%+ growth</div>
                          </div>
                          <div className="bg-blue-100 p-2 rounded text-xs border border-blue-200">
                            <div className="font-medium">Databricks</div>
                            <div className="text-gray-600">Data + AI Platform</div>
                            <div className="text-blue-700 text-xs mt-1">$43B valuation • 60% growth</div>
                          </div>
                          <div className="bg-yellow-100 p-2 rounded text-xs border border-yellow-200">
                            <div className="font-medium">🎯 NeuralStack</div>
                            <div className="text-gray-600">GPU Optimization</div>
                            <div className="text-yellow-700 text-xs mt-1">$180M valuation • 200% growth • OUR TARGET</div>
                          </div>
                        </div>
                      </div>

                      {/* Quadrant 3: Low Growth, High Maturity */}
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-gray-700 mb-2">Established (Mature + Stable)</div>
                        <div className="space-y-1">
                          <div className="bg-gray-100 p-2 rounded text-xs border border-gray-200">
                            <div className="font-medium">Google Cloud AI</div>
                            <div className="text-gray-600">Enterprise AI</div>
                            <div className="text-gray-700 text-xs mt-1">~$1.8T parent • 15% growth</div>
                          </div>
                          <div className="bg-gray-100 p-2 rounded text-xs border border-gray-200">
                            <div className="font-medium">AWS AI Services</div>
                            <div className="text-gray-600">Cloud AI</div>
                            <div className="text-gray-700 text-xs mt-1">~$1.5T parent • 12% growth</div>
                          </div>
                        </div>
                      </div>

                      {/* Quadrant 4: Low Growth, Low Maturity */}
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-red-700 mb-2">Laggards (Emerging + Slow)</div>
                        <div className="space-y-1">
                          <div className="bg-red-100 p-2 rounded text-xs border border-red-200">
                            <div className="font-medium">Traditional AI</div>
                            <div className="text-gray-600">Legacy Vendors</div>
                            <div className="text-red-700 text-xs mt-1">Mixed valuations • &lt;15% growth</div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-4 text-xs text-gray-600">
                      Y-axis: Market Maturity • X-axis: Revenue Growth Rate
                    </div>
                  </div>
                </div>

                {/* Competitive Analysis */}
                <div className="space-y-4">
                  <h3 className="font-semibold">Competitive Intelligence</h3>
                  
                  <Card className="p-4">
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Target className="h-4 w-4 text-blue-600" />
                      NeuralStack Positioning Analysis
                    </h4>
                    
                    <div className="space-y-3">
                      <div className="flex justify-between items-center p-2 bg-green-50 rounded">
                        <span className="text-sm font-medium">Technical Moat</span>
                        <Badge className="bg-green-600">Strong</Badge>
                      </div>
                      
                      <div className="flex justify-between items-center p-2 bg-yellow-50 rounded">
                        <span className="text-sm font-medium">Market Position</span>
                        <Badge className="bg-yellow-600">Challenger</Badge>
                      </div>
                      
                      <div className="flex justify-between items-center p-2 bg-green-50 rounded">
                        <span className="text-sm font-medium">Growth Vector</span>
                        <Badge className="bg-green-600">Excellent</Badge>
                      </div>
                      
                      <div className="flex justify-between items-center p-2 bg-blue-50 rounded">
                        <span className="text-sm font-medium">Valuation vs Peers</span>
                        <Badge className="bg-blue-600">Undervalued</Badge>
                      </div>
                    </div>
                    
                    <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertCircle className="h-4 w-4 text-gray-600" />
                        <span className="text-sm font-medium text-gray-900">Agent Alpha Signal</span>
                      </div>
                      <p className="text-sm text-gray-800">
                        Trading at 8x ARR vs sector median of 15x. GPU optimization space heating up. 
                        NVIDIA partnership creates massive moat. <strong>Expected 92% IRR over 24 months.</strong>
                      </p>
                    </div>
                  </Card>

                  <Card className="p-4">
                    <h4 className="font-medium mb-3">Market Dynamics</h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span>TAM expanding 40% annually ($500B by 2030)</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                        <span>Increasing enterprise GPU adoption</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                        <span>Risk: NVIDIA backward integration</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                        <span>Opportunity: AMD/Intel partnerships</span>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>
              
              {/* Live Market Feed */}
              <div className="mt-6">
                <h3 className="font-semibold mb-3">Live Market Intelligence</h3>
                <div className="grid grid-cols-3 gap-4">
                  <Card className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium">Recent Funding</span>
                    </div>
                    <p className="text-xs text-gray-600">AI Infrastructure sector raised $2.3B in Q4</p>
                    <p className="text-xs text-green-600 mt-1">↑ 340% vs Q4 2023</p>
                  </Card>
                  
                  <Card className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Building2 className="h-4 w-4 text-blue-600" />
                      <span className="text-sm font-medium">M&A Activity</span>
                    </div>
                    <p className="text-xs text-gray-600">12 strategic acquisitions this quarter</p>
                    <p className="text-xs text-blue-600 mt-1">Avg 12x ARR multiple</p>
                  </Card>
                  
                  <Card className="p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <BarChart3 className="h-4 w-4 text-purple-600" />
                      <span className="text-sm font-medium">Valuations</span>
                    </div>
                    <p className="text-xs text-gray-600">Median Series B at 15x ARR</p>
                    <p className="text-xs text-purple-600 mt-1">NeuralStack at 8x = 47% discount</p>
                  </Card>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Hedging Tab */}
        <TabsContent value="hedging" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active Hedge Positions</CardTitle>
              <CardDescription>Managing currency and market risk across jurisdictions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {hedgePositions.map((position) => (
                  <div key={position.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center gap-4">
                      <Shield className="h-5 w-5 text-blue-500" />
                      <div>
                        <p className="font-medium">{position.instrument}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <span>{position.type}</span>
                          <span>•</span>
                          <span>Expires {position.maturity}</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">
                        {position.currency} {(position.notional / 1000000).toFixed(1)}M
                      </p>
                      <p className={`text-sm ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {position.pnl >= 0 ? '+' : ''}{(position.pnl / 1000).toFixed(0)}K P&L
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="h-4 w-4 text-blue-600" />
                  <p className="font-medium text-blue-900">Hedging Recommendations</p>
                </div>
                <ul className="space-y-1 text-sm text-blue-800">
                  <li>• Consider adding GBP hedge for UK expansion (£3M exposure)</li>
                  <li>• Interest rate swap recommended for floating rate debt</li>
                  <li>• Equity collar strategy for concentrated NVDA position</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cash Management Tab */}
        <TabsContent value="cash" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Multi-Jurisdiction Cash Positions</CardTitle>
              <CardDescription>Optimize yield while managing regulatory constraints</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {cashPositions.map((position, index) => (
                  <div key={index} className="p-4 border rounded-lg">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-5 w-5 text-gray-500" />
                        <div>
                          <p className="font-medium">{position.jurisdiction}</p>
                          <p className="text-sm text-gray-500">{position.currency}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-xl font-bold">
                          {position.currency} {(position.balance / 1000000).toFixed(1)}M
                        </p>
                        <p className="text-sm text-green-600">
                          {position.yield}% yield
                        </p>
                      </div>
                    </div>
                    
                    {position.restrictions.length > 0 && (
                      <div className="bg-yellow-50 p-2 rounded text-xs text-yellow-800">
                        {position.restrictions.join(' • ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-6 grid grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm text-gray-600">Total Cash</p>
                  <p className="text-xl font-bold">$65M</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Weighted Yield</p>
                  <p className="text-xl font-bold text-green-600">4.8%</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Annual Income</p>
                  <p className="text-xl font-bold">$3.1M</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Public Markets Tab */}
        <TabsContent value="public" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Public Market Positions</CardTitle>
              <CardDescription>Liquid positions with AI-driven analysis</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {publicPositions.map((position) => (
                  <div key={position.ticker} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                        <span className="font-bold text-blue-600">{position.ticker}</span>
                      </div>
                      <div>
                        <p className="font-medium">{position.shares.toLocaleString()} shares</p>
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <span>Avg: ${position.avgCost}</span>
                          <ChevronRight className="h-3 w-3" />
                          <span>Current: ${position.currentPrice}</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className={`text-lg font-bold ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {position.pnl >= 0 ? '+' : ''}${(position.pnl / 1000000).toFixed(2)}M
                        </p>
                        <p className={`text-sm ${position.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {position.pnlPercent >= 0 ? '+' : ''}{position.pnlPercent.toFixed(1)}%
                        </p>
                      </div>
                      
                      <div className="text-center">
                        <Badge className={
                          position.aiRating === 'BUY' ? 'bg-green-100 text-green-700' :
                          position.aiRating === 'SELL' ? 'bg-red-100 text-red-700' :
                          'bg-yellow-100 text-yellow-700'
                        }>
                          AI: {position.aiRating}
                        </Badge>
                        <p className="text-xs text-gray-500 mt-1">
                          Corr: {position.correlation}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg">
                <p className="font-medium mb-2">Yahoo Finance Integration Active</p>
                <div className="grid grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600">Portfolio Beta</p>
                    <p className="font-bold">1.15</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Sharpe Ratio</p>
                    <p className="font-bold">2.3</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Correlation</p>
                    <p className="font-bold">0.72</p>
                  </div>
                  <div>
                    <p className="text-gray-600">VaR (95%)</p>
                    <p className="font-bold text-red-600">-$1.2M</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}