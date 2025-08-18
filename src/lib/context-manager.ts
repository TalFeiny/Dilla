// Context Manager - Handles conversation state and output overrides

export interface ConversationContext {
  currentOutput: any;
  history: Array<{
    query: string;
    output: any;
    timestamp: Date;
    overridden: boolean;
  }>;
  entities: Map<string, any>;
  lastMentioned: {
    company?: string;
    companies?: string[];
    metric?: string;
    metrics?: string[];
    timeframe?: string;
    operation?: string;
  };
  state: 'initial' | 'showing_results' | 'comparing' | 'analyzing';
}

export type UserIntent = 
  | 'override'    // "No, actually..."
  | 'extend'      // "Also show..."
  | 'refine'      // "Only the..."
  | 'drill_down'  // "Show more details"
  | 'pivot'       // "What about..."
  | 'compare'     // "Compare to..."
  | 'undo'        // "Go back"
  | 'new';        // Fresh query

export class ContextManager {
  private context: ConversationContext;
  
  constructor() {
    this.context = {
      currentOutput: null,
      history: [],
      entities: new Map(),
      lastMentioned: {},
      state: 'initial'
    };
  }
  
  // Analyze user intent based on query patterns
  analyzeIntent(query: string): UserIntent {
    const lowerQuery = query.toLowerCase();
    
    // Override patterns - user wants to replace current output
    if (/^(no|not|actually|instead|forget that|scratch that|wait)/i.test(query)) {
      return 'override';
    }
    
    // Extension patterns - user wants to add to current output
    if (/^(also|and|plus|add|include|as well)/i.test(query)) {
      return 'extend';
    }
    
    // Refinement patterns - user wants to modify current output
    if (/^(but|except|only|just|specifically|filter)/i.test(query)) {
      return 'refine';
    }
    
    // Drill down patterns - user wants more detail
    if (/(show me more|details|break.*down|elaborate|expand)/i.test(query)) {
      return 'drill_down';
    }
    
    // Pivot patterns - user wants related but different info
    if (/^(what about|how about|now show|switch to)/i.test(query)) {
      return 'pivot';
    }
    
    // Comparison patterns
    if (/(compare|versus|vs|how does.*compare|side.?by.?side)/i.test(query)) {
      return 'compare';
    }
    
    // Undo patterns
    if (/^(go back|previous|undo|revert)/i.test(query)) {
      return 'undo';
    }
    
    // Check for pronouns that reference context
    if (/\b(it|this|that|these|those|them|the same)\b/i.test(query) && this.context.currentOutput) {
      // If referencing something, it's likely a refinement or extension
      return lowerQuery.includes('compare') ? 'compare' : 'refine';
    }
    
    return 'new';
  }
  
  // Resolve pronouns and references in the query
  resolveReferences(query: string): string {
    let resolved = query;
    const last = this.context.lastMentioned;
    
    // Resolve "it" -> last company
    if (/\bit\b/i.test(query) && last.company) {
      resolved = resolved.replace(/\bit\b/gi, last.company);
    }
    
    // Resolve "them" / "they" -> last companies
    if (/\b(them|they)\b/i.test(query) && last.companies && last.companies.length > 1) {
      const companiesStr = last.companies.join(' and ');
      resolved = resolved.replace(/\bthem\b/gi, companiesStr);
      resolved = resolved.replace(/\bthey\b/gi, companiesStr);
    }
    
    // Resolve "that" in context
    if (/\bthat\b/i.test(query)) {
      if (last.metric && /that metric/i.test(query)) {
        resolved = resolved.replace(/\bthat metric\b/gi, last.metric);
      } else if (last.company && /that company/i.test(query)) {
        resolved = resolved.replace(/\bthat company\b/gi, last.company);
      }
    }
    
    // Resolve "the same" -> previous operation/metrics
    if (/\bthe same\b/i.test(query)) {
      if (last.metrics && last.metrics.length > 0) {
        const metricsStr = last.metrics.join(', ');
        resolved = resolved.replace(/\bthe same\b/gi, metricsStr);
      } else if (last.operation) {
        resolved = resolved.replace(/\bthe same\b/gi, last.operation);
      }
    }
    
    // Resolve "this" -> current output reference
    if (/\bthis\b/i.test(query) && this.context.currentOutput) {
      // Context-aware replacement based on what's shown
      if (this.context.state === 'comparing') {
        resolved = resolved.replace(/\bthis comparison\b/gi, 'the current comparison');
      } else if (this.context.state === 'analyzing') {
        resolved = resolved.replace(/\bthis analysis\b/gi, 'the current analysis');
      }
    }
    
    return resolved;
  }
  
  // Process query with context awareness
  async processQuery(query: string, executeFunction: (q: string, ctx: any) => Promise<any>) {
    // Step 1: Analyze intent
    const intent = this.analyzeIntent(query);
    
    // Step 2: Resolve references
    const resolvedQuery = this.resolveReferences(query);
    
    // Step 3: Prepare execution context
    const executionContext = this.prepareExecutionContext(intent, resolvedQuery);
    
    // Step 4: Execute based on intent
    let result;
    
    switch (intent) {
      case 'override':
        result = await this.handleOverride(resolvedQuery, executeFunction);
        break;
        
      case 'extend':
        result = await this.handleExtension(resolvedQuery, executeFunction);
        break;
        
      case 'refine':
        result = await this.handleRefinement(resolvedQuery, executeFunction);
        break;
        
      case 'drill_down':
        result = await this.handleDrillDown(resolvedQuery, executeFunction);
        break;
        
      case 'pivot':
        result = await this.handlePivot(resolvedQuery, executeFunction);
        break;
        
      case 'compare':
        result = await this.handleComparison(resolvedQuery, executeFunction);
        break;
        
      case 'undo':
        result = this.handleUndo();
        break;
        
      default:
        result = await this.handleNewQuery(resolvedQuery, executeFunction);
    }
    
    // Step 5: Update context
    this.updateContext(resolvedQuery, result, intent);
    
    return {
      intent,
      originalQuery: query,
      resolvedQuery,
      result,
      context: this.getContext()
    };
  }
  
  private async handleOverride(query: string, execute: Function) {
    // Mark current output as overridden
    if (this.context.currentOutput) {
      this.context.history.push({
        ...this.context.currentOutput,
        overridden: true,
        timestamp: new Date()
      });
    }
    
    // Clean the query (remove override indicators)
    const cleanQuery = query.replace(/^(no|not|actually|instead|forget that|scratch that|wait),?\s*/i, '');
    
    // Execute fresh
    return await execute(cleanQuery, { fresh: true });
  }
  
  private async handleExtension(query: string, execute: Function) {
    // Clean the query
    const cleanQuery = query.replace(/^(also|and|plus|add|include|as well),?\s*/i, '');
    
    // Execute with merge context
    const newData = await execute(cleanQuery, { 
      mergeWith: this.context.currentOutput 
    });
    
    // Merge results
    return this.mergeOutputs(this.context.currentOutput, newData);
  }
  
  private async handleRefinement(query: string, execute: Function) {
    // Apply refinement to current output
    const refinementRules = this.extractRefinementRules(query);
    
    return this.applyRefinement(this.context.currentOutput, refinementRules);
  }
  
  private async handleDrillDown(query: string, execute: Function) {
    // Get more details about current focus
    if (!this.context.currentOutput) {
      return await execute(query, {});
    }
    
    return await execute(query, {
      drillDownFrom: this.context.currentOutput,
      expandFields: this.extractFieldsToExpand(query)
    });
  }
  
  private async handlePivot(query: string, execute: Function) {
    // Keep entity context but change the analysis
    const cleanQuery = query.replace(/^(what about|how about|now show|switch to),?\s*/i, '');
    
    return await execute(cleanQuery, {
      entities: Array.from(this.context.entities.keys()),
      pivotFrom: this.context.lastMentioned.operation
    });
  }
  
  private async handleComparison(query: string, execute: Function) {
    // Add comparison to current view
    const comparisonTarget = this.extractComparisonTarget(query);
    
    return await execute(query, {
      compareWith: this.context.currentOutput,
      target: comparisonTarget
    });
  }
  
  private handleUndo() {
    // Restore previous state
    if (this.context.history.length > 0) {
      const previous = this.context.history.pop();
      if (previous && !previous.overridden) {
        this.context.currentOutput = previous.output;
        return previous.output;
      }
    }
    return null;
  }
  
  private async handleNewQuery(query: string, execute: Function) {
    // Fresh query, but keep entity mappings
    return await execute(query, {
      knownEntities: Array.from(this.context.entities.keys())
    });
  }
  
  private prepareExecutionContext(intent: UserIntent, query: string) {
    return {
      intent,
      hasCurrentOutput: !!this.context.currentOutput,
      currentOutputType: this.context.currentOutput?.type,
      knownEntities: Array.from(this.context.entities.keys()),
      lastOperation: this.context.lastMentioned.operation,
      state: this.context.state
    };
  }
  
  private updateContext(query: string, result: any, intent: UserIntent) {
    // Update current output (unless it was an undo)
    if (intent !== 'undo') {
      this.context.currentOutput = {
        query,
        output: result,
        timestamp: new Date(),
        overridden: false
      };
    }
    
    // Extract and update entities
    this.updateEntities(query, result);
    
    // Update last mentioned items
    this.updateLastMentioned(query, result);
    
    // Update state
    this.updateState(intent, result);
  }
  
  private updateEntities(query: string, result: any) {
    // Extract company names from query and results
    const companyPattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g;
    const companies = query.match(companyPattern) || [];
    
    companies.forEach(company => {
      if (!this.context.entities.has(company)) {
        this.context.entities.set(company, {
          firstMentioned: new Date(),
          data: result?.data?.[company]
        });
      }
    });
  }
  
  private updateLastMentioned(query: string, result: any) {
    // Update last mentioned companies
    const companies = this.extractCompanies(query);
    if (companies.length > 0) {
      this.context.lastMentioned.companies = companies;
      this.context.lastMentioned.company = companies[0];
    }
    
    // Update last mentioned metrics
    const metrics = this.extractMetrics(query);
    if (metrics.length > 0) {
      this.context.lastMentioned.metrics = metrics;
      this.context.lastMentioned.metric = metrics[0];
    }
    
    // Update last operation
    if (query.includes('compare')) {
      this.context.lastMentioned.operation = 'comparison';
    } else if (query.includes('analyze')) {
      this.context.lastMentioned.operation = 'analysis';
    }
  }
  
  private updateState(intent: UserIntent, result: any) {
    if (intent === 'compare' || result?.type === 'comparison') {
      this.context.state = 'comparing';
    } else if (intent === 'new' && result?.type === 'analysis') {
      this.context.state = 'analyzing';
    } else if (result?.data) {
      this.context.state = 'showing_results';
    }
  }
  
  private mergeOutputs(current: any, newData: any) {
    // Intelligent merging based on output types
    if (!current) return newData;
    if (!newData) return current;
    
    // If both are arrays, concatenate
    if (Array.isArray(current) && Array.isArray(newData)) {
      return [...current, ...newData];
    }
    
    // If both are objects with data arrays
    if (current.data && newData.data) {
      return {
        ...current,
        data: [...(current.data || []), ...(newData.data || [])],
        merged: true
      };
    }
    
    // Default: side by side
    return {
      type: 'merged',
      left: current,
      right: newData
    };
  }
  
  private extractRefinementRules(query: string) {
    const rules: any = {};
    
    // Extract "only" constraints
    const onlyMatch = query.match(/only\s+(.+?)(?:\s|$)/i);
    if (onlyMatch) {
      rules.filter = onlyMatch[1];
    }
    
    // Extract "except" constraints
    const exceptMatch = query.match(/except\s+(.+?)(?:\s|$)/i);
    if (exceptMatch) {
      rules.exclude = exceptMatch[1];
    }
    
    return rules;
  }
  
  private applyRefinement(output: any, rules: any) {
    if (!output || !rules) return output;
    
    // Apply filters
    if (rules.filter && output.data) {
      output.data = output.data.filter((item: any) => {
        // Simple filter implementation
        return JSON.stringify(item).toLowerCase().includes(rules.filter.toLowerCase());
      });
    }
    
    // Apply exclusions
    if (rules.exclude && output.data) {
      output.data = output.data.filter((item: any) => {
        return !JSON.stringify(item).toLowerCase().includes(rules.exclude.toLowerCase());
      });
    }
    
    return output;
  }
  
  private extractFieldsToExpand(query: string): string[] {
    const fields = [];
    
    if (/revenue|sales/i.test(query)) fields.push('revenue');
    if (/growth/i.test(query)) fields.push('growth_rate');
    if (/valuation/i.test(query)) fields.push('valuation');
    if (/funding/i.test(query)) fields.push('funding');
    
    return fields;
  }
  
  private extractComparisonTarget(query: string): string {
    // Extract what to compare with
    const patterns = [
      /compare (?:to|with) (\w+)/i,
      /versus (\w+)/i,
      /vs\.? (\w+)/i
    ];
    
    for (const pattern of patterns) {
      const match = query.match(pattern);
      if (match) return match[1];
    }
    
    return '';
  }
  
  private extractCompanies(query: string): string[] {
    const companies = [];
    const pattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g;
    const matches = query.match(pattern) || [];
    
    // Filter out common non-company words
    const nonCompanies = ['Show', 'Compare', 'Find', 'Get', 'List', 'What', 'How'];
    
    return matches.filter(m => !nonCompanies.includes(m));
  }
  
  private extractMetrics(query: string): string[] {
    const metrics = [];
    const metricKeywords = [
      'revenue', 'growth', 'valuation', 'funding', 'burn',
      'runway', 'employees', 'margin', 'profit', 'ebitda'
    ];
    
    const lower = query.toLowerCase();
    metricKeywords.forEach(metric => {
      if (lower.includes(metric)) {
        metrics.push(metric);
      }
    });
    
    return metrics;
  }
  
  // Get current context for display
  getContext(): ConversationContext {
    return this.context;
  }
  
  // Clear context
  reset() {
    this.context = {
      currentOutput: null,
      history: [],
      entities: new Map(),
      lastMentioned: {},
      state: 'initial'
    };
  }
}