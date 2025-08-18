'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Building2, TrendingUp, DollarSign, Target, Zap, BarChart3, Activity, AlertCircle, Loader2, CheckCircle2, History, Trash2, Eye, Save, X } from 'lucide-react';
import { CompanySelector } from '@/components/ui/company-selector';
import { PWERMResultsDisplayV2 } from '@/components/pwerm/PWERMResultsDisplayV2';

interface Company {
  id: string;
  name: string;
  current_arr_usd: number;
  sector: string;
  total_invested_usd?: number;
}

interface PWERMRun {
  id: string;
  timestamp: string;
  companyName: string;
  currentARR: number;
  growthRate: number;
  sector: string;
  results: any;
  status: 'success' | 'error';
  error?: string;
}

// Better sector list without generic "Technology"
const SECTORS = [
  { value: 'AI-Gen AI', label: 'AI - Generative AI' },
  { value: 'AI-ML Infra', label: 'AI - ML Infrastructure' },
  { value: 'AI-Applied AI', label: 'AI - Applied AI' },
  { value: 'SaaS-HR Tech', label: 'SaaS - HR Tech' },
  { value: 'SaaS-Sales/CRM', label: 'SaaS - Sales/CRM' },
  { value: 'SaaS-DevTools', label: 'SaaS - Developer Tools' },
  { value: 'SaaS-Data/Analytics', label: 'SaaS - Data/Analytics' },
  { value: 'SaaS-Marketing', label: 'SaaS - Marketing' },
  { value: 'SaaS-Security', label: 'SaaS - Security' },
  { value: 'SaaS-Productivity', label: 'SaaS - Productivity' },
  { value: 'Fintech-Payments', label: 'Fintech - Payments' },
  { value: 'Fintech-Banking', label: 'Fintech - Banking' },
  { value: 'Fintech-Lending', label: 'Fintech - Lending' },
  { value: 'Fintech-Insurance', label: 'Fintech - Insurance' },
  { value: 'Health-Telemedicine', label: 'Health - Telemedicine' },
  { value: 'Health-Digital Health', label: 'Health - Digital Health' },
  { value: 'Health-Biotech', label: 'Health - Biotech' },
  { value: 'Marketplace-Commerce', label: 'Marketplace - Commerce' },
  { value: 'Marketplace-Mobility', label: 'Marketplace - Mobility' },
  { value: 'Marketplace-Services', label: 'Marketplace - Services' },
  { value: 'B2B Fintech', label: 'B2B Fintech' },
  { value: 'B2C Fintech', label: 'B2C Fintech' },
  { value: 'E-com', label: 'E-commerce' },
  { value: 'Edtech', label: 'Education Tech' },
  { value: 'Cyber', label: 'Cybersecurity' },
  { value: 'Dev Tool', label: 'Developer Tools' },
  { value: 'Climate Tech', label: 'Climate Tech' },
  { value: 'Supply Chain', label: 'Supply Chain' },
];

export default function PWERMAnalysisPage() {
  const [loading, setLoading] = useState(false);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [progressSteps, setProgressSteps] = useState<Array<{message: string, completed: boolean}>>([]);
  const [previousRuns, setPreviousRuns] = useState<PWERMRun[]>([]);
  const [viewingRun, setViewingRun] = useState<PWERMRun | null>(null);
  const [activeTab, setActiveTab] = useState('new');
  
  // Form state
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [currentARR, setCurrentARR] = useState('');
  const [growthRate, setGrowthRate] = useState('');
  const [sector, setSector] = useState('SaaS-HR Tech'); // Default to a specific sector
  const [isManualEntry, setIsManualEntry] = useState(false);

  // Fetch companies and load previous runs on mount
  useEffect(() => {
    fetchCompanies();
    loadPreviousRuns();
  }, []);

  // Load previous runs from localStorage
  const loadPreviousRuns = () => {
    try {
      const stored = localStorage.getItem('pwerm_runs');
      if (stored) {
        const runs = JSON.parse(stored);
        setPreviousRuns(runs.sort((a: PWERMRun, b: PWERMRun) => 
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        ));
      }
    } catch (err) {
      console.error('Failed to load previous runs:', err);
    }
  };

  // Save run to localStorage
  const saveRun = (run: PWERMRun) => {
    try {
      // Get existing runs directly from localStorage to avoid stale state
      const stored = localStorage.getItem('pwerm_runs');
      const existingRuns = stored ? JSON.parse(stored) : [];
      const filteredRuns = existingRuns.filter((r: PWERMRun) => r.id !== run.id);
      const updatedRuns = [run, ...filteredRuns].slice(0, 20); // Keep last 20 runs
      localStorage.setItem('pwerm_runs', JSON.stringify(updatedRuns));
      setPreviousRuns(updatedRuns);
    } catch (err) {
      console.error('Failed to save run:', err);
    }
  };

  // Delete a run
  const deleteRun = (runId: string) => {
    const updatedRuns = previousRuns.filter(r => r.id !== runId);
    localStorage.setItem('pwerm_runs', JSON.stringify(updatedRuns));
    setPreviousRuns(updatedRuns);
    if (viewingRun?.id === runId) {
      setViewingRun(null);
      setActiveTab('new');
    }
  };

  // Clear all runs
  const clearAllRuns = () => {
    if (confirm('Are you sure you want to clear all saved runs?')) {
      localStorage.removeItem('pwerm_runs');
      setPreviousRuns([]);
      setViewingRun(null);
      setActiveTab('new');
    }
  };

  const fetchCompanies = async () => {
    try {
      // Check if we have cached data in sessionStorage
      const cached = sessionStorage.getItem('pwerm_companies_cache');
      const cacheTime = sessionStorage.getItem('pwerm_companies_cache_time');
      const now = Date.now();
      
      // Use cache if it's less than 5 minutes old
      if (cached && cacheTime && (now - parseInt(cacheTime)) < 5 * 60 * 1000) {
        const cachedData = JSON.parse(cached);
        setCompanies(cachedData);
        setLoadingCompanies(false);
        return;
      }
      
      // Fetch from optimized companies-all endpoint with lightweight flag
      const response = await fetch('/api/companies-all?lightweight=true');
      if (response.ok) {
        const data = await response.json();
        
        // Filter companies with valid names
        const validCompanies = data.filter((company: Company) => 
          company.name && company.name.trim() !== ''
        );
        
        // Sort by ARR (highest first) for better UX, then by name
        validCompanies.sort((a: Company, b: Company) => {
          if (a.current_arr_usd && b.current_arr_usd) {
            return b.current_arr_usd - a.current_arr_usd;
          }
          return a.name.localeCompare(b.name);
        });
        
        // Cache the data
        sessionStorage.setItem('pwerm_companies_cache', JSON.stringify(validCompanies));
        sessionStorage.setItem('pwerm_companies_cache_time', now.toString());
        
        setCompanies(validCompanies);
      }
    } catch (err) {
      console.error('Failed to fetch companies:', err);
    } finally {
      setLoadingCompanies(false);
    }
  };

  // Handle company selection
  const handleCompanySelect = (companyId: string) => {
    if (companyId === 'manual') {
      setIsManualEntry(true);
      setSelectedCompany(null);
      setCompanyName('');
      setCurrentARR('');
      setGrowthRate('50');
      setSector('SaaS-HR Tech');
    } else {
      setIsManualEntry(false);
      const company = companies.find(c => c.id === companyId);
      if (company) {
        setSelectedCompany(company);
        setCompanyName(company.name);
        // Always convert to millions for display (e.g., 300 for $300M)
        // If value is > 10000, assume it's in dollars and divide by 1M
        // If value is < 10000, assume it's already in millions
        const arr = company.current_arr_usd || 0;
        const arrInMillions = arr > 10000 ? arr / 1000000 : arr;
        setCurrentARR(arrInMillions ? arrInMillions.toString() : '0');
        setGrowthRate('50'); // Default growth rate
        
        // Use the sector directly from the database
        // If company has a sector, use it; otherwise use default
        if (company.sector) {
          // Check if the company's sector is in our SECTORS list
          const sectorExists = SECTORS.some(s => s.value === company.sector);
          if (sectorExists) {
            setSector(company.sector);
          } else {
            // If not in our list, still use it but user can change
            setSector(company.sector);
          }
        } else {
          // Default if no sector in database
          setSector('SaaS-HR Tech');
        }
      }
    }
    setSelectedCompanyId(companyId);
  };

  // View a previous run
  const viewRun = (run: PWERMRun) => {
    setViewingRun(run);
    setResults(run.results);
    setError(run.error || null);
    setActiveTab('new');
  };

  const runAnalysis = async () => {
    if (!companyName || !currentARR || !growthRate) {
      setError('Please fill in all required fields');
      return;
    }

    // ARR is already in millions (e.g., user enters 300 = $300M)
    // Make sure it's treated as millions
    let arrInMillions = parseFloat(currentARR);
    // Safety check: if someone accidentally enters the full value
    if (arrInMillions > 100000) {
      arrInMillions = arrInMillions / 1000000;
    }

    setLoading(true);
    setError(null);
    setResults(null);
    setViewingRun(null);
    setProgress(0);
    setProgressMessage('Starting PWERM analysis...');
    setProgressSteps([]);

    const runId = `run-${Date.now()}`;

    try {
      setProgressMessage('Categorizing company and analyzing market...');
      setProgress(10);

      const response = await fetch('/api/pwerm-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_name: companyName,
          current_arr: arrInMillions, // API expects millions
          growth_rate: parseFloat(growthRate) / 100,
          sector: sector,
        }),
      });

      setProgress(50);
      setProgressMessage('Processing analysis results...');

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      setProgress(90);
      setProgressMessage('Finalizing results...');

      // Save successful run
      const run: PWERMRun = {
        id: runId,
        timestamp: new Date().toISOString(),
        companyName,
        currentARR: parseFloat(currentARR), // Store in millions as entered
        growthRate: parseFloat(growthRate),
        sector,
        results: data,
        status: 'success',
      };
      
      saveRun(run);
      setResults(data);
      setProgress(100);
      setProgressMessage('Analysis complete!');
      
    } catch (err) {
      console.error('PWERM Analysis Error:', err);
      const errorMessage = err instanceof Error ? err.message : 'Analysis failed';
      setError(errorMessage);
      
      // Save failed run
      const run: PWERMRun = {
        id: runId,
        timestamp: new Date().toISOString(),
        companyName,
        currentARR: parseFloat(currentARR), // Store in millions as entered
        growthRate: parseFloat(growthRate),
        sector,
        results: null,
        status: 'error',
        error: errorMessage,
      };
      
      saveRun(run);
    } finally {
      setLoading(false);
      setTimeout(() => {
        setProgress(0);
        setProgressMessage('');
      }, 2000);
    }
  };

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-gray-900 to-gray-600 dark:from-gray-100 dark:to-gray-400 bg-clip-text text-transparent">PWERM Playground</h1>
          <p className="text-sm text-muted-foreground mt-1 font-medium">Probability-Weighted Expected Return Method</p>
        </div>
        <Badge variant="outline" className="text-sm font-medium">
          Advanced Valuation
        </Badge>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="new">New Analysis</TabsTrigger>
          <TabsTrigger value="history">
            Previous Runs ({previousRuns.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="new">
          <div className="grid gap-6">
            {/* Input Form */}
            <Card>
              <CardHeader>
                <CardTitle>Company Information</CardTitle>
                <CardDescription>
                  Enter company details for PWERM valuation analysis
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="company">Company</Label>
                    <CompanySelector
                      companies={companies}
                      value={selectedCompanyId}
                      onSelect={handleCompanySelect}
                      placeholder="Select or search company..."
                      loading={loadingCompanies}
                      allowManualEntry={true}
                    />
                  </div>

                  {isManualEntry && (
                    <div>
                      <Label htmlFor="company-name">Company Name</Label>
                      <Input
                        id="company-name"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        placeholder="Enter company name"
                      />
                    </div>
                  )}

                  <div>
                    <Label htmlFor="sector">Sector/Subsector</Label>
                    <Select value={sector} onValueChange={setSector}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select sector" />
                      </SelectTrigger>
                      <SelectContent>
                        {SECTORS.map(s => (
                          <SelectItem key={s.value} value={s.value}>
                            {s.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label htmlFor="arr">Current ARR ($M)</Label>
                    <Input
                      id="arr"
                      type="number"
                      value={currentARR}
                      onChange={(e) => setCurrentARR(e.target.value)}
                      placeholder="e.g., 300"
                    />
                    <p className="text-sm text-muted-foreground mt-1">
                      {currentARR && !isNaN(parseFloat(currentARR)) && `$${parseFloat(currentARR).toFixed(1)}M ARR`}
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="growth">Annual Growth Rate (%)</Label>
                    <Input
                      id="growth"
                      type="number"
                      value={growthRate}
                      onChange={(e) => setGrowthRate(e.target.value)}
                      placeholder="e.g., 80"
                      min="0"
                      max="500"
                    />
                  </div>
                </div>

                {/* Progress Section */}
                {loading && (
                  <div className="space-y-2">
                    <Progress value={progress} className="h-2" />
                    <p className="text-sm text-muted-foreground">{progressMessage}</p>
                    {progressSteps.length > 0 && (
                      <div className="space-y-1 mt-2">
                        {progressSteps.map((step, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-xs">
                            <CheckCircle2 className="h-3 w-3 text-green-500" />
                            <span className="text-muted-foreground">{step.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <Button
                  onClick={runAnalysis}
                  disabled={loading || !companyName || !currentARR || !growthRate}
                  className="w-full md:w-auto"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Running Analysis...
                    </>
                  ) : (
                    <>
                      <Zap className="mr-2 h-4 w-4" />
                      Run PWERM Analysis
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Error Display */}
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Analysis Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Viewing Previous Run Banner */}
            {viewingRun && (
              <Alert>
                <History className="h-4 w-4" />
                <AlertTitle>Viewing Previous Run</AlertTitle>
                <AlertDescription className="flex items-center justify-between">
                  <span>
                    {viewingRun.companyName} - {new Date(viewingRun.timestamp).toLocaleString()}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setViewingRun(null);
                      setResults(null);
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </AlertDescription>
              </Alert>
            )}

            {/* Results Display */}
            {results && <PWERMResultsDisplayV2 results={results} />}
          </div>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Previous Analysis Runs</CardTitle>
                {previousRuns.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearAllRuns}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Clear All
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {previousRuns.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No previous runs saved
                </p>
              ) : (
                <div className="space-y-2">
                  {previousRuns.map((run) => (
                    <div
                      key={run.id}
                      className={`flex items-center justify-between p-3 border rounded-lg hover:bg-accent/50 transition-colors ${
                        run.status === 'success' ? 'cursor-pointer' : ''
                      }`}
                      onClick={(e) => {
                        // Only trigger if clicking on the row itself, not buttons
                        if (run.status === 'success' && 
                            !(e.target as HTMLElement).closest('button')) {
                          viewRun(run);
                          setActiveTab('new');
                        }
                      }}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-base">{run.companyName}</span>
                          <Badge variant={run.status === 'success' ? 'default' : 'destructive'}>
                            {run.status}
                          </Badge>
                          <Badge variant="outline">{run.sector}</Badge>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1 font-medium">
                          ARR: ${run.currentARR.toFixed(1)}M | 
                          Growth: {run.growthRate}% | 
                          {' '}{new Date(run.timestamp).toLocaleString()}
                        </div>
                        {run.status === 'success' && run.results?.summary && (
                          <div className="text-sm mt-1 font-semibold text-emerald-600 dark:text-emerald-400">
                            Expected Value: ${(run.results.summary.expected_exit_value / 1000000).toFixed(1)}M
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {run.status === 'success' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              viewRun(run);
                              setActiveTab('new');
                            }}
                          >
                            <Eye className="mr-2 h-4 w-4" />
                            View
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteRun(run.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}