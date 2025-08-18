'use client';

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calculator, Plus, Trash2, TrendingUp, TrendingDown, BarChart3, Download } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface ScenarioGeneratorProps {
  baseData?: {
    startingARR: number;
    monthlyGrowthRate: number;
    churnRate: number;
    averageDealSize: number;
  };
  onExport?: (scenarios: any) => void;
}

export const ScenarioGenerator: React.FC<ScenarioGeneratorProps> = ({
  baseData = {
    startingARR: 1500,
    monthlyGrowthRate: 15,
    churnRate: 5,
    averageDealSize: 500
  },
  onExport
}) => {
  const [scenarios, setScenarios] = useState<Array<{
    id: string;
    name: string;
    growthRate: number;
    churnRate: number;
    newDealsPerMonth: number;
    dealSizeGrowth: number;
    color: string;
  }>>([
    {
      id: '1',
      name: 'Base Case',
      growthRate: 15,
      churnRate: 5,
      newDealsPerMonth: 4,
      dealSizeGrowth: 0,
      color: '#3b82f6'
    },
    {
      id: '2',
      name: 'Bull Case',
      growthRate: 25,
      churnRate: 3,
      newDealsPerMonth: 6,
      dealSizeGrowth: 10,
      color: '#10b981'
    },
    {
      id: '3',
      name: 'Bear Case',
      growthRate: 5,
      churnRate: 8,
      newDealsPerMonth: 2,
      dealSizeGrowth: -5,
      color: '#ef4444'
    }
  ]);

  const [months] = useState([
    'Jan-24', 'Feb-24', 'Mar-24', 'Apr-24', 'May-24', 'Jun-24',
    'Jul-24', 'Aug-24', 'Sep-24', 'Oct-24', 'Nov-24', 'Dec-24'
  ]);

  const [selectedScenario, setSelectedScenario] = useState(scenarios[0].id);

  // Calculate projections for each scenario
  const projections = useMemo(() => {
    return scenarios.map(scenario => {
      let currentARR = baseData.startingARR;
      const monthlyData = months.map((month, index) => {
        const previousARR = currentARR;
        
        // Calculate new ARR from deals
        const avgDealSize = baseData.averageDealSize * (1 + scenario.dealSizeGrowth / 100);
        const newARR = scenario.newDealsPerMonth * avgDealSize;
        
        // Calculate churn
        const churnARR = (currentARR * scenario.churnRate) / 100;
        
        // Calculate net new ARR
        const netNewARR = newARR - churnARR;
        
        // Update current ARR
        currentARR = currentARR + netNewARR;
        
        return {
          month,
          arr_bom: previousARR,
          new_arr: newARR,
          churn_arr: -churnARR,
          net_new_arr: netNewARR,
          arr_eom: currentARR,
          growth_rate: previousARR > 0 ? ((currentARR - previousARR) / previousARR * 100) : 0
        };
      });
      
      return {
        scenario,
        data: monthlyData,
        totalGrowth: ((currentARR - baseData.startingARR) / baseData.startingARR * 100),
        endingARR: currentARR
      };
    });
  }, [scenarios, months, baseData]);

  const addScenario = () => {
    const newScenario = {
      id: Date.now().toString(),
      name: `Scenario ${scenarios.length + 1}`,
      growthRate: 10,
      churnRate: 5,
      newDealsPerMonth: 3,
      dealSizeGrowth: 0,
      color: '#' + Math.floor(Math.random()*16777215).toString(16)
    };
    setScenarios([...scenarios, newScenario]);
  };

  const updateScenario = (id: string, field: string, value: any) => {
    setScenarios(scenarios.map(s => 
      s.id === id ? { ...s, [field]: value } : s
    ));
  };

  const deleteScenario = (id: string) => {
    if (scenarios.length > 1) {
      setScenarios(scenarios.filter(s => s.id !== id));
    }
  };

  const exportScenarios = () => {
    if (onExport) {
      onExport(projections);
    } else {
      // Default export to CSV
      const csv = generateCSV();
      downloadCSV(csv, 'scenario_analysis.csv');
    }
  };

  const generateCSV = () => {
    let csv = 'Month';
    scenarios.forEach(s => {
      csv += `,${s.name} - ARR BOM,${s.name} - New ARR,${s.name} - Churn,${s.name} - ARR EOM`;
    });
    csv += '\n';
    
    months.forEach((month, idx) => {
      csv += month;
      projections.forEach(proj => {
        const data = proj.data[idx];
        csv += `,${data.arr_bom},${data.new_arr},${data.churn_arr},${data.arr_eom}`;
      });
      csv += '\n';
    });
    
    return csv;
  };

  const downloadCSV = (csv: string, filename: string) => {
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
  };

  return (
    <div className="space-y-6">
      {/* Scenario Controls */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Scenario Configuration</CardTitle>
            <div className="flex gap-2">
              <Button onClick={addScenario} size="sm">
                <Plus className="h-4 w-4 mr-1" />
                Add Scenario
              </Button>
              <Button onClick={exportScenarios} variant="outline" size="sm">
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={selectedScenario} onValueChange={setSelectedScenario}>
            <TabsList className="grid grid-cols-4 w-full">
              {scenarios.map(s => (
                <TabsTrigger key={s.id} value={s.id}>
                  {s.name}
                </TabsTrigger>
              ))}
            </TabsList>
            
            {scenarios.map(scenario => (
              <TabsContent key={scenario.id} value={scenario.id} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Scenario Name</Label>
                    <Input 
                      value={scenario.name}
                      onChange={(e) => updateScenario(scenario.id, 'name', e.target.value)}
                    />
                  </div>
                  
                  <div>
                    <Label>Color</Label>
                    <div className="flex gap-2">
                      <Input 
                        type="color"
                        value={scenario.color}
                        onChange={(e) => updateScenario(scenario.id, 'color', e.target.value)}
                        className="w-16"
                      />
                      <Input 
                        value={scenario.color}
                        onChange={(e) => updateScenario(scenario.id, 'color', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <Label>Monthly Growth Rate: {scenario.growthRate}%</Label>
                    <Slider 
                      value={[scenario.growthRate]}
                      onValueChange={(v) => updateScenario(scenario.id, 'growthRate', v[0])}
                      min={-10}
                      max={50}
                      step={1}
                    />
                  </div>
                  
                  <div>
                    <Label>Monthly Churn Rate: {scenario.churnRate}%</Label>
                    <Slider 
                      value={[scenario.churnRate]}
                      onValueChange={(v) => updateScenario(scenario.id, 'churnRate', v[0])}
                      min={0}
                      max={20}
                      step={0.5}
                    />
                  </div>
                  
                  <div>
                    <Label>New Deals per Month: {scenario.newDealsPerMonth}</Label>
                    <Slider 
                      value={[scenario.newDealsPerMonth]}
                      onValueChange={(v) => updateScenario(scenario.id, 'newDealsPerMonth', v[0])}
                      min={0}
                      max={20}
                      step={1}
                    />
                  </div>
                  
                  <div>
                    <Label>Deal Size Growth: {scenario.dealSizeGrowth}%</Label>
                    <Slider 
                      value={[scenario.dealSizeGrowth]}
                      onValueChange={(v) => updateScenario(scenario.id, 'dealSizeGrowth', v[0])}
                      min={-20}
                      max={50}
                      step={1}
                    />
                  </div>
                </div>
                
                {scenarios.length > 1 && (
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={() => deleteScenario(scenario.id)}
                  >
                    <Trash2 className="h-4 w-4 mr-1" />
                    Delete Scenario
                  </Button>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      {/* Vertical Month-by-Month Table */}
      <Card>
        <CardHeader>
          <CardTitle>Scenario Comparison Matrix</CardTitle>
          <p className="text-sm text-muted-foreground">
            Monthly progression across all scenarios
          </p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2 font-medium">Month</th>
                  {scenarios.map(s => (
                    <React.Fragment key={s.id}>
                      <th 
                        className="text-right p-2 font-medium" 
                        style={{ color: s.color }}
                        colSpan={4}
                      >
                        {s.name}
                      </th>
                    </React.Fragment>
                  ))}
                </tr>
                <tr className="border-b text-xs text-muted-foreground">
                  <th className="p-2"></th>
                  {scenarios.map(s => (
                    <React.Fragment key={s.id}>
                      <th className="text-right p-1">BOM</th>
                      <th className="text-right p-1">New</th>
                      <th className="text-right p-1">Churn</th>
                      <th className="text-right p-1">EOM</th>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {months.map((month, idx) => (
                  <tr key={month} className="border-b hover:bg-gray-50">
                    <td className="p-2 font-medium">{month}</td>
                    {projections.map(proj => {
                      const data = proj.data[idx];
                      return (
                        <React.Fragment key={proj.scenario.id}>
                          <td className="text-right p-1">
                            ${data.arr_bom.toFixed(0)}
                          </td>
                          <td className="text-right p-1 text-green-600">
                            +${data.new_arr.toFixed(0)}
                          </td>
                          <td className="text-right p-1 text-red-600">
                            {data.churn_arr.toFixed(0)}
                          </td>
                          <td className="text-right p-1 font-semibold">
                            ${data.arr_eom.toFixed(0)}
                          </td>
                        </React.Fragment>
                      );
                    })}
                  </tr>
                ))}
                
                {/* Summary Row */}
                <tr className="font-semibold bg-gray-50">
                  <td className="p-2">Total Growth</td>
                  {projections.map(proj => (
                    <td 
                      key={proj.scenario.id} 
                      colSpan={4}
                      className="text-right p-2"
                      style={{ color: proj.scenario.color }}
                    >
                      {proj.totalGrowth > 0 ? '+' : ''}{proj.totalGrowth.toFixed(1)}% 
                      (${proj.endingARR.toFixed(0)})
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Scenario Outcomes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {projections.map(proj => (
          <Card key={proj.scenario.id}>
            <CardHeader className="pb-2">
              <CardTitle 
                className="text-sm font-medium"
                style={{ color: proj.scenario.color }}
              >
                {proj.scenario.name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Starting ARR</span>
                  <span className="text-sm font-medium">${baseData.startingARR}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Ending ARR</span>
                  <span className="text-sm font-bold">${proj.endingARR.toFixed(0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Total Growth</span>
                  <span className="text-sm font-medium">
                    {proj.totalGrowth > 0 ? '+' : ''}{proj.totalGrowth.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Avg Monthly Growth</span>
                  <span className="text-sm">{proj.scenario.growthRate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-muted-foreground">Churn Rate</span>
                  <span className="text-sm">{proj.scenario.churnRate}%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};