'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { GraduationCap, Plus, Trash2, X, Sparkles, Search, Calculator } from 'lucide-react';

interface PortfolioCompany {
  id: string;
  name: string;
  sector: string;
  stage: string;
  investmentAmount: number;
  ownershipPercentage: number;
  currentArr: number;
  valuation: number;
  investmentDate: string;
  exitDate?: string;
  exitValue?: number;
  exitMultiple?: number;
  fundId: string;
  // Calculated fields
  individualIrr?: number;
  individualMultiple?: number;
  individualReturn?: number;
}

interface Portfolio {
  id: string;
  name: string;
  fundSize: number;
  totalInvested: number;
  totalValuation: number;
  companies: PortfolioCompany[];
}

interface NewPortfolio {
  name: string;
  fundSize: number;
  targetMultiple: number;
  vintageYear: number;
  fundType: string;
  sectors: string[];
  strategy: string;
  deploymentPeriod: number;
  harvestPeriod: number;
}

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>('');
  const [availableCompanies, setAvailableCompanies] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [showAddFundModal, setShowAddFundModal] = useState(false);
  const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
  const [showSimulationModal, setShowSimulationModal] = useState(false);
  const [selectedPortfolioForSimulation, setSelectedPortfolioForSimulation] = useState<Portfolio | null>(null);
  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    fundSize: 0,
    targetMultiple: 30000,
    vintageYear: new Date().getFullYear(),
    fundType: 'venture'
  });
  const [newCompany, setNewCompany] = useState({
    name: '',
    sector: '',
    stage: '',
    investmentAmount: 0,
    ownershipPercentage: 0,
    investmentDate: new Date().toISOString().split('T')[0],
    currentArr: 0,
    valuation: 0
  });

  const loadPortfolios = async () => {
    try {
      const response = await fetch('/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        // Metrics are now pre-calculated on the server
        setPortfolios(data);
      }
    } catch (error) {
      console.error('Error loading portfolios:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPortfolios();
    searchCompanies('');
  }, []);

  const searchCompanies = async (query: string) => {
    setIsSearching(true);
    try {
      const response = await fetch(`/api/companies/search?q=${encodeURIComponent(query)}&limit=100`);
      if (response.ok) {
        const data = await response.json();
        setAvailableCompanies(data.companies || []);
      }
    } catch (error) {
      console.error('Error searching companies:', error);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      searchCompanies(searchQuery);
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchQuery]);

  const generateRandomPortfolio = async () => {
    const portfolioName = `Random Portfolio ${new Date().toLocaleDateString()}`;
    const fundSize = Math.floor(Math.random() * 90000000) + 10000000; // 10M to 100M
    
    // Create the portfolio first
    const portfolioResponse = await fetch('/api/portfolio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: portfolioName,
        fundSize: fundSize,
        targetMultiple: 30000,
        vintageYear: new Date().getFullYear(),
        fundType: 'venture'
      })
    });

    if (!portfolioResponse.ok) {
      alert('Failed to create random portfolio');
      return;
    }

    const newPortfolio = await portfolioResponse.json();
    const portfolioId = newPortfolio.id;

    // Fetch random companies from the database
    const numCompanies = Math.floor(Math.random() * 10) + 5; // 5-15 companies
    const randomCompaniesResponse = await fetch(`/api/companies/random?limit=${numCompanies}`);
    
    if (!randomCompaniesResponse.ok) {
      alert('Failed to fetch random companies');
      return;
    }
    
    const selectedCompanies = await randomCompaniesResponse.json();
    
    // Ensure we have an array of companies
    const companiesArray = Array.isArray(selectedCompanies) ? selectedCompanies : [];
    
    if (companiesArray.length === 0) {
      alert('No companies found to add to portfolio');
      return;
    }

    // Add each company to the portfolio
    console.log(`Adding ${companiesArray.length} companies to portfolio ${portfolioId}`);
    let successCount = 0;
    let failCount = 0;
    
    for (const company of companiesArray) {
      const investmentAmount = Math.floor(Math.random() * 4500000) + 500000; // 500K to 5M
      const ownershipPercentage = Math.floor(Math.random() * 15) + 5; // 5% to 20%
      
      const response = await fetch(`/api/portfolio/${portfolioId}/companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: company.name,
          sector: company.sector || 'Technology',
          stage: 'Series A',
          investmentAmount: investmentAmount,
          ownershipPercentage: ownershipPercentage,
          investmentDate: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000 * 2).toISOString().split('T')[0],
          currentArr: company.current_arr_usd || Math.floor(Math.random() * 10000000),
          valuation: company.total_invested_usd || investmentAmount * (100 / ownershipPercentage)
        })
      });
      
      if (response.ok) {
        successCount++;
        console.log(`Successfully added ${company.name} (${successCount}/${companiesArray.length})`);
      } else {
        failCount++;
        const error = await response.text();
        console.error(`Failed to add ${company.name}:`, error);
      }
    }
    
    console.log(`Finished: ${successCount} success, ${failCount} failed out of ${companiesArray.length} total`);
    

    loadPortfolios();
    alert(`Created random portfolio "${portfolioName}" with ${companiesArray.length} companies!`);
  };

  const handleAddPortfolio = async () => {
    try {
      const response = await fetch('/api/portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPortfolio)
      });

      if (response.ok) {
        setShowAddFundModal(false);
        setNewPortfolio({
          name: '',
          fundSize: 0,
          targetMultiple: 30000,
          vintageYear: new Date().getFullYear(),
          fundType: 'venture'
        });
        loadPortfolios();
      }
    } catch (error) {
      console.error('Error adding portfolio:', error);
    }
  };

  const handleAddCompany = async () => {
    if (!selectedPortfolio) {
      alert('Please select a portfolio first');
      return;
    }

    try {
      const response = await fetch(`/api/portfolio/${selectedPortfolio}/companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCompany)
      });

      if (response.ok) {
        setShowAddCompanyModal(false);
        setNewCompany({
          name: '',
          sector: '',
          stage: '',
          investmentAmount: 0,
          ownershipPercentage: 0,
          investmentDate: new Date().toISOString().split('T')[0],
          currentArr: 0,
          valuation: 0
        });
        loadPortfolios();
      }
    } catch (error) {
      console.error('Error adding company:', error);
    }
  };

  const handleDeletePortfolio = async (portfolioId: string) => {
    if (confirm('Are you sure you want to delete this portfolio?')) {
      try {
        const response = await fetch(`/api/portfolio/${portfolioId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          loadPortfolios();
        }
      } catch (error) {
        console.error('Error deleting portfolio:', error);
      }
    }
  };

  const handleDeleteCompany = async (portfolioId: string, companyId: string) => {
    if (confirm('Are you sure you want to delete this company?')) {
      try {
        const response = await fetch(`/api/portfolio/${portfolioId}/companies?companyId=${companyId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          loadPortfolios();
        }
      } catch (error) {
        console.error('Error deleting company:', error);
      }
    }
  };

  const handleRunScenarios = async (portfolioId: string) => {
    try {
      const response = await fetch(`/api/scenarios/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolioId })
      });

      if (response.ok) {
        alert('Scenarios analysis started successfully!');
      } else {
        alert('Failed to start scenarios analysis');
      }
    } catch (error) {
      console.error('Error running scenarios:', error);
      alert('Error running scenarios analysis');
    }
  };

  const handleRunPWERM = async (portfolioId: string) => {
    try {
      const response = await fetch(`/api/pwerm/scenarios`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolioId })
      });

      if (response.ok) {
        alert('PWERM analysis started successfully!');
      } else {
        alert('Failed to start PWERM analysis');
      }
    } catch (error) {
      console.error('Error running PWERM:', error);
      alert('Error running PWERM analysis');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Portfolio Management</h1>
        <div className="flex gap-2">
          <Button onClick={() => window.location.href = '/portfolio/pacing'} variant="outline">
            View Pacing Graph
          </Button>
          <Button onClick={generateRandomPortfolio} variant="outline">
            <Sparkles className="w-4 h-4 mr-2" />
            Random Portfolio
          </Button>
          <Button onClick={() => setShowAddFundModal(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Fund
          </Button>
        </div>
      </div>

      {portfolios.length === 0 ? (
        <Alert>
          <AlertDescription>
            No funds created yet. Create your first fund to get started.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-6">
          {portfolios.map((portfolio) => (
            <Card key={portfolio.id}>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-xl">{portfolio.name}</CardTitle>
                    <CardDescription>
                      Fund Size: ${portfolio.fundSize.toLocaleString()} | 
                      Invested: ${portfolio.totalInvested.toLocaleString()} | 
                      Current Value: ${portfolio.totalValuation.toLocaleString()}
                    </CardDescription>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDeletePortfolio(portfolio.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-lg font-semibold">Companies ({portfolio.companies.length})</h3>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => {
                          setSelectedPortfolioForSimulation(portfolio);
                          setShowSimulationModal(true);
                        }}
                        size="sm"
                        variant="outline"
                      >
                        <Calculator className="w-4 h-4 mr-2" />
                        Simulate Outcomes
                      </Button>
                      <Button
                        onClick={() => handleRunScenarios(portfolio.id)}
                        size="sm"
                        variant="outline"
                      >
                        Run Scenarios
                      </Button>
                      <Button
                        onClick={() => handleRunPWERM(portfolio.id)}
                        size="sm"
                        variant="outline"
                      >
                        Run PWERM
                      </Button>
                      <Button
                        onClick={() => {
                          setSelectedPortfolio(portfolio.id);
                          setShowAddCompanyModal(true);
                        }}
                        size="sm"
                      >
                        <Plus className="w-4 h-4 mr-2" />
                        Add Company
                      </Button>
                    </div>
                  </div>
                  
                  {portfolio.companies.length === 0 ? (
                    <p className="text-gray-500">No companies in this portfolio yet.</p>
                  ) : (
                    <div className="grid gap-4">
                      {portfolio.companies.map((company) => (
                        <Card key={company.id} className="p-4">
                          <div className="flex justify-between items-start">
                            <div className="flex-1">
                              <h4 className="font-semibold">{company.name}</h4>
                              <p className="text-sm text-gray-600">
                                {company.sector} • {company.stage}
                              </p>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
                                <div>
                                  <p className="text-xs text-gray-500">Investment</p>
                                  <p className="font-medium">${company.investmentAmount.toLocaleString()}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500">Ownership</p>
                                  <p className="font-medium">{company.ownershipPercentage}%</p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500">Current ARR</p>
                                  <p className="font-medium">${company.currentArr.toLocaleString()}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500">Valuation</p>
                                  <p className="font-medium">${company.valuation.toLocaleString()}</p>
                                </div>
                              </div>
                              <div className="grid grid-cols-3 gap-4 mt-2">
                                <div>
                                  <p className="text-xs text-gray-500">Individual IRR</p>
                                  <p className={`font-medium ${company.individualIrr && company.individualIrr > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    {company.individualIrr ? `${company.individualIrr.toFixed(1)}%` : 'N/A'}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500">Multiple</p>
                                  <p className="font-medium">{company.individualMultiple ? company.individualMultiple.toFixed(2) : 'N/A'}</p>
                                </div>
                                <div>
                                  <p className="text-xs text-gray-500">Return</p>
                                  <p className={`font-medium ${company.individualReturn && company.individualReturn > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                    ${company.individualReturn ? company.individualReturn.toLocaleString() : 'N/A'}
                                  </p>
                                </div>
                              </div>
                            </div>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => handleDeleteCompany(portfolio.id, company.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add Fund Modal */}
      {showAddFundModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Add New Fund</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowAddFundModal(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="fundName">Fund Name</Label>
                <Input
                  id="fundName"
                  value={newPortfolio.name}
                  onChange={(e) => setNewPortfolio({...newPortfolio, name: e.target.value})}
                  placeholder="Enter fund name"
                />
              </div>
              <div>
                <Label htmlFor="fundSize">Fund Size (USD)</Label>
                <Input
                  id="fundSize"
                  type="number"
                  value={newPortfolio.fundSize}
                  onChange={(e) => setNewPortfolio({...newPortfolio, fundSize: parseInt(e.target.value)})}
                  placeholder="Enter fund size"
                />
              </div>
              <div>
                <Label htmlFor="targetMultiple">Target Multiple (bps)</Label>
                <Input
                  id="targetMultiple"
                  type="number"
                  value={newPortfolio.targetMultiple}
                  onChange={(e) => setNewPortfolio({...newPortfolio, targetMultiple: parseInt(e.target.value)})}
                  placeholder="30000"
                />
              </div>
              <div>
                <Label htmlFor="vintageYear">Vintage Year</Label>
                <Input
                  id="vintageYear"
                  type="number"
                  value={newPortfolio.vintageYear}
                  onChange={(e) => setNewPortfolio({...newPortfolio, vintageYear: parseInt(e.target.value)})}
                  placeholder="2024"
                />
              </div>
              <div>
                <Label htmlFor="fundType">Fund Type</Label>
                <Input
                  id="fundType"
                  value={newPortfolio.fundType}
                  onChange={(e) => setNewPortfolio({...newPortfolio, fundType: e.target.value})}
                  placeholder="venture"
                />
              </div>
              <Button onClick={handleAddPortfolio} className="w-full">
                Create Fund
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Add Company Modal */}
      {showAddCompanyModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Add Company to Portfolio</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowAddCompanyModal(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="companySearch">Search Companies</Label>
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="companySearch"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Type to search companies..."
                    className="pl-8"
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="companySelect">Select Company</Label>
                <Select
                  value={newCompany.name}
                  onValueChange={(value) => {
                    const selected = availableCompanies.find(c => c.name === value);
                    if (selected) {
                      setNewCompany({
                        ...newCompany,
                        name: selected.name,
                        sector: selected.sector || newCompany.sector,
                        currentArr: selected.current_arr_usd || newCompany.currentArr,
                        valuation: selected.total_invested_usd || newCompany.valuation
                      });
                    }
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a company" />
                  </SelectTrigger>
                  <SelectContent>
                    {isSearching ? (
                      <SelectItem value="loading" disabled>Searching...</SelectItem>
                    ) : availableCompanies.length === 0 ? (
                      <SelectItem value="none" disabled>No companies found</SelectItem>
                    ) : (
                      availableCompanies.map((company) => (
                        <SelectItem key={company.id} value={company.name}>
                          <div className="flex flex-col">
                            <span>{company.name}</span>
                            {company.sector && (
                              <span className="text-xs text-muted-foreground">{company.sector}</span>
                            )}
                          </div>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="text-center text-sm text-muted-foreground">OR</div>
              <div>
                <Label htmlFor="companyName">Enter Company Name Manually</Label>
                <Input
                  id="companyName"
                  value={newCompany.name}
                  onChange={(e) => setNewCompany({...newCompany, name: e.target.value})}
                  placeholder="Enter company name"
                />
              </div>
              <div>
                <Label htmlFor="sector">Sector</Label>
                <Input
                  id="sector"
                  value={newCompany.sector}
                  onChange={(e) => setNewCompany({...newCompany, sector: e.target.value})}
                  placeholder="Enter sector"
                />
              </div>
              <div>
                <Label htmlFor="stage">Stage</Label>
                <Select
                  value={newCompany.stage}
                  onValueChange={(value) => setNewCompany({...newCompany, stage: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select stage" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Pre-Seed">Pre-Seed</SelectItem>
                    <SelectItem value="Seed">Seed</SelectItem>
                    <SelectItem value="Series A">Series A</SelectItem>
                    <SelectItem value="Series B">Series B</SelectItem>
                    <SelectItem value="Series C">Series C</SelectItem>
                    <SelectItem value="Series D+">Series D+</SelectItem>
                    <SelectItem value="Growth">Growth</SelectItem>
                    <SelectItem value="Late Stage">Late Stage</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="investmentAmount">Investment Amount (USD)</Label>
                <Input
                  id="investmentAmount"
                  type="number"
                  value={newCompany.investmentAmount}
                  onChange={(e) => setNewCompany({...newCompany, investmentAmount: parseInt(e.target.value)})}
                  placeholder="Enter investment amount"
                />
              </div>
              <div>
                <Label htmlFor="ownershipPercentage">Ownership Percentage</Label>
                <Input
                  id="ownershipPercentage"
                  type="number"
                  value={newCompany.ownershipPercentage}
                  onChange={(e) => setNewCompany({...newCompany, ownershipPercentage: parseFloat(e.target.value)})}
                  placeholder="Enter ownership percentage"
                />
              </div>
              <div>
                <Label htmlFor="investmentDate">Investment Date</Label>
                <Input
                  id="investmentDate"
                  type="date"
                  value={newCompany.investmentDate}
                  onChange={(e) => setNewCompany({...newCompany, investmentDate: e.target.value})}
                />
              </div>
              <div>
                <Label htmlFor="currentArr">Current ARR (USD)</Label>
                <Input
                  id="currentArr"
                  type="number"
                  value={newCompany.currentArr}
                  onChange={(e) => setNewCompany({...newCompany, currentArr: parseInt(e.target.value)})}
                  placeholder="Enter current ARR"
                />
              </div>
              <div>
                <Label htmlFor="valuation">Current Valuation (USD)</Label>
                <Input
                  id="valuation"
                  type="number"
                  value={newCompany.valuation}
                  onChange={(e) => setNewCompany({...newCompany, valuation: parseInt(e.target.value)})}
                  placeholder="Enter current valuation"
                />
              </div>
              <Button onClick={handleAddCompany} className="w-full">
                Add Company
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Simulation Modal */}
      {showSimulationModal && selectedPortfolioForSimulation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto">
          <Card className="w-full max-w-4xl m-4 max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex justify-between items-center">
                <CardTitle>Portfolio Outcome Simulation</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setShowSimulationModal(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
              <CardDescription>
                Simulate ownership dilution and exit scenarios for {selectedPortfolioForSimulation.name}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-purple-50 p-4 rounded-lg">
                  <h4 className="font-semibold text-purple-900 mb-2">Portfolio Stats</h4>
                  <p className="text-sm">Companies: {selectedPortfolioForSimulation.companies.length}</p>
                  <p className="text-sm">Total Invested: ${selectedPortfolioForSimulation.totalInvested.toLocaleString()}</p>
                  <p className="text-sm">Current Value: ${selectedPortfolioForSimulation.totalValuation.toLocaleString()}</p>
                </div>
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-semibold text-blue-900 mb-2">Ownership Analysis</h4>
                  <p className="text-sm">Average Ownership: {(selectedPortfolioForSimulation.companies.reduce((sum, c) => sum + c.ownershipPercentage, 0) / selectedPortfolioForSimulation.companies.length).toFixed(1)}%</p>
                  <p className="text-sm">Max Ownership: {Math.max(...selectedPortfolioForSimulation.companies.map(c => c.ownershipPercentage))}%</p>
                  <p className="text-sm">Min Ownership: {Math.min(...selectedPortfolioForSimulation.companies.map(c => c.ownershipPercentage))}%</p>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-semibold">Exit Scenarios</h4>
                {selectedPortfolioForSimulation.companies.map((company) => {
                  const acquirePrice = company.valuation * (3 + Math.random() * 7); // 3-10x current valuation
                  const ipoPrice = company.valuation * (10 + Math.random() * 20); // 10-30x for IPO
                  const failureReturn = 0;
                  
                  return (
                    <div key={company.id} className="border rounded-lg p-4">
                      <h5 className="font-medium mb-2">{company.name}</h5>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-gray-600">Acquisition (3-10x)</p>
                          <p className="font-bold text-green-600">
                            ${((acquirePrice * company.ownershipPercentage / 100)).toLocaleString()}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(acquirePrice / company.investmentAmount).toFixed(1)}x return
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600">IPO (10-30x)</p>
                          <p className="font-bold text-blue-600">
                            ${((ipoPrice * company.ownershipPercentage / 100)).toLocaleString()}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(ipoPrice / company.investmentAmount).toFixed(1)}x return
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600">Write-off</p>
                          <p className="font-bold text-red-600">$0</p>
                          <p className="text-xs text-gray-500">0x return</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Portfolio Outcomes</h4>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Conservative (50% fail, 40% acquire, 10% IPO):</span>
                    <span className="font-bold">
                      {(() => {
                        const companies = selectedPortfolioForSimulation.companies;
                        const numFail = Math.floor(companies.length * 0.5);
                        const numAcquire = Math.floor(companies.length * 0.4);
                        const numIPO = companies.length - numFail - numAcquire;
                        
                        let totalReturn = 0;
                        companies.forEach((c, i) => {
                          if (i < numFail) {
                            // Failed companies
                            totalReturn += 0;
                          } else if (i < numFail + numAcquire) {
                            // Acquired companies (5x average)
                            totalReturn += c.investmentAmount * 5;
                          } else {
                            // IPO companies (20x average)
                            totalReturn += c.investmentAmount * 20;
                          }
                        });
                        
                        const multiple = totalReturn / selectedPortfolioForSimulation.totalInvested;
                        return `${multiple.toFixed(1)}x ($${totalReturn.toLocaleString()})`;
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Optimistic (20% fail, 60% acquire, 20% IPO):</span>
                    <span className="font-bold text-green-600">
                      {(() => {
                        const companies = selectedPortfolioForSimulation.companies;
                        const numFail = Math.floor(companies.length * 0.2);
                        const numAcquire = Math.floor(companies.length * 0.6);
                        const numIPO = companies.length - numFail - numAcquire;
                        
                        let totalReturn = 0;
                        companies.forEach((c, i) => {
                          if (i < numFail) {
                            totalReturn += 0;
                          } else if (i < numFail + numAcquire) {
                            totalReturn += c.investmentAmount * 5;
                          } else {
                            totalReturn += c.investmentAmount * 20;
                          }
                        });
                        
                        const multiple = totalReturn / selectedPortfolioForSimulation.totalInvested;
                        return `${multiple.toFixed(1)}x ($${totalReturn.toLocaleString()})`;
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
