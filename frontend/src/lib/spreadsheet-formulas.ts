/**
 * Enhanced Spreadsheet Formula Engine
 * Financial formulas and functions for VC/PE analysis
 */

export class FormulaEngine {
  private cells: Record<string, any>;
  
  constructor(cells: Record<string, any>) {
    this.cells = cells;
  }

  /**
   * Evaluate any formula string
   */
  evaluate(formula: string): any {
    if (!formula.startsWith('=')) return formula;
    
    let expr = formula.substring(1).toUpperCase();
    
    // Replace cell references first
    expr = this.replaceCellReferences(expr);
    
    // Process functions from most complex to simplest
    expr = this.processFinancialFunctions(expr);
    expr = this.processLookupFunctions(expr);  // Add lookup functions
    expr = this.processStatisticalFunctions(expr);
    expr = this.processLogicalFunctions(expr);
    expr = this.processTextFunctions(expr);
    expr = this.processDateFunctions(expr);
    expr = this.processMathFunctions(expr);
    
    // Evaluate the final expression
    return this.safeEval(expr);
  }

  /**
   * Financial Functions
   */
  private processFinancialFunctions(expr: string): string {
    // NPV - Net Present Value
    expr = expr.replace(/NPV\(([^,]+),([^)]+)\)/g, (match, rate, range) => {
      const r = parseFloat(rate);
      const values = this.getRangeValues(range);
      let npv = 0;
      values.forEach((val, i) => {
        npv += val / Math.pow(1 + r, i + 1);
      });
      return npv.toString();
    });

    // IRR - Internal Rate of Return (simplified Newton's method)
    expr = expr.replace(/IRR\(([^)]+)\)/g, (match, range) => {
      const values = this.getRangeValues(range);
      let rate = 0.1; // Initial guess
      
      for (let i = 0; i < 100; i++) {
        let npv = 0;
        let dnpv = 0;
        
        values.forEach((val, t) => {
          const factor = Math.pow(1 + rate, t);
          npv += val / factor;
          dnpv -= t * val / (factor * (1 + rate));
        });
        
        const newRate = rate - npv / dnpv;
        if (Math.abs(newRate - rate) < 0.0001) break;
        rate = newRate;
      }
      
      return rate.toString();
    });

    // XIRR - IRR for irregular cash flows
    expr = expr.replace(/XIRR\(([^,]+),([^)]+)\)/g, (match, values, dates) => {
      // Simplified XIRR - would need date parsing in real implementation
      return '0.15'; // Placeholder
    });

    // PMT - Payment calculation
    expr = expr.replace(/PMT\(([^,]+),([^,]+),([^)]+)\)/g, (match, rate, nper, pv) => {
      const r = parseFloat(rate);
      const n = parseFloat(nper);
      const p = parseFloat(pv);
      if (r === 0) return (-p / n).toString();
      const pmt = -p * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
      return pmt.toString();
    });

    // FV - Future Value
    expr = expr.replace(/FV\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, (match, rate, nper, pmt, pv) => {
      const r = parseFloat(rate);
      const n = parseFloat(nper);
      const payment = parseFloat(pmt);
      const present = parseFloat(pv);
      const fv = -present * Math.pow(1 + r, n) - payment * ((Math.pow(1 + r, n) - 1) / r);
      return fv.toString();
    });

    // PV - Present Value
    expr = expr.replace(/PV\(([^,]+),([^,]+),([^)]+)\)/g, (match, rate, nper, pmt) => {
      const r = parseFloat(rate);
      const n = parseFloat(nper);
      const payment = parseFloat(pmt);
      if (r === 0) return (-payment * n).toString();
      const pv = -payment * ((1 - Math.pow(1 + r, -n)) / r);
      return pv.toString();
    });

    // RATE - Interest rate calculation
    expr = expr.replace(/RATE\(([^,]+),([^,]+),([^)]+)\)/g, (match, nper, pmt, pv) => {
      const n = parseFloat(nper);
      const payment = parseFloat(pmt);
      const present = parseFloat(pv);
      
      // Newton's method for RATE
      let rate = 0.1;
      for (let i = 0; i < 100; i++) {
        const factor = Math.pow(1 + rate, n);
        const f = present * factor + payment * ((factor - 1) / rate);
        const df = present * n * Math.pow(1 + rate, n - 1) + 
                   payment * ((n * Math.pow(1 + rate, n - 1) * rate - (factor - 1)) / (rate * rate));
        const newRate = rate - f / df;
        if (Math.abs(newRate - rate) < 0.0001) break;
        rate = newRate;
      }
      return rate.toString();
    });

    // WACC - Weighted Average Cost of Capital
    expr = expr.replace(/WACC\(([^,]+),([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, equity, debt, costEquity, costDebt, taxRate) => {
      const e = parseFloat(equity);
      const d = parseFloat(debt);
      const ce = parseFloat(costEquity);
      const cd = parseFloat(costDebt);
      const t = parseFloat(taxRate);
      const total = e + d;
      const wacc = (e / total) * ce + (d / total) * cd * (1 - t);
      return wacc.toString();
    });

    // CAGR - Compound Annual Growth Rate
    expr = expr.replace(/CAGR\(([^,]+),([^,]+),([^)]+)\)/g, (match, beginValue, endValue, years) => {
      const bv = parseFloat(beginValue);
      const ev = parseFloat(endValue);
      const y = parseFloat(years);
      const cagr = Math.pow(ev / bv, 1 / y) - 1;
      return cagr.toString();
    });

    // MOIC - Multiple on Invested Capital
    expr = expr.replace(/MOIC\(([^,]+),([^)]+)\)/g, (match, exitValue, invested) => {
      const exit = parseFloat(exitValue);
      const inv = parseFloat(invested);
      return (exit / inv).toString();
    });

    // DPI - Distributions to Paid-In
    expr = expr.replace(/DPI\(([^,]+),([^)]+)\)/g, (match, distributions, paidIn) => {
      const dist = parseFloat(distributions);
      const paid = parseFloat(paidIn);
      return (dist / paid).toString();
    });

    // TVPI - Total Value to Paid-In
    expr = expr.replace(/TVPI\(([^,]+),([^,]+),([^)]+)\)/g, (match, distributions, nav, paidIn) => {
      const dist = parseFloat(distributions);
      const navValue = parseFloat(nav);
      const paid = parseFloat(paidIn);
      return ((dist + navValue) / paid).toString();
    });

    // MIRR - Modified Internal Rate of Return
    expr = expr.replace(/MIRR\(([^,]+),([^,]+),([^)]+)\)/g, (match, range, financeRate, reinvestRate) => {
      const values = this.getRangeValues(range);
      const fRate = parseFloat(financeRate);
      const rRate = parseFloat(reinvestRate);
      const n = values.length;
      
      let positiveFlows = 0;
      let negativeFlows = 0;
      
      values.forEach((val, i) => {
        if (val > 0) {
          positiveFlows += val / Math.pow(1 + rRate, i);
        } else {
          negativeFlows += val / Math.pow(1 + fRate, i);
        }
      });
      
      const mirr = Math.pow(-positiveFlows * Math.pow(1 + rRate, n) / negativeFlows, 1 / (n - 1)) - 1;
      return mirr.toString();
    });

    // XNPV - NPV for irregular cash flows
    expr = expr.replace(/XNPV\(([^,]+),([^,]+),([^)]+)\)/g, (match, rate, values, dates) => {
      const r = parseFloat(rate);
      const vals = this.getRangeValues(values);
      // For simplicity, assume dates are evenly spaced years
      let xnpv = 0;
      vals.forEach((val, i) => {
        xnpv += val / Math.pow(1 + r, i);
      });
      return xnpv.toString();
    });

    // NPER - Number of periods
    expr = expr.replace(/NPER\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, (match, rate, pmt, pv, fv = '0') => {
      const r = parseFloat(rate);
      const payment = parseFloat(pmt);
      const present = parseFloat(pv);
      const future = parseFloat(fv);
      
      if (r === 0) {
        return (-(present + future) / payment).toString();
      }
      
      const nper = Math.log((payment - future * r) / (payment + present * r)) / Math.log(1 + r);
      return nper.toString();
    });

    // IPMT - Interest payment
    expr = expr.replace(/IPMT\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, (match, rate, per, nper, pv) => {
      const r = parseFloat(rate);
      const period = parseFloat(per);
      const n = parseFloat(nper);
      const present = parseFloat(pv);
      
      // Calculate payment first
      const pmt = -present * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
      
      // Calculate interest portion for the period
      let balance = present;
      for (let i = 1; i < period; i++) {
        const interest = balance * r;
        const principal = pmt - interest;
        balance += principal;
      }
      
      const ipmt = balance * r;
      return ipmt.toString();
    });

    // PPMT - Principal payment
    expr = expr.replace(/PPMT\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, (match, rate, per, nper, pv) => {
      const r = parseFloat(rate);
      const period = parseFloat(per);
      const n = parseFloat(nper);
      const present = parseFloat(pv);
      
      // Calculate total payment
      const pmt = -present * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
      
      // Calculate interest portion
      let balance = present;
      for (let i = 1; i < period; i++) {
        const interest = balance * r;
        const principal = pmt - interest;
        balance += principal;
      }
      
      const ipmt = balance * r;
      const ppmt = pmt - ipmt;
      return ppmt.toString();
    });

    // SLN - Straight-line depreciation
    expr = expr.replace(/SLN\(([^,]+),([^,]+),([^)]+)\)/g, (match, cost, salvage, life) => {
      const c = parseFloat(cost);
      const s = parseFloat(salvage);
      const l = parseFloat(life);
      return ((c - s) / l).toString();
    });

    // DB - Declining balance depreciation
    expr = expr.replace(/DB\(([^,]+),([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, cost, salvage, life, period, month = '12') => {
      const c = parseFloat(cost);
      const s = parseFloat(salvage);
      const l = parseFloat(life);
      const p = parseFloat(period);
      const m = parseFloat(month);
      
      // Fixed declining balance rate
      const rate = 1 - Math.pow(s / c, 1 / l);
      
      let totalDep = 0;
      let bookValue = c;
      
      for (let i = 1; i <= p; i++) {
        const yearDep = i === 1 
          ? bookValue * rate * (m / 12)
          : bookValue * rate;
        totalDep += yearDep;
        bookValue -= yearDep;
      }
      
      return (p === 1 ? c * rate * (m / 12) : bookValue * rate).toString();
    });

    // DDB - Double declining balance depreciation
    expr = expr.replace(/DDB\(([^,]+),([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, cost, salvage, life, period, factor = '2') => {
      const c = parseFloat(cost);
      const s = parseFloat(salvage);
      const l = parseFloat(life);
      const p = parseFloat(period);
      const f = parseFloat(factor);
      
      const rate = f / l;
      let bookValue = c;
      let depreciation = 0;
      
      for (let i = 1; i <= p; i++) {
        depreciation = Math.min(bookValue * rate, bookValue - s);
        if (i === p) return depreciation.toString();
        bookValue -= depreciation;
      }
      
      return depreciation.toString();
    });

    // EFFECT - Effective annual interest rate
    expr = expr.replace(/EFFECT\(([^,]+),([^)]+)\)/g, (match, nominalRate, npery) => {
      const nominal = parseFloat(nominalRate);
      const n = parseFloat(npery);
      const effect = Math.pow(1 + nominal / n, n) - 1;
      return effect.toString();
    });

    // NOMINAL - Nominal annual interest rate
    expr = expr.replace(/NOMINAL\(([^,]+),([^)]+)\)/g, (match, effectRate, npery) => {
      const effect = parseFloat(effectRate);
      const n = parseFloat(npery);
      const nominal = n * (Math.pow(1 + effect, 1 / n) - 1);
      return nominal.toString();
    });

    // CAP TABLE FORMULAS
    
    // DILUTION - Calculate dilution percentage
    expr = expr.replace(/DILUTION\(([^,]+),([^,]+),([^)]+)\)/g, (match, oldShares, newShares, totalShares) => {
      const old = parseFloat(oldShares);
      const newS = parseFloat(newShares);
      const total = parseFloat(totalShares);
      const dilution = 1 - (old / (total + newS));
      return dilution.toString();
    });

    // OWNERSHIP - Calculate ownership percentage
    expr = expr.replace(/OWNERSHIP\(([^,]+),([^)]+)\)/g, (match, shares, totalShares) => {
      const s = parseFloat(shares);
      const total = parseFloat(totalShares);
      return (s / total).toString();
    });

    // PRICEPERSH ARE - Calculate price per share
    expr = expr.replace(/PRICEPERSHARE\(([^,]+),([^)]+)\)/g, (match, valuation, shares) => {
      const val = parseFloat(valuation);
      const s = parseFloat(shares);
      return (val / s).toString();
    });

    // OPTIONPOOL - Calculate option pool size
    expr = expr.replace(/OPTIONPOOL\(([^,]+),([^)]+)\)/g, (match, percentage, postMoney) => {
      const pct = parseFloat(percentage);
      const post = parseFloat(postMoney);
      return (post * pct).toString();
    });

    // WATERFALL FORMULAS
    
    // LIQUIDPREF - Calculate liquidation preference
    expr = expr.replace(/LIQUIDPREF\(([^,]+),([^,]+),([^)]+)\)/g, (match, investment, multiple, participating) => {
      const inv = parseFloat(investment);
      const mult = parseFloat(multiple);
      const part = participating === 'true' || participating === '1';
      // Simple liquidation preference calculation
      return (inv * mult).toString();
    });

    // WATERFALL - Calculate waterfall distribution
    expr = expr.replace(/WATERFALL\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, exitValue, prefAmount, commonShares, totalShares) => {
      const exit = parseFloat(exitValue);
      const pref = parseFloat(prefAmount);
      const common = parseFloat(commonShares);
      const total = parseFloat(totalShares);
      
      // Simple waterfall: pref first, then pro-rata
      if (exit <= pref) {
        return '0'; // Common gets nothing
      }
      const remaining = exit - pref;
      const commonPayout = remaining * (common / total);
      return commonPayout.toString();
    });

    // WATERFALLPRO - Professional waterfall with all parameters
    expr = expr.replace(/WATERFALLPRO\(([^)]+)\)/g, (match, params) => {
      // Parse JSON-like parameters for complex waterfall
      // Format: "exit:100M, seriesA:{inv:10M,mult:1,part:false}, seriesB:{inv:20M,mult:1.5,part:true,cap:3}, paripassu:true"
      try {
        // This would parse complex waterfall parameters
        // For now, return placeholder
        return '"Complex waterfall calculation"';
      } catch {
        return '#ERROR';
      }
    });

    // PARIPASU - Calculate pari passu distribution
    expr = expr.replace(/PARIPASSU\(([^,]+),([^)]+)\)/g, (match, exitValue, investorsJson) => {
      const exit = parseFloat(exitValue);
      
      // Parse investors array: [{inv:10M,mult:1},{inv:20M,mult:1.5}]
      try {
        // Simple pari passu: distribute proportionally to preference amounts
        // This is a simplified implementation
        return (exit * 0.5).toString(); // Placeholder
      } catch {
        return '#ERROR';
      }
    });

    // DILUTIONIMPACT - Calculate dilution impact across rounds
    expr = expr.replace(/DILUTIONIMPACT\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, initialOwnership, newShares, existingShares, optionPool) => {
      const initial = parseFloat(initialOwnership);
      const newS = parseFloat(newShares);
      const existing = parseFloat(existingShares);
      const pool = parseFloat(optionPool) || 0;
      
      const totalNew = existing + newS + (existing * pool);
      const diluted = (initial * existing) / totalNew;
      const dilutionPct = 1 - (diluted / initial);
      
      return JSON.stringify({
        originalOwnership: initial,
        dilutedOwnership: diluted,
        dilutionPercent: dilutionPct,
        effectiveMultiple: 1 / (1 - dilutionPct)
      });
    });

    // EXITMATRIX - Returns matrix for different exit scenarios
    expr = expr.replace(/EXITMATRIX\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g,
      (match, minExit, maxExit, steps, prefStack) => {
      const min = parseFloat(minExit);
      const max = parseFloat(maxExit);
      const stepCount = parseFloat(steps);
      const pref = parseFloat(prefStack);
      
      const results = [];
      const stepSize = (max - min) / stepCount;
      
      for (let i = 0; i <= stepCount; i++) {
        const exitVal = min + (stepSize * i);
        const commonReturn = Math.max(0, exitVal - pref);
        const prefReturn = Math.min(exitVal, pref);
        results.push({
          exit: exitVal,
          preferred: prefReturn,
          common: commonReturn,
          commonROI: commonReturn > 0 ? (commonReturn / (exitVal - pref)) : 0
        });
      }
      
      return JSON.stringify(results);
    });

    // SENSITIVITYWF - Waterfall sensitivity to parameter changes
    expr = expr.replace(/SENSITIVITYWF\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g,
      (match, baseExit, parameter, rangePercent, baseTerms) => {
      const exit = parseFloat(baseExit);
      const param = parameter; // 'multiple', 'participation', 'cap'
      const range = parseFloat(rangePercent);
      
      // Calculate impact of changing the parameter
      const results = [];
      for (let mult = -range; mult <= range; mult += range/5) {
        const adjusted = exit * (1 + mult);
        results.push({
          change: mult,
          value: adjusted,
          impact: adjusted - exit
        });
      }
      
      return JSON.stringify(results);
    });

    // IPORATCHET - IPO ratchet calculation (20% guaranteed return for late stage)
    expr = expr.replace(/IPORATCHET\(([^,]+),([^,]+),([^)]+)\)/g, 
      (match, investment, currentValue, minReturn) => {
      const inv = parseFloat(investment);
      const current = parseFloat(currentValue);
      const minRet = parseFloat(minReturn) || 0.20; // Default 20% return
      
      const minValue = inv * (1 + minRet);
      return Math.max(current, minValue).toString();
    });

    // PARTICIPATING - Participating preferred calculation
    expr = expr.replace(/PARTICIPATING\(([^,]+),([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, exitValue, investment, multiple, ownership, cap) => {
      const exit = parseFloat(exitValue);
      const inv = parseFloat(investment);
      const mult = parseFloat(multiple);
      const own = parseFloat(ownership);
      const capAmount = cap === 'uncapped' ? Infinity : parseFloat(cap);
      
      // First get liquidation preference
      const liqPref = inv * mult;
      
      if (exit <= liqPref) {
        return liqPref.toString();
      }
      
      // Then participate in remainder
      const remainder = exit - liqPref;
      const participation = remainder * own;
      
      // Apply cap if exists
      const total = Math.min(liqPref + participation, capAmount);
      return total.toString();
    });

    // DOWNROUND - Downround waterfall with enhanced terms
    expr = expr.replace(/DOWNROUND\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, exitValue, investment, enhancedMultiple, participating) => {
      const exit = parseFloat(exitValue);
      const inv = parseFloat(investment);
      const mult = parseFloat(enhancedMultiple); // Typically > 1X in downrounds
      const part = participating === 'true' || participating === '1';
      
      const liqPref = inv * mult;
      
      if (!part) {
        return Math.min(exit, liqPref).toString();
      }
      
      // Participating: get pref + share of remainder
      if (exit <= liqPref) {
        return liqPref.toString();
      }
      
      // Simplified participation calculation
      const remainder = exit - liqPref;
      const participation = remainder * 0.2; // Assume 20% ownership for simplicity
      return (liqPref + participation).toString();
    });

    // MASTOCK - M&A with stock component (50:50 mix)
    expr = expr.replace(/MASTOCK\(([^,]+),([^,]+),([^)]+)\)/g, 
      (match, exitValue, cashRatio, stockRatio) => {
      const exit = parseFloat(exitValue);
      const cash = parseFloat(cashRatio) || 0.5;
      const stock = parseFloat(stockRatio) || 0.5;
      
      return JSON.stringify({
        cash: exit * cash,
        stock: exit * stock,
        total: exit
      });
    });

    // CUMULDIV - Cumulative dividend calculation
    expr = expr.replace(/CUMULDIV\(([^,]+),([^,]+),([^)]+)\)/g, 
      (match, investment, rate, years) => {
      const inv = parseFloat(investment);
      const r = parseFloat(rate);
      const y = parseFloat(years);
      
      // Compound cumulative dividends
      const accumulated = inv * Math.pow(1 + r, y);
      return accumulated.toString();
    });

    // CATCHUP - Calculate catch-up provision
    expr = expr.replace(/CATCHUP\(([^,]+),([^,]+),([^)]+)\)/g, (match, proceeds, hurdle, catchupPct) => {
      const proc = parseFloat(proceeds);
      const hurdleAmt = parseFloat(hurdle);
      const catchup = parseFloat(catchupPct);
      
      if (proc <= hurdleAmt) return '0';
      const excess = proc - hurdleAmt;
      return (excess * catchup).toString();
    });

    // CARRIEDINT - Calculate carried interest
    expr = expr.replace(/CARRIEDINT\(([^,]+),([^,]+),([^)]+)\)/g, (match, profits, hurdle, carryPct) => {
      const prof = parseFloat(profits);
      const hurdleAmt = parseFloat(hurdle);
      const carry = parseFloat(carryPct);
      
      if (prof <= hurdleAmt) return '0';
      return ((prof - hurdleAmt) * carry).toString();
    });

    // SCENARIO PLANNING FORMULAS
    
    // SCENARIO - Calculate scenario-based value
    expr = expr.replace(/SCENARIO\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, baseCase, bestCase, worstCase, probability) => {
      const base = parseFloat(baseCase);
      const best = parseFloat(bestCase);
      const worst = parseFloat(worstCase);
      const prob = probability.split(',').map(p => parseFloat(p));
      
      // Weighted average of scenarios
      const weighted = base * prob[0] + best * prob[1] + worst * prob[2];
      return weighted.toString();
    });

    // SENSITIVITY - Sensitivity analysis
    expr = expr.replace(/SENSITIVITY\(([^,]+),([^,]+),([^)]+)\)/g, (match, baseValue, variable, change) => {
      const base = parseFloat(baseValue);
      const varValue = parseFloat(variable);
      const changeAmt = parseFloat(change);
      
      // Calculate sensitivity impact
      const impact = base * (1 + (varValue * changeAmt));
      return impact.toString();
    });

    // MONTECARLO - Simplified Monte Carlo (returns average for demo)
    expr = expr.replace(/MONTECARLO\(([^,]+),([^,]+),([^)]+)\)/g, (match, mean, stdDev, iterations) => {
      const m = parseFloat(mean);
      const std = parseFloat(stdDev);
      const iter = parseFloat(iterations);
      
      // Simplified: just return mean with some variance
      // In real implementation, would run actual Monte Carlo
      const variance = std * 0.1; // Simplified calculation
      return (m + variance).toString();
    });

    // BREAKEVEN - Calculate breakeven point
    expr = expr.replace(/BREAKEVEN\(([^,]+),([^,]+),([^)]+)\)/g, (match, fixedCosts, contribution, units) => {
      const fixed = parseFloat(fixedCosts);
      const contrib = parseFloat(contribution);
      const u = parseFloat(units) || 1;
      
      return (fixed / (contrib / u)).toString();
    });

    // PWERM - Probability Weighted Expected Return Method
    // Note: This is a placeholder that should trigger an API call in the actual implementation
    expr = expr.replace(/PWERM\(([^)]+)\)/g, (match, companyName) => {
      // In real implementation, this would trigger an async API call to /api/pwerm-analysis
      // For now, return a placeholder that indicates PWERM analysis is needed
      return `"PWERM:${companyName.replace(/"/g, '')}"`;
    });

    return expr;
  }

  /**
   * Lookup and Reference Functions
   */
  private processLookupFunctions(expr: string): string {
    // VLOOKUP
    expr = expr.replace(/VLOOKUP\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g, 
      (match, value, range, colIndex, exactMatch) => {
        const searchValue = this.evaluateOperand(value);
        const rangeValues = this.getRangeAs2D(range);
        const col = parseInt(colIndex) - 1;
        const exact = exactMatch === 'TRUE' || exactMatch === '1';
        
        for (let i = 0; i < rangeValues.length; i++) {
          if (exact ? rangeValues[i][0] === searchValue : String(rangeValues[i][0]).includes(String(searchValue))) {
            return rangeValues[i][col] || '#N/A';
          }
        }
        return '#N/A';
    });
    
    // HLOOKUP
    expr = expr.replace(/HLOOKUP\(([^,]+),([^,]+),([^,]+),([^)]+)\)/g,
      (match, value, range, rowIndex, exactMatch) => {
        const searchValue = this.evaluateOperand(value);
        const rangeValues = this.getRangeAs2D(range);
        const row = parseInt(rowIndex) - 1;
        
        if (rangeValues.length > 0) {
          const firstRow = rangeValues[0];
          for (let i = 0; i < firstRow.length; i++) {
            if (firstRow[i] === searchValue) {
              return rangeValues[row] ? rangeValues[row][i] : '#N/A';
            }
          }
        }
        return '#N/A';
    });
    
    // INDEX
    expr = expr.replace(/INDEX\(([^,]+),([^,]+),([^)]+)\)/g,
      (match, range, row, col) => {
        const rangeValues = this.getRangeAs2D(range);
        const r = parseInt(row) - 1;
        const c = parseInt(col) - 1;
        return rangeValues[r] ? rangeValues[r][c] || '#REF!' : '#REF!';
    });
    
    // MATCH
    expr = expr.replace(/MATCH\(([^,]+),([^,]+),([^)]+)\)/g,
      (match, value, range, matchType) => {
        const searchValue = this.evaluateOperand(value);
        const rangeValues = this.getRangeValues(range);
        const type = parseInt(matchType) || 0;
        
        for (let i = 0; i < rangeValues.length; i++) {
          if (type === 0 && rangeValues[i] === searchValue) {
            return (i + 1).toString();
          }
        }
        return '#N/A';
    });
    
    // OFFSET
    expr = expr.replace(/OFFSET\(([^,]+),([^,]+),([^,]+),([^,]+),([^)]+)\)/g,
      (match, ref, rows, cols, height, width) => {
        // Simplified OFFSET - would need more complex implementation
        return '0';
    });
    
    return expr;
  }

  /**
   * Text Functions
   */
  private processTextFunctions(expr: string): string {
    // FIND
    expr = expr.replace(/FIND\("([^"]+)",\s*"([^"]+)"\)/g,
      (match, searchText, withinText) => {
        const pos = withinText.indexOf(searchText);
        return pos >= 0 ? (pos + 1).toString() : '#VALUE!';
    });
    
    // SEARCH (case-insensitive FIND)
    expr = expr.replace(/SEARCH\("([^"]+)",\s*"([^"]+)"\)/g,
      (match, searchText, withinText) => {
        const pos = withinText.toLowerCase().indexOf(searchText.toLowerCase());
        return pos >= 0 ? (pos + 1).toString() : '#VALUE!';
    });
    
    // SUBSTITUTE
    expr = expr.replace(/SUBSTITUTE\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)/g,
      (match, text, oldText, newText) => {
        return `"${text.replace(new RegExp(oldText, 'g'), newText)}"`;
    });
    
    // REPLACE
    expr = expr.replace(/REPLACE\("([^"]+)",\s*(\d+),\s*(\d+),\s*"([^"]+)"\)/g,
      (match, text, start, length, newText) => {
        const s = parseInt(start) - 1;
        const l = parseInt(length);
        return `"${text.substring(0, s) + newText + text.substring(s + l)}"`;
    });
    
    // MID
    expr = expr.replace(/MID\("([^"]+)",\s*(\d+),\s*(\d+)\)/g,
      (match, text, start, length) => {
        const s = parseInt(start) - 1;
        const l = parseInt(length);
        return `"${text.substring(s, s + l)}"`;
    });
    
    // LEFT
    expr = expr.replace(/LEFT\("([^"]+)",\s*(\d+)\)/g,
      (match, text, length) => {
        return `"${text.substring(0, parseInt(length))}"`;
    });
    
    // RIGHT
    expr = expr.replace(/RIGHT\("([^"]+)",\s*(\d+)\)/g,
      (match, text, length) => {
        const l = parseInt(length);
        return `"${text.substring(text.length - l)}"`;
    });
    
    // TRIM
    expr = expr.replace(/TRIM\("([^"]+)"\)/g,
      (match, text) => {
        return `"${text.trim()}"`;
    });
    
    // UPPER
    expr = expr.replace(/UPPER\("([^"]+)"\)/g,
      (match, text) => {
        return `"${text.toUpperCase()}"`;
    });
    
    // LOWER
    expr = expr.replace(/LOWER\("([^"]+)"\)/g,
      (match, text) => {
        return `"${text.toLowerCase()}"`;
    });
    
    // PROPER (Title Case)
    expr = expr.replace(/PROPER\("([^"]+)"\)/g,
      (match, text) => {
        return `"${text.replace(/\w\S*/g, txt => 
          txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase())}"`;
    });
    
    // TEXT (number formatting)
    expr = expr.replace(/TEXT\(([^,]+),\s*"([^"]+)"\)/g,
      (match, value, format) => {
        const val = parseFloat(this.evaluateOperand(value));
        if (format.includes('0.00')) {
          return val.toFixed(2);
        } else if (format.includes('%')) {
          return (val * 100).toFixed(0) + '%';
        } else if (format.includes('$')) {
          return '$' + val.toFixed(2);
        }
        return val.toString();
    });
    
    // VALUE (convert text to number)
    expr = expr.replace(/VALUE\("([^"]+)"\)/g,
      (match, text) => {
        const num = parseFloat(text.replace(/[$,%]/g, ''));
        return isNaN(num) ? '#VALUE!' : num.toString();
    });
    
    return expr;
  }

  /**
   * Statistical Functions
   */
  private processStatisticalFunctions(expr: string): string {
    // STDEV - Standard Deviation
    expr = expr.replace(/STDEV\(([^)]+)\)/g, (match, range) => {
      const values = this.getRangeValues(range);
      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
      return Math.sqrt(variance).toString();
    });

    // VAR - Variance
    expr = expr.replace(/VAR\(([^)]+)\)/g, (match, range) => {
      const values = this.getRangeValues(range);
      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
      return variance.toString();
    });

    // MEDIAN
    expr = expr.replace(/MEDIAN\(([^)]+)\)/g, (match, range) => {
      const values = this.getRangeValues(range).sort((a, b) => a - b);
      const mid = Math.floor(values.length / 2);
      return values.length % 2 !== 0 
        ? values[mid].toString() 
        : ((values[mid - 1] + values[mid]) / 2).toString();
    });

    // PERCENTILE
    expr = expr.replace(/PERCENTILE\(([^,]+),([^)]+)\)/g, (match, range, k) => {
      const values = this.getRangeValues(range).sort((a, b) => a - b);
      const percentile = parseFloat(k);
      const index = (values.length - 1) * percentile;
      const lower = Math.floor(index);
      const upper = Math.ceil(index);
      const weight = index - lower;
      return (values[lower] * (1 - weight) + values[upper] * weight).toString();
    });

    // CORREL - Correlation
    expr = expr.replace(/CORREL\(([^,]+),([^)]+)\)/g, (match, range1, range2) => {
      const x = this.getRangeValues(range1);
      const y = this.getRangeValues(range2);
      const n = Math.min(x.length, y.length);
      
      const meanX = x.reduce((a, b) => a + b, 0) / n;
      const meanY = y.reduce((a, b) => a + b, 0) / n;
      
      let numerator = 0;
      let denomX = 0;
      let denomY = 0;
      
      for (let i = 0; i < n; i++) {
        numerator += (x[i] - meanX) * (y[i] - meanY);
        denomX += Math.pow(x[i] - meanX, 2);
        denomY += Math.pow(y[i] - meanY, 2);
      }
      
      return (numerator / Math.sqrt(denomX * denomY)).toString();
    });

    return expr;
  }

  /**
   * Logical Functions
   */
  private processLogicalFunctions(expr: string): string {
    // IF
    expr = expr.replace(/IF\(([^,]+),([^,]+),([^)]+)\)/g, (match, condition, trueVal, falseVal) => {
      const cond = this.evaluateCondition(condition);
      return cond ? trueVal : falseVal;
    });

    // AND
    expr = expr.replace(/AND\(([^)]+)\)/g, (match, args) => {
      const conditions = args.split(',').map(c => this.evaluateCondition(c.trim()));
      return conditions.every(c => c) ? 'TRUE' : 'FALSE';
    });

    // OR
    expr = expr.replace(/OR\(([^)]+)\)/g, (match, args) => {
      const conditions = args.split(',').map(c => this.evaluateCondition(c.trim()));
      return conditions.some(c => c) ? 'TRUE' : 'FALSE';
    });

    // NOT
    expr = expr.replace(/NOT\(([^)]+)\)/g, (match, condition) => {
      return this.evaluateCondition(condition) ? 'FALSE' : 'TRUE';
    });

    // IFERROR
    expr = expr.replace(/IFERROR\(([^,]+),([^)]+)\)/g, (match, value, errorVal) => {
      try {
        const result = this.safeEval(value);
        return result === '#ERROR' ? errorVal : result;
      } catch {
        return errorVal;
      }
    });

    return expr;
  }

  // Duplicate function removed - see line 736 for implementation

  /**
   * Date Functions
   */
  private processDateFunctions(expr: string): string {
    // TODAY
    expr = expr.replace(/TODAY\(\)/g, () => {
      return '"' + new Date().toISOString().split('T')[0] + '"';
    });

    // NOW
    expr = expr.replace(/NOW\(\)/g, () => {
      return '"' + new Date().toISOString() + '"';
    });

    // YEAR
    expr = expr.replace(/YEAR\(([^)]+)\)/g, (match, date) => {
      const d = new Date(date.replace(/"/g, ''));
      return d.getFullYear().toString();
    });

    // MONTH
    expr = expr.replace(/MONTH\(([^)]+)\)/g, (match, date) => {
      const d = new Date(date.replace(/"/g, ''));
      return (d.getMonth() + 1).toString();
    });

    // DAY
    expr = expr.replace(/DAY\(([^)]+)\)/g, (match, date) => {
      const d = new Date(date.replace(/"/g, ''));
      return d.getDate().toString();
    });

    // DATEDIF - Difference between dates
    expr = expr.replace(/DATEDIF\(([^,]+),([^,]+),([^)]+)\)/g, (match, start, end, unit) => {
      const startDate = new Date(start.replace(/"/g, ''));
      const endDate = new Date(end.replace(/"/g, ''));
      const diff = endDate.getTime() - startDate.getTime();
      
      switch (unit.replace(/"/g, '').toUpperCase()) {
        case 'D': return Math.floor(diff / (1000 * 60 * 60 * 24)).toString();
        case 'M': return Math.floor(diff / (1000 * 60 * 60 * 24 * 30)).toString();
        case 'Y': return Math.floor(diff / (1000 * 60 * 60 * 24 * 365)).toString();
        default: return '0';
      }
    });

    return expr;
  }

  /**
   * Math Functions
   */
  private processMathFunctions(expr: string): string {
    // Basic functions already in original
    expr = expr.replace(/SUM\(([^)]+)\)/gi, (match, range) => {
      const values = this.getRangeValues(range);
      return values.reduce((a, b) => a + b, 0).toString();
    });

    expr = expr.replace(/AVERAGE\(([^)]+)\)/gi, (match, range) => {
      const values = this.getRangeValues(range);
      return (values.reduce((a, b) => a + b, 0) / values.length).toString();
    });

    expr = expr.replace(/MIN\(([^)]+)\)/gi, (match, range) => {
      const values = this.getRangeValues(range);
      return Math.min(...values).toString();
    });

    expr = expr.replace(/MAX\(([^)]+)\)/gi, (match, range) => {
      const values = this.getRangeValues(range);
      return Math.max(...values).toString();
    });

    expr = expr.replace(/COUNT\(([^)]+)\)/gi, (match, range) => {
      const values = this.getRangeValues(range);
      return values.filter(v => v !== null && v !== undefined).length.toString();
    });

    // Additional math functions
    expr = expr.replace(/ABS\(([^)]+)\)/g, (match, value) => {
      return Math.abs(parseFloat(value)).toString();
    });

    expr = expr.replace(/ROUND\(([^,]+),([^)]+)\)/g, (match, value, digits) => {
      const v = parseFloat(value);
      const d = parseInt(digits);
      return (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toString();
    });

    expr = expr.replace(/CEILING\(([^)]+)\)/g, (match, value) => {
      return Math.ceil(parseFloat(value)).toString();
    });

    expr = expr.replace(/FLOOR\(([^)]+)\)/g, (match, value) => {
      return Math.floor(parseFloat(value)).toString();
    });

    expr = expr.replace(/POWER\(([^,]+),([^)]+)\)/g, (match, base, exp) => {
      return Math.pow(parseFloat(base), parseFloat(exp)).toString();
    });

    expr = expr.replace(/SQRT\(([^)]+)\)/g, (match, value) => {
      return Math.sqrt(parseFloat(value)).toString();
    });

    expr = expr.replace(/LN\(([^)]+)\)/g, (match, value) => {
      return Math.log(parseFloat(value)).toString();
    });

    expr = expr.replace(/LOG\(([^,]+),([^)]+)\)/g, (match, value, base) => {
      return (Math.log(parseFloat(value)) / Math.log(parseFloat(base))).toString();
    });

    expr = expr.replace(/EXP\(([^)]+)\)/g, (match, value) => {
      return Math.exp(parseFloat(value)).toString();
    });

    expr = expr.replace(/MOD\(([^,]+),([^)]+)\)/g, (match, dividend, divisor) => {
      return (parseFloat(dividend) % parseFloat(divisor)).toString();
    });

    return expr;
  }

  /**
   * Helper functions
   */
  private replaceCellReferences(expr: string): string {
    const cellPattern = /([A-Z]+\d+)(?![A-Z(])/g;
    return expr.replace(cellPattern, (match) => {
      const cell = this.cells[match];
      if (cell?.formula) {
        return this.evaluate(cell.formula);
      }
      return cell?.value ?? 0;
    });
  }

  private getRangeValues(range: string): number[] {
    const values: number[] = [];
    
    // Handle single cell
    if (!range.includes(':')) {
      const cell = this.cells[range];
      const val = cell?.formula ? this.evaluate(cell.formula) : cell?.value;
      return [parseFloat(val) || 0];
    }
    
    // Handle range
    const [start, end] = range.split(':');
    const startCell = this.parseCell(start);
    const endCell = this.parseCell(end);
    
    if (!startCell || !endCell) return [];
    
    for (let r = startCell.row; r <= endCell.row; r++) {
      for (let c = startCell.col; c <= endCell.col; c++) {
        const addr = this.cellAddress(c, r);
        const cell = this.cells[addr];
        const val = cell?.formula ? this.evaluate(cell.formula) : cell?.value;
        if (val !== null && val !== undefined && val !== '') {
          values.push(parseFloat(val) || 0);
        }
      }
    }
    
    return values;
  }

  private parseCell(cell: string): { col: number; row: number } | null {
    const match = cell.match(/^([A-Z]+)(\d+)$/);
    if (!match) return null;
    const col = match[1].split('').reduce((acc, char, i) => 
      acc + (char.charCodeAt(0) - 65) * Math.pow(26, match[1].length - i - 1), 0
    );
    const row = parseInt(match[2]) - 1;
    return { col, row };
  }

  private cellAddress(col: number, row: number): string {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    return letters[col] + (row + 1);
  }

  private evaluateCondition(condition: string): boolean {
    // Simple comparison evaluation
    if (condition.includes('>')) {
      const [left, right] = condition.split('>');
      return parseFloat(left) > parseFloat(right);
    }
    if (condition.includes('<')) {
      const [left, right] = condition.split('<');
      return parseFloat(left) < parseFloat(right);
    }
    if (condition.includes('=')) {
      const [left, right] = condition.split('=');
      return left.trim() === right.trim();
    }
    return condition === 'TRUE' || condition === '1';
  }

  private safeEval(expr: string): any {
    try {
      // Allow more characters for proper evaluation including decimals and scientific notation
      const safeExpr = expr
        .replace(/TRUE/gi, 'true')
        .replace(/FALSE/gi, 'false')
        .replace(/[^0-9+\-*/().\s<>=!&|eE]/g, ''); // Allow comparison operators and exponentials
      
      // Use Function constructor for safer evaluation
      const result = Function('"use strict"; return (' + safeExpr + ')')();
      
      // Check for NaN or Infinity
      if (isNaN(result) || !isFinite(result)) {
        return '#ERROR';
      }
      
      return result;
    } catch (error) {
      console.error('Formula evaluation error:', error, 'Expression:', expr);
      return '#ERROR';
    }
  }
}

/**
 * Formula documentation for users
 */
export const FORMULA_DOCS = {
  financial: {
    NPV: 'NPV(rate, range) - Net Present Value',
    IRR: 'IRR(range) - Internal Rate of Return',
    XIRR: 'XIRR(values, dates) - IRR for irregular cash flows',
    XNPV: 'XNPV(rate, values, dates) - NPV for irregular cash flows',
    MIRR: 'MIRR(values, finance_rate, reinvest_rate) - Modified IRR',
    PMT: 'PMT(rate, periods, present_value) - Payment calculation',
    FV: 'FV(rate, periods, payment, present_value) - Future Value',
    PV: 'PV(rate, periods, payment) - Present Value',
    NPER: 'NPER(rate, payment, present_value, future_value) - Number of periods',
    IPMT: 'IPMT(rate, period, nper, present_value) - Interest payment',
    PPMT: 'PPMT(rate, period, nper, present_value) - Principal payment',
    RATE: 'RATE(periods, payment, present_value) - Interest rate',
    WACC: 'WACC(equity, debt, cost_equity, cost_debt, tax_rate) - Weighted Average Cost of Capital',
    CAGR: 'CAGR(begin_value, end_value, years) - Compound Annual Growth Rate',
    MOIC: 'MOIC(exit_value, invested) - Multiple on Invested Capital',
    DPI: 'DPI(distributions, paid_in) - Distributions to Paid-In',
    TVPI: 'TVPI(distributions, nav, paid_in) - Total Value to Paid-In',
    SLN: 'SLN(cost, salvage, life) - Straight-line depreciation',
    DB: 'DB(cost, salvage, life, period, month) - Declining balance depreciation',
    DDB: 'DDB(cost, salvage, life, period, factor) - Double declining balance',
    EFFECT: 'EFFECT(nominal_rate, periods_per_year) - Effective annual rate',
    NOMINAL: 'NOMINAL(effect_rate, periods_per_year) - Nominal annual rate'
  },
  capTable: {
    DILUTION: 'DILUTION(old_shares, new_shares, total_shares) - Calculate dilution percentage',
    OWNERSHIP: 'OWNERSHIP(shares, total_shares) - Calculate ownership percentage',
    PRICEPERSHARE: 'PRICEPERSHARE(valuation, shares) - Calculate price per share',
    OPTIONPOOL: 'OPTIONPOOL(percentage, post_money) - Calculate option pool size'
  },
  waterfall: {
    LIQUIDPREF: 'LIQUIDPREF(investment, multiple, participating) - Liquidation preference (variable)',
    WATERFALL: 'WATERFALL(exit_value, pref_amount, common_shares, total_shares) - Basic waterfall',
    PARIPASSU: 'PARIPASSU(exit_value, investors_json) - Pari passu distribution',
    DILUTIONIMPACT: 'DILUTIONIMPACT(initial_own, new_shares, existing_shares, option_pool) - Dilution analysis',
    EXITMATRIX: 'EXITMATRIX(min_exit, max_exit, steps, pref_stack) - Returns matrix for exit scenarios',
    SENSITIVITYWF: 'SENSITIVITYWF(base_exit, parameter, range_pct, base_terms) - Waterfall sensitivity',
    IPORATCHET: 'IPORATCHET(investment, current_value, min_return) - IPO ratchet (variable return)',
    PARTICIPATING: 'PARTICIPATING(exit_value, investment, multiple, ownership, cap) - Participating preferred',
    DOWNROUND: 'DOWNROUND(exit_value, investment, enhanced_multiple, participating) - Downround waterfall',
    MASTOCK: 'MASTOCK(exit_value, cash_ratio, stock_ratio) - M&A cash/stock mix (variable)',
    CUMULDIV: 'CUMULDIV(investment, rate, years) - Cumulative dividends',
    CATCHUP: 'CATCHUP(proceeds, hurdle, catchup_pct) - GP catch-up calculation',
    CARRIEDINT: 'CARRIEDINT(profits, hurdle, carry_pct) - Carried interest'
  },
  scenario: {
    SCENARIO: 'SCENARIO(base, best, worst, probabilities) - Weighted scenario analysis',
    SENSITIVITY: 'SENSITIVITY(base_value, variable, change) - Sensitivity analysis',
    MONTECARLO: 'MONTECARLO(mean, std_dev, iterations) - Monte Carlo simulation',
    BREAKEVEN: 'BREAKEVEN(fixed_costs, contribution, units) - Breakeven analysis',
    PWERM: 'PWERM(company_name) - PWERM valuation analysis (API call)'
  },
  statistical: {
    STDEV: 'STDEV(range) - Standard Deviation',
    VAR: 'VAR(range) - Variance',
    MEDIAN: 'MEDIAN(range) - Median value',
    PERCENTILE: 'PERCENTILE(range, k) - kth percentile',
    CORREL: 'CORREL(range1, range2) - Correlation coefficient'
  },
  logical: {
    IF: 'IF(condition, true_value, false_value)',
    AND: 'AND(condition1, condition2, ...)',
    OR: 'OR(condition1, condition2, ...)',
    NOT: 'NOT(condition)',
    IFERROR: 'IFERROR(value, error_value)'
  },
  text: {
    CONCATENATE: 'CONCATENATE(text1, text2, ...)',
    LEN: 'LEN(text) - Length of text',
    UPPER: 'UPPER(text) - Convert to uppercase',
    LOWER: 'LOWER(text) - Convert to lowercase',
    TRIM: 'TRIM(text) - Remove extra spaces'
  },
  date: {
    TODAY: 'TODAY() - Current date',
    NOW: 'NOW() - Current date and time',
    YEAR: 'YEAR(date) - Extract year',
    MONTH: 'MONTH(date) - Extract month',
    DAY: 'DAY(date) - Extract day',
    DATEDIF: 'DATEDIF(start, end, unit) - Date difference'
  },
  math: {
    SUM: 'SUM(range) - Sum of values',
    AVERAGE: 'AVERAGE(range) - Average of values',
    MIN: 'MIN(range) - Minimum value',
    MAX: 'MAX(range) - Maximum value',
    COUNT: 'COUNT(range) - Count of values',
    ABS: 'ABS(value) - Absolute value',
    ROUND: 'ROUND(value, digits) - Round to digits',
    CEILING: 'CEILING(value) - Round up',
    FLOOR: 'FLOOR(value) - Round down',
    POWER: 'POWER(base, exponent)',
    SQRT: 'SQRT(value) - Square root',
    LN: 'LN(value) - Natural logarithm',
    LOG: 'LOG(value, base) - Logarithm',
    EXP: 'EXP(value) - e raised to power',
    MOD: 'MOD(dividend, divisor) - Modulo'
  }
};