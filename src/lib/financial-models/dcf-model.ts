/**
 * Discounted Cash Flow (DCF) Model
 * Core valuation model for intrinsic value calculation
 */

export interface DCFInputs {
  // Historical financials
  historicalRevenue: number[];
  historicalEBITDA: number[];
  historicalCapex: number[];
  historicalNWC: number[];
  
  // Projection assumptions
  revenueGrowthRates: number[];
  ebitdaMargins: number[];
  taxRate: number;
  terminalGrowthRate: number;
  
  // Discount rate components
  riskFreeRate: number;
  marketRiskPremium: number;
  beta: number;
  costOfDebt: number;
  targetDebtRatio: number;
  
  // Balance sheet items
  cashBalance: number;
  totalDebt: number;
  sharesOutstanding: number;
}

export interface DCFOutputs {
  // Projected financials
  projectedRevenue: number[];
  projectedEBITDA: number[];
  projectedEBIT: number[];
  projectedNOPAT: number[];
  projectedFCF: number[];
  
  // Valuation outputs
  wacc: number;
  terminalValue: number;
  pvOfCashFlows: number;
  pvOfTerminalValue: number;
  enterpriseValue: number;
  equityValue: number;
  impliedSharePrice: number;
  
  // Sensitivity analysis
  sensitivityMatrix: {
    waccSensitivity: number[][];
    growthSensitivity: number[][];
    marginSensitivity: number[][];
  };
  
  // Returns metrics
  irr: number;
  mirr: number;
  paybackPeriod: number;
}

export class DCFModel {
  private inputs: DCFInputs;
  private projectionYears: number = 5;
  
  constructor(inputs: DCFInputs) {
    this.inputs = inputs;
  }

  /**
   * Calculate WACC (Weighted Average Cost of Capital)
   */
  calculateWACC(): number {
    const { riskFreeRate, marketRiskPremium, beta, costOfDebt, targetDebtRatio, taxRate } = this.inputs;
    
    // Cost of Equity using CAPM
    const costOfEquity = riskFreeRate + (beta * marketRiskPremium);
    
    // After-tax cost of debt
    const afterTaxCostOfDebt = costOfDebt * (1 - taxRate);
    
    // WACC calculation
    const equityWeight = 1 - targetDebtRatio;
    const debtWeight = targetDebtRatio;
    
    const wacc = (costOfEquity * equityWeight) + (afterTaxCostOfDebt * debtWeight);
    
    return wacc;
  }

  /**
   * Project Free Cash Flows
   */
  projectCashFlows(): number[] {
    const fcf: number[] = [];
    const { revenueGrowthRates, ebitdaMargins, taxRate } = this.inputs;
    
    let currentRevenue = this.inputs.historicalRevenue[this.inputs.historicalRevenue.length - 1];
    
    for (let i = 0; i < this.projectionYears; i++) {
      // Project revenue
      currentRevenue = currentRevenue * (1 + revenueGrowthRates[i]);
      
      // Calculate EBITDA
      const ebitda = currentRevenue * ebitdaMargins[i];
      
      // Depreciation assumption (simplified)
      const depreciation = currentRevenue * 0.03; // 3% of revenue
      
      // EBIT
      const ebit = ebitda - depreciation;
      
      // NOPAT (Net Operating Profit After Tax)
      const nopat = ebit * (1 - taxRate);
      
      // Add back depreciation
      const cashFromOperations = nopat + depreciation;
      
      // Subtract Capex (as % of revenue)
      const capex = currentRevenue * 0.04; // 4% of revenue
      
      // Change in NWC (as % of revenue growth)
      const nwcChange = (currentRevenue * revenueGrowthRates[i]) * 0.1; // 10% of revenue growth
      
      // Free Cash Flow
      const freeCashFlow = cashFromOperations - capex - nwcChange;
      
      fcf.push(freeCashFlow);
    }
    
    return fcf;
  }

  /**
   * Calculate Terminal Value using Gordon Growth Model
   */
  calculateTerminalValue(lastFCF: number): number {
    const wacc = this.calculateWACC();
    const { terminalGrowthRate } = this.inputs;
    
    // Gordon Growth Model: TV = FCF(1+g) / (WACC - g)
    const terminalValue = (lastFCF * (1 + terminalGrowthRate)) / (wacc - terminalGrowthRate);
    
    return terminalValue;
  }

  /**
   * Calculate Present Value of Cash Flows
   */
  calculatePV(cashFlows: number[], discountRate: number): number {
    return cashFlows.reduce((pv, cf, index) => {
      const discountFactor = Math.pow(1 + discountRate, index + 1);
      return pv + (cf / discountFactor);
    }, 0);
  }

  /**
   * Run full DCF valuation
   */
  runValuation(): DCFOutputs {
    // Calculate WACC
    const wacc = this.calculateWACC();
    
    // Project cash flows
    const projectedFCF = this.projectCashFlows();
    
    // Calculate terminal value
    const lastFCF = projectedFCF[projectedFCF.length - 1];
    const terminalValue = this.calculateTerminalValue(lastFCF);
    
    // Calculate PV of cash flows
    const pvOfCashFlows = this.calculatePV(projectedFCF, wacc);
    
    // Calculate PV of terminal value
    const discountFactor = Math.pow(1 + wacc, this.projectionYears);
    const pvOfTerminalValue = terminalValue / discountFactor;
    
    // Enterprise Value
    const enterpriseValue = pvOfCashFlows + pvOfTerminalValue;
    
    // Equity Value
    const { cashBalance, totalDebt, sharesOutstanding } = this.inputs;
    const equityValue = enterpriseValue + cashBalance - totalDebt;
    
    // Implied share price
    const impliedSharePrice = equityValue / sharesOutstanding;
    
    // Run sensitivity analysis
    const sensitivityMatrix = this.runSensitivityAnalysis(enterpriseValue);
    
    // Calculate returns metrics
    const irr = this.calculateIRR(projectedFCF, -enterpriseValue);
    const mirr = this.calculateMIRR(projectedFCF, wacc, wacc);
    const paybackPeriod = this.calculatePaybackPeriod(projectedFCF, enterpriseValue);
    
    return {
      projectedRevenue: this.projectRevenue(),
      projectedEBITDA: this.projectEBITDA(),
      projectedEBIT: this.projectEBIT(),
      projectedNOPAT: this.projectNOPAT(),
      projectedFCF,
      wacc,
      terminalValue,
      pvOfCashFlows,
      pvOfTerminalValue,
      enterpriseValue,
      equityValue,
      impliedSharePrice,
      sensitivityMatrix,
      irr,
      mirr,
      paybackPeriod
    };
  }

  /**
   * Sensitivity Analysis
   */
  runSensitivityAnalysis(baseEV: number): any {
    const waccRange = [-0.02, -0.01, 0, 0.01, 0.02]; // +/- 2%
    const growthRange = [-0.01, -0.005, 0, 0.005, 0.01]; // +/- 1%
    
    const waccSensitivity: number[][] = [];
    const growthSensitivity: number[][] = [];
    
    const baseWACC = this.calculateWACC();
    const baseGrowth = this.inputs.terminalGrowthRate;
    
    // WACC sensitivity
    for (const waccDelta of waccRange) {
      const row: number[] = [];
      for (const growthDelta of growthRange) {
        const adjustedWACC = baseWACC + waccDelta;
        const adjustedGrowth = baseGrowth + growthDelta;
        
        // Recalculate with adjusted parameters
        const fcf = this.projectCashFlows();
        const lastFCF = fcf[fcf.length - 1];
        const tv = (lastFCF * (1 + adjustedGrowth)) / (adjustedWACC - adjustedGrowth);
        const pvCF = this.calculatePV(fcf, adjustedWACC);
        const pvTV = tv / Math.pow(1 + adjustedWACC, this.projectionYears);
        const ev = pvCF + pvTV;
        
        row.push(ev);
      }
      waccSensitivity.push(row);
    }
    
    // Margin sensitivity
    const marginSensitivity: number[][] = [];
    const marginRange = [-0.02, -0.01, 0, 0.01, 0.02]; // +/- 2%
    
    for (const marginDelta of marginRange) {
      const row: number[] = [];
      for (const growthDelta of growthRange) {
        // Adjust margins and recalculate
        const adjustedMargins = this.inputs.ebitdaMargins.map(m => m + marginDelta);
        const tempInputs = { ...this.inputs, ebitdaMargins: adjustedMargins };
        const tempModel = new DCFModel(tempInputs);
        const result = tempModel.runValuation();
        row.push(result.enterpriseValue);
      }
      marginSensitivity.push(row);
    }
    
    return {
      waccSensitivity,
      growthSensitivity: waccSensitivity, // Using same for simplicity
      marginSensitivity
    };
  }

  /**
   * Helper methods for projections
   */
  private projectRevenue(): number[] {
    const revenue: number[] = [];
    let current = this.inputs.historicalRevenue[this.inputs.historicalRevenue.length - 1];
    
    for (let i = 0; i < this.projectionYears; i++) {
      current = current * (1 + this.inputs.revenueGrowthRates[i]);
      revenue.push(current);
    }
    
    return revenue;
  }

  private projectEBITDA(): number[] {
    const revenue = this.projectRevenue();
    return revenue.map((rev, i) => rev * this.inputs.ebitdaMargins[i]);
  }

  private projectEBIT(): number[] {
    const ebitda = this.projectEBITDA();
    const revenue = this.projectRevenue();
    return ebitda.map((ebitda, i) => ebitda - (revenue[i] * 0.03)); // 3% depreciation
  }

  private projectNOPAT(): number[] {
    const ebit = this.projectEBIT();
    return ebit.map(e => e * (1 - this.inputs.taxRate));
  }

  /**
   * IRR Calculation using Newton's method
   */
  private calculateIRR(cashFlows: number[], initialInvestment: number): number {
    const maxIterations = 100;
    const tolerance = 0.00001;
    let rate = 0.1; // Initial guess
    
    for (let i = 0; i < maxIterations; i++) {
      let npv = initialInvestment;
      let dnpv = 0;
      
      for (let j = 0; j < cashFlows.length; j++) {
        const factor = Math.pow(1 + rate, j + 1);
        npv += cashFlows[j] / factor;
        dnpv -= (j + 1) * cashFlows[j] / Math.pow(1 + rate, j + 2);
      }
      
      const newRate = rate - npv / dnpv;
      
      if (Math.abs(newRate - rate) < tolerance) {
        return newRate;
      }
      
      rate = newRate;
    }
    
    return rate;
  }

  /**
   * MIRR Calculation
   */
  private calculateMIRR(cashFlows: number[], financeRate: number, reinvestRate: number): number {
    const n = cashFlows.length;
    
    // Calculate future value of positive cash flows
    let fvPositive = 0;
    for (let i = 0; i < n; i++) {
      if (cashFlows[i] > 0) {
        fvPositive += cashFlows[i] * Math.pow(1 + reinvestRate, n - i - 1);
      }
    }
    
    // Calculate present value of negative cash flows
    let pvNegative = 0;
    for (let i = 0; i < n; i++) {
      if (cashFlows[i] < 0) {
        pvNegative += cashFlows[i] / Math.pow(1 + financeRate, i);
      }
    }
    
    // MIRR calculation
    const mirr = Math.pow(fvPositive / Math.abs(pvNegative), 1 / n) - 1;
    
    return mirr;
  }

  /**
   * Payback Period Calculation
   */
  private calculatePaybackPeriod(cashFlows: number[], initialInvestment: number): number {
    let cumulative = -initialInvestment;
    
    for (let i = 0; i < cashFlows.length; i++) {
      cumulative += cashFlows[i];
      if (cumulative >= 0) {
        // Linear interpolation for partial year
        const previousCumulative = cumulative - cashFlows[i];
        const partialYear = Math.abs(previousCumulative) / cashFlows[i];
        return i + partialYear;
      }
    }
    
    return cashFlows.length; // Not paid back within projection period
  }

  /**
   * Export to Excel-compatible format
   */
  exportToExcel(): any {
    const outputs = this.runValuation();
    
    return {
      assumptions: {
        'Revenue Growth': this.inputs.revenueGrowthRates,
        'EBITDA Margins': this.inputs.ebitdaMargins,
        'Tax Rate': this.inputs.taxRate,
        'Terminal Growth': this.inputs.terminalGrowthRate,
        'WACC': outputs.wacc
      },
      projections: {
        'Revenue': outputs.projectedRevenue,
        'EBITDA': outputs.projectedEBITDA,
        'EBIT': outputs.projectedEBIT,
        'NOPAT': outputs.projectedNOPAT,
        'Free Cash Flow': outputs.projectedFCF
      },
      valuation: {
        'PV of Cash Flows': outputs.pvOfCashFlows,
        'Terminal Value': outputs.terminalValue,
        'PV of Terminal Value': outputs.pvOfTerminalValue,
        'Enterprise Value': outputs.enterpriseValue,
        'Less: Net Debt': this.inputs.totalDebt - this.inputs.cashBalance,
        'Equity Value': outputs.equityValue,
        'Shares Outstanding': this.inputs.sharesOutstanding,
        'Implied Share Price': outputs.impliedSharePrice
      },
      sensitivity: outputs.sensitivityMatrix
    };
  }
}

// Helper function for quick DCF valuation
export function quickDCF(
  revenue: number,
  growthRate: number,
  ebitdaMargin: number,
  wacc: number,
  terminalGrowth: number
): number {
  const projectionYears = 5;
  const fcf: number[] = [];
  
  for (let i = 0; i < projectionYears; i++) {
    revenue = revenue * (1 + growthRate);
    const ebitda = revenue * ebitdaMargin;
    const ebit = ebitda * 0.9; // 10% D&A
    const nopat = ebit * 0.75; // 25% tax
    const fcfValue = nopat * 0.8; // 20% reinvestment
    fcf.push(fcfValue);
  }
  
  const terminalValue = (fcf[fcf.length - 1] * (1 + terminalGrowth)) / (wacc - terminalGrowth);
  
  let enterpriseValue = 0;
  for (let i = 0; i < fcf.length; i++) {
    enterpriseValue += fcf[i] / Math.pow(1 + wacc, i + 1);
  }
  enterpriseValue += terminalValue / Math.pow(1 + wacc, projectionYears);
  
  return enterpriseValue;
}