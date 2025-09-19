'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { 
  MessageSquare, 
  Calendar, 
  TrendingUp, 
  AlertCircle, 
  Building2,
  DollarSign,
  Clock,
  Users,
  ChevronRight,
  Mail,
  Phone,
  Video,
  FileText,
  BarChart3,
  Activity,
  Target,
  Info
} from 'lucide-react';

interface PortfolioCompany {
  id: string;
  name: string;
  sector: string;
  investment_date: string;
  initial_investment: number;
  current_valuation: number;
  ownership_percentage: number;
  
  // Communication tracking
  last_communication_date?: string;
  last_communication_type?: string;
  last_communication_summary?: string;
  days_since_contact?: number;
  communication_status: string;
  follow_up_required: boolean;
  follow_up_date?: string;
  
  // Valuation methods
  dcf_valuation?: number;
  comps_valuation?: number;
  precedent_valuation?: number;
  vc_method_valuation?: number;
  pwerm_valuation?: number;
  mark_to_market_valuation?: number;
  
  // Metrics
  arr?: number;
  growth_rate?: number;
  burn_rate?: number;
  runway_months?: number;
  ltv_cac_ratio?: number;
  
  // Status
  exit_status: string;
  board_seat: boolean;
  lead_investor: boolean;
}

interface CommunicationLog {
  type: string;
  date: string;
  subject?: string;
  summary?: string;
  participants?: string[];
  follow_up_required?: boolean;
  follow_up_date?: string;
  sentiment?: string;
}

const getCommunicationIcon = (type: string) => {
  switch(type) {
    case 'email': return <Mail className="w-4 h-4" />;
    case 'call': return <Phone className="w-4 h-4" />;
    case 'meeting': return <Users className="w-4 h-4" />;
    case 'video': return <Video className="w-4 h-4" />;
    case 'quarterly_report': return <FileText className="w-4 h-4" />;
    default: return <MessageSquare className="w-4 h-4" />;
  }
};

const getCommunicationStatusColor = (status: string) => {
  switch(status) {
    case 'recent': return 'bg-green-100 text-green-800';
    case 'normal': return 'bg-blue-100 text-blue-800';
    case 'attention_needed': return 'bg-yellow-100 text-yellow-800';
    case 'overdue': return 'bg-red-100 text-red-800';
    case 'no_contact': return 'bg-gray-100 text-gray-800';
    default: return 'bg-gray-100 text-gray-800';
  }
};

const getValuationMethodName = (method: string) => {
  const names: Record<string, string> = {
    dcf_valuation: 'DCF',
    comps_valuation: 'Comps',
    precedent_valuation: 'Precedent',
    vc_method_valuation: 'VC Method',
    pwerm_valuation: 'PWERM',
    mark_to_market_valuation: 'Mark-to-Market'
  };
  return names[method] || method;
};

export default function EnhancedPortfolioPage() {
  const [portfolios, setPortfolios] = useState<any[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<PortfolioCompany | null>(null);
  const [showCommunicationModal, setShowCommunicationModal] = useState(false);
  const [showValuationModal, setShowValuationModal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  const [communicationLog, setCommunicationLog] = useState<CommunicationLog>({
    type: 'email',
    date: new Date().toISOString().split('T')[0],
    subject: '',
    summary: '',
    participants: [],
    follow_up_required: false,
    sentiment: 'neutral'
  });

  const [valuationData, setValuationData] = useState({
    method: 'dcf',
    date: new Date().toISOString().split('T')[0],
    amount: 0,
    revenue: 0,
    arr: 0,
    growth_rate: 0,
    confidence_level: 'medium',
    notes: ''
  });

  const loadPortfolios = async () => {
    try {
      const response = await fetch('/api/v2/portfolio/enhanced');
      if (response.ok) {
        const data = await response.json();
        setPortfolios(data.portfolios || []);
      }
    } catch (error) {
      console.error('Error loading portfolios:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolios();
  }, []);

  const handleLogCommunication = async () => {
    if (!selectedCompany) return;
    
    try {
      const response = await fetch(`/api/v2/portfolio/companies/${selectedCompany.id}/communication`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(communicationLog)
      });
      
      if (response.ok) {
        setShowCommunicationModal(false);
        loadPortfolios();
      }
    } catch (error) {
      console.error('Error logging communication:', error);
    }
  };

  const handleAddValuation = async () => {
    if (!selectedCompany) return;
    
    try {
      const response = await fetch(`/api/v2/portfolio/companies/${selectedCompany.id}/valuation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(valuationData)
      });
      
      if (response.ok) {
        setShowValuationModal(false);
        loadPortfolios();
      }
    } catch (error) {
      console.error('Error adding valuation:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  // Mock data for demonstration
  const mockPortfolio = {
    name: "Growth Fund I",
    companies: [
      {
        id: "1",
        name: "DataSync Inc",
        sector: "Data Infrastructure",
        investment_date: "2021-03-15",
        initial_investment: 5000000,
        current_valuation: 15000000,
        ownership_percentage: 12.5,
        last_communication_date: "2024-01-10",
        last_communication_type: "quarterly_report",
        last_communication_summary: "Q4 results strong, ARR up 50% YoY",
        days_since_contact: 5,
        communication_status: "recent",
        follow_up_required: false,
        dcf_valuation: 16000000,
        comps_valuation: 14500000,
        vc_method_valuation: 18000000,
        pwerm_valuation: 15000000,
        arr: 10000000,
        growth_rate: 0.5,
        runway_months: 24,
        exit_status: "active",
        board_seat: true,
        lead_investor: true
      },
      {
        id: "2",
        name: "CloudOps Platform",
        sector: "DevOps",
        investment_date: "2021-06-20",
        initial_investment: 3000000,
        current_valuation: 8000000,
        ownership_percentage: 15.0,
        last_communication_date: "2023-12-15",
        last_communication_type: "email",
        last_communication_summary: "Preparing Series B fundraise",
        days_since_contact: 31,
        communication_status: "attention_needed",
        follow_up_required: true,
        follow_up_date: "2024-01-20",
        dcf_valuation: 8500000,
        comps_valuation: 7800000,
        arr: 5000000,
        growth_rate: 0.3,
        runway_months: 18,
        exit_status: "active",
        board_seat: false,
        lead_investor: false
      },
      {
        id: "3",
        name: "AI Analytics Co",
        sector: "AI/ML",
        investment_date: "2022-01-10",
        initial_investment: 7000000,
        current_valuation: 12000000,
        ownership_percentage: 18.0,
        days_since_contact: 65,
        communication_status: "overdue",
        follow_up_required: true,
        arr: 3000000,
        growth_rate: 0.8,
        exit_status: "active",
        board_seat: true,
        lead_investor: true
      }
    ]
  };

  const companies = mockPortfolio.companies as PortfolioCompany[];

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">{mockPortfolio.name}</h1>
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <div className="flex items-center gap-1">
            <Building2 className="w-4 h-4" />
            <span>{companies.length} Companies</span>
          </div>
          <div className="flex items-center gap-1">
            <DollarSign className="w-4 h-4" />
            <span>${companies.reduce((sum, c) => sum + c.current_valuation, 0).toLocaleString()} Total Value</span>
          </div>
          <div className="flex items-center gap-1">
            <Activity className="w-4 h-4" />
            <span>{companies.filter(c => c.communication_status === 'attention_needed' || c.communication_status === 'overdue').length} Need Attention</span>
          </div>
        </div>
      </div>

      {/* Communication Summary Bar */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex justify-between items-center">
            <div className="flex gap-8">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-sm">Recent Contact: {companies.filter(c => c.communication_status === 'recent').length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-sm">Attention Needed: {companies.filter(c => c.communication_status === 'attention_needed').length}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-sm">Overdue: {companies.filter(c => c.communication_status === 'overdue').length}</span>
              </div>
            </div>
            <div className="text-sm text-gray-600">
              Average days since contact: {Math.round(companies.reduce((sum, c) => sum + (c.days_since_contact || 0), 0) / companies.length)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="communications">Communications</TabsTrigger>
          <TabsTrigger value="valuations">Valuations</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-4">
            {companies.map((company) => (
              <Card key={company.id} className="hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <h3 className="text-xl font-semibold">{company.name}</h3>
                            {company.board_seat && <Badge variant="secondary">Board Seat</Badge>}
                            {company.lead_investor && <Badge variant="secondary">Lead</Badge>}
                          </div>
                          <p className="text-sm text-gray-600">{company.sector}</p>
                        </div>
                        <Badge className={getCommunicationStatusColor(company.communication_status)}>
                          {company.communication_status.replace('_', ' ')}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-gray-500">Investment</p>
                          <p className="font-medium">${(company.initial_investment / 1000000).toFixed(1)}M</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Current Value</p>
                          <p className="font-medium">${(company.current_valuation / 1000000).toFixed(1)}M</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Multiple</p>
                          <p className="font-medium">{(company.current_valuation / company.initial_investment).toFixed(2)}x</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500">Ownership</p>
                          <p className="font-medium">{company.ownership_percentage}%</p>
                        </div>
                      </div>

                      {/* Communication Status */}
                      <div className="bg-gray-50 rounded-lg p-3 mb-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            {company.last_communication_type && getCommunicationIcon(company.last_communication_type)}
                            <span className="text-sm font-medium">Last Contact</span>
                          </div>
                          {company.days_since_contact !== undefined && (
                            <span className="text-sm text-gray-600">
                              {company.days_since_contact === 0 ? 'Today' : `${company.days_since_contact} days ago`}
                            </span>
                          )}
                        </div>
                        {company.last_communication_summary && (
                          <p className="text-sm text-gray-600">{company.last_communication_summary}</p>
                        )}
                        {company.follow_up_required && (
                          <div className="flex items-center gap-2 mt-2">
                            <AlertCircle className="w-4 h-4 text-yellow-500" />
                            <span className="text-sm text-yellow-700">
                              Follow-up required {company.follow_up_date && `by ${company.follow_up_date}`}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Valuation Methods */}
                      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                        {company.dcf_valuation && (
                          <div className="text-center">
                            <p className="text-xs text-gray-500">DCF</p>
                            <p className="text-sm font-medium">${(company.dcf_valuation / 1000000).toFixed(1)}M</p>
                          </div>
                        )}
                        {company.comps_valuation && (
                          <div className="text-center">
                            <p className="text-xs text-gray-500">Comps</p>
                            <p className="text-sm font-medium">${(company.comps_valuation / 1000000).toFixed(1)}M</p>
                          </div>
                        )}
                        {company.vc_method_valuation && (
                          <div className="text-center">
                            <p className="text-xs text-gray-500">VC Method</p>
                            <p className="text-sm font-medium">${(company.vc_method_valuation / 1000000).toFixed(1)}M</p>
                          </div>
                        )}
                        {company.pwerm_valuation && (
                          <div className="text-center">
                            <p className="text-xs text-gray-500">PWERM</p>
                            <p className="text-sm font-medium">${(company.pwerm_valuation / 1000000).toFixed(1)}M</p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2 ml-4">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedCompany(company);
                          setShowCommunicationModal(true);
                        }}
                      >
                        <MessageSquare className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedCompany(company);
                          setShowValuationModal(true);
                        }}
                      >
                        <TrendingUp className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="communications">
          <Card>
            <CardHeader>
              <CardTitle>Communication Timeline</CardTitle>
              <CardDescription>Track all interactions with portfolio companies</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {companies.map((company) => (
                  <div key={company.id} className="border-l-2 border-gray-200 pl-4 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium">{company.name}</h4>
                      <Badge className={getCommunicationStatusColor(company.communication_status)}>
                        {company.days_since_contact ? `${company.days_since_contact} days ago` : 'No contact'}
                      </Badge>
                    </div>
                    {company.last_communication_type && (
                      <div className="flex items-start gap-2">
                        {getCommunicationIcon(company.last_communication_type)}
                        <div className="flex-1">
                          <p className="text-sm text-gray-600">{company.last_communication_summary}</p>
                          <p className="text-xs text-gray-500 mt-1">{company.last_communication_date}</p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="valuations">
          <Card>
            <CardHeader>
              <CardTitle>Valuation Analysis</CardTitle>
              <CardDescription>Compare valuations across different methodologies</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {companies.map((company) => {
                  const valuations = [
                    { method: 'dcf_valuation', value: company.dcf_valuation },
                    { method: 'comps_valuation', value: company.comps_valuation },
                    { method: 'precedent_valuation', value: company.precedent_valuation },
                    { method: 'vc_method_valuation', value: company.vc_method_valuation },
                    { method: 'pwerm_valuation', value: company.pwerm_valuation },
                    { method: 'mark_to_market_valuation', value: company.mark_to_market_valuation }
                  ].filter(v => v.value);

                  const avgValuation = valuations.length > 0 
                    ? valuations.reduce((sum, v) => sum + (v.value || 0), 0) / valuations.length 
                    : 0;

                  return (
                    <div key={company.id} className="border rounded-lg p-4">
                      <h4 className="font-medium mb-3">{company.name}</h4>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {valuations.map((val) => (
                          <div key={val.method}>
                            <p className="text-xs text-gray-500">{getValuationMethodName(val.method)}</p>
                            <p className="font-medium">${((val.value || 0) / 1000000).toFixed(1)}M</p>
                          </div>
                        ))}
                        {avgValuation > 0 && (
                          <div className="border-l pl-4">
                            <p className="text-xs text-gray-500">Average</p>
                            <p className="font-medium text-blue-600">${(avgValuation / 1000000).toFixed(1)}M</p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics">
          <Card>
            <CardHeader>
              <CardTitle>Key Metrics</CardTitle>
              <CardDescription>Performance indicators across the portfolio</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                {companies.map((company) => (
                  <div key={company.id} className="border rounded-lg p-4">
                    <h4 className="font-medium mb-3">{company.name}</h4>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                      {company.arr && (
                        <div>
                          <p className="text-xs text-gray-500">ARR</p>
                          <p className="font-medium">${(company.arr / 1000000).toFixed(1)}M</p>
                        </div>
                      )}
                      {company.growth_rate && (
                        <div>
                          <p className="text-xs text-gray-500">Growth Rate</p>
                          <p className="font-medium">{(company.growth_rate * 100).toFixed(0)}%</p>
                        </div>
                      )}
                      {company.runway_months && (
                        <div>
                          <p className="text-xs text-gray-500">Runway</p>
                          <p className="font-medium">{company.runway_months} months</p>
                        </div>
                      )}
                      {company.ltv_cac_ratio && (
                        <div>
                          <p className="text-xs text-gray-500">LTV/CAC</p>
                          <p className="font-medium">{company.ltv_cac_ratio.toFixed(1)}x</p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-gray-500">Multiple</p>
                        <p className="font-medium">{(company.current_valuation / company.initial_investment).toFixed(2)}x</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Communication Modal */}
      {showCommunicationModal && selectedCompany && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Log Communication</CardTitle>
              <CardDescription>{selectedCompany.name}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Type</Label>
                <Select
                  value={communicationLog.type}
                  onValueChange={(value) => setCommunicationLog({...communicationLog, type: value})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="call">Phone Call</SelectItem>
                    <SelectItem value="meeting">Meeting</SelectItem>
                    <SelectItem value="video">Video Call</SelectItem>
                    <SelectItem value="quarterly_report">Quarterly Report</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Date</Label>
                <Input
                  type="date"
                  value={communicationLog.date}
                  onChange={(e) => setCommunicationLog({...communicationLog, date: e.target.value})}
                />
              </div>
              <div>
                <Label>Subject</Label>
                <Input
                  value={communicationLog.subject}
                  onChange={(e) => setCommunicationLog({...communicationLog, subject: e.target.value})}
                  placeholder="Brief subject..."
                />
              </div>
              <div>
                <Label>Summary</Label>
                <Textarea
                  value={communicationLog.summary}
                  onChange={(e) => setCommunicationLog({...communicationLog, summary: e.target.value})}
                  placeholder="Key points discussed..."
                  rows={3}
                />
              </div>
              <div>
                <Label>Sentiment</Label>
                <Select
                  value={communicationLog.sentiment}
                  onValueChange={(value) => setCommunicationLog({...communicationLog, sentiment: value})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="positive">Positive</SelectItem>
                    <SelectItem value="neutral">Neutral</SelectItem>
                    <SelectItem value="negative">Negative</SelectItem>
                    <SelectItem value="concerning">Concerning</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={communicationLog.follow_up_required}
                  onChange={(e) => setCommunicationLog({...communicationLog, follow_up_required: e.target.checked})}
                />
                <Label>Follow-up Required</Label>
              </div>
              {communicationLog.follow_up_required && (
                <div>
                  <Label>Follow-up Date</Label>
                  <Input
                    type="date"
                    value={communicationLog.follow_up_date}
                    onChange={(e) => setCommunicationLog({...communicationLog, follow_up_date: e.target.value})}
                  />
                </div>
              )}
              <div className="flex gap-2">
                <Button onClick={handleLogCommunication} className="flex-1">Save</Button>
                <Button variant="outline" onClick={() => setShowCommunicationModal(false)}>Cancel</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Valuation Modal */}
      {showValuationModal && selectedCompany && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle>Add Valuation</CardTitle>
              <CardDescription>{selectedCompany.name}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Valuation Method</Label>
                <Select
                  value={valuationData.method}
                  onValueChange={(value) => setValuationData({...valuationData, method: value})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dcf">DCF</SelectItem>
                    <SelectItem value="comparable_companies">Comparable Companies</SelectItem>
                    <SelectItem value="precedent_transactions">Precedent Transactions</SelectItem>
                    <SelectItem value="venture_capital_method">VC Method</SelectItem>
                    <SelectItem value="pwerm">PWERM</SelectItem>
                    <SelectItem value="mark_to_market">Mark-to-Market</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Valuation Date</Label>
                <Input
                  type="date"
                  value={valuationData.date}
                  onChange={(e) => setValuationData({...valuationData, date: e.target.value})}
                />
              </div>
              <div>
                <Label>Valuation Amount ($)</Label>
                <Input
                  type="number"
                  value={valuationData.amount}
                  onChange={(e) => setValuationData({...valuationData, amount: parseFloat(e.target.value)})}
                  placeholder="Enter valuation..."
                />
              </div>
              <div>
                <Label>ARR at Valuation ($)</Label>
                <Input
                  type="number"
                  value={valuationData.arr}
                  onChange={(e) => setValuationData({...valuationData, arr: parseFloat(e.target.value)})}
                  placeholder="Annual recurring revenue..."
                />
              </div>
              <div>
                <Label>Growth Rate (%)</Label>
                <Input
                  type="number"
                  value={valuationData.growth_rate}
                  onChange={(e) => setValuationData({...valuationData, growth_rate: parseFloat(e.target.value)})}
                  placeholder="YoY growth rate..."
                />
              </div>
              <div>
                <Label>Confidence Level</Label>
                <Select
                  value={valuationData.confidence_level}
                  onValueChange={(value) => setValuationData({...valuationData, confidence_level: value})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Notes</Label>
                <Textarea
                  value={valuationData.notes}
                  onChange={(e) => setValuationData({...valuationData, notes: e.target.value})}
                  placeholder="Assumptions and notes..."
                  rows={3}
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleAddValuation} className="flex-1">Save</Button>
                <Button variant="outline" onClick={() => setShowValuationModal(false)}>Cancel</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}