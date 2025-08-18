/**
 * Model Consistency Guard
 * Prevents agent hallucination and ensures model consistency
 * Fast deduplication and conflict detection
 */

import { createHash } from 'crypto';

export interface Model {
  id: string;
  type: string;
  company: string;
  version: number;
  created: Date;
  modified: Date;
  checksum: string;
  data: any;
  metadata: {
    source: string;
    confidence: number;
    validated: boolean;
  };
}

export interface ModelConflict {
  existing: Model;
  proposed: Model;
  conflicts: string[];
  resolution: 'keep_existing' | 'update' | 'version' | 'merge';
}

export class ModelConsistencyGuard {
  private static instance: ModelConsistencyGuard;
  private models: Map<string, Model> = new Map();
  private checksums: Map<string, string> = new Map();
  private companyModels: Map<string, Set<string>> = new Map();
  private modelHistory: Map<string, Model[]> = new Map();

  private constructor() {
    this.loadFromStorage();
  }

  static getInstance(): ModelConsistencyGuard {
    if (!ModelConsistencyGuard.instance) {
      ModelConsistencyGuard.instance = new ModelConsistencyGuard();
    }
    return ModelConsistencyGuard.instance;
  }

  /**
   * Check if a model already exists (fast lookup)
   */
  hasModel(company: string, type: string): boolean {
    const key = this.getModelKey(company, type);
    return this.models.has(key);
  }

  /**
   * Get existing model (fast retrieval)
   */
  getModel(company: string, type: string): Model | null {
    const key = this.getModelKey(company, type);
    return this.models.get(key) || null;
  }

  /**
   * Validate and register a new model
   */
  async registerModel(
    company: string,
    type: string,
    data: any,
    source: string = 'agent'
  ): Promise<{ success: boolean; model?: Model; conflict?: ModelConflict }> {
    const key = this.getModelKey(company, type);
    const checksum = this.calculateChecksum(data);
    
    // Check for existing model
    const existing = this.models.get(key);
    
    if (existing) {
      // Check if it's the same content (fast checksum comparison)
      if (existing.checksum === checksum) {
        return { 
          success: true, 
          model: existing 
        };
      }
      
      // Detect conflicts
      const conflicts = this.detectConflicts(existing.data, data);
      
      if (conflicts.length > 0) {
        const conflict: ModelConflict = {
          existing,
          proposed: this.createModel(company, type, data, source),
          conflicts,
          resolution: this.suggestResolution(conflicts, existing, data)
        };
        
        return { 
          success: false, 
          conflict 
        };
      }
      
      // No conflicts, update the model
      return this.updateModel(existing, data, source);
    }
    
    // Create new model
    const model = this.createModel(company, type, data, source);
    this.storeModel(model);
    
    return { 
      success: true, 
      model 
    };
  }

  /**
   * Detect conflicts between models
   */
  private detectConflicts(existing: any, proposed: any): string[] {
    const conflicts: string[] = [];
    
    // Check for conflicting values
    for (const key in proposed) {
      if (key in existing) {
        const existingVal = existing[key];
        const proposedVal = proposed[key];
        
        if (this.isSignificantDifference(existingVal, proposedVal, key)) {
          conflicts.push(`${key}: ${existingVal} vs ${proposedVal}`);
        }
      }
    }
    
    return conflicts;
  }

  /**
   * Check if difference is significant
   */
  private isSignificantDifference(val1: any, val2: any, key: string): boolean {
    // Ignore metadata fields
    if (['updated', 'modified', 'timestamp', 'version'].includes(key)) {
      return false;
    }
    
    // Numbers: check if difference > 10%
    if (typeof val1 === 'number' && typeof val2 === 'number') {
      const diff = Math.abs(val1 - val2);
      const avg = (val1 + val2) / 2;
      return avg > 0 && (diff / avg) > 0.1;
    }
    
    // Arrays: check length and content
    if (Array.isArray(val1) && Array.isArray(val2)) {
      if (val1.length !== val2.length) return true;
      return !val1.every((v, i) => this.isEqual(v, val2[i]));
    }
    
    // Objects: recursive check
    if (typeof val1 === 'object' && typeof val2 === 'object') {
      return JSON.stringify(val1) !== JSON.stringify(val2);
    }
    
    // Direct comparison
    return val1 !== val2;
  }

  /**
   * Suggest conflict resolution
   */
  private suggestResolution(
    conflicts: string[],
    existing: Model,
    proposedData: any
  ): 'keep_existing' | 'update' | 'version' | 'merge' {
    // If existing model is validated, keep it
    if (existing.metadata.validated) {
      return 'keep_existing';
    }
    
    // If many conflicts, create new version
    if (conflicts.length > 5) {
      return 'version';
    }
    
    // If minor conflicts, merge
    if (conflicts.length <= 2) {
      return 'merge';
    }
    
    // Default to update
    return 'update';
  }

  /**
   * Update existing model
   */
  private updateModel(
    existing: Model,
    newData: any,
    source: string
  ): { success: boolean; model: Model } {
    // Store history
    this.addToHistory(existing);
    
    // Update model
    existing.data = newData;
    existing.modified = new Date();
    existing.version++;
    existing.checksum = this.calculateChecksum(newData);
    existing.metadata.source = source;
    
    // Re-store
    this.storeModel(existing);
    
    return { 
      success: true, 
      model: existing 
    };
  }

  /**
   * Merge two models intelligently
   */
  mergeModels(existing: Model, proposed: any): Model {
    const merged = { ...existing.data };
    
    for (const key in proposed) {
      if (!(key in merged) || this.shouldUseProposed(key, merged[key], proposed[key])) {
        merged[key] = proposed[key];
      }
    }
    
    existing.data = merged;
    existing.modified = new Date();
    existing.version++;
    existing.checksum = this.calculateChecksum(merged);
    
    return existing;
  }

  /**
   * Decide if proposed value should be used
   */
  private shouldUseProposed(key: string, existing: any, proposed: any): boolean {
    // Use proposed if existing is null/undefined
    if (existing == null) return true;
    
    // Use proposed if it has more detail
    if (typeof proposed === 'object' && typeof existing === 'object') {
      return Object.keys(proposed).length > Object.keys(existing).length;
    }
    
    // Use proposed if it's a larger number (assuming more recent)
    if (typeof proposed === 'number' && typeof existing === 'number') {
      return proposed > existing;
    }
    
    // Keep existing by default
    return false;
  }

  /**
   * Create a new model
   */
  private createModel(company: string, type: string, data: any, source: string): Model {
    const id = this.generateId(company, type);
    const checksum = this.calculateChecksum(data);
    
    return {
      id,
      type,
      company,
      version: 1,
      created: new Date(),
      modified: new Date(),
      checksum,
      data,
      metadata: {
        source,
        confidence: 0.8,
        validated: false
      }
    };
  }

  /**
   * Store model in memory
   */
  private storeModel(model: Model) {
    const key = this.getModelKey(model.company, model.type);
    
    // Store in main map
    this.models.set(key, model);
    
    // Store checksum for fast lookup
    this.checksums.set(model.checksum, key);
    
    // Track by company
    if (!this.companyModels.has(model.company)) {
      this.companyModels.set(model.company, new Set());
    }
    this.companyModels.get(model.company)!.add(key);
    
    // Persist to storage
    this.saveToStorage();
  }

  /**
   * Add model to history
   */
  private addToHistory(model: Model) {
    const key = this.getModelKey(model.company, model.type);
    
    if (!this.modelHistory.has(key)) {
      this.modelHistory.set(key, []);
    }
    
    const history = this.modelHistory.get(key)!;
    history.push({ ...model }); // Deep copy
    
    // Keep only last 10 versions
    if (history.length > 10) {
      history.shift();
    }
  }

  /**
   * Get all models for a company
   */
  getCompanyModels(company: string): Model[] {
    const modelKeys = this.companyModels.get(company);
    if (!modelKeys) return [];
    
    return Array.from(modelKeys)
      .map(key => this.models.get(key))
      .filter(Boolean) as Model[];
  }

  /**
   * Validate model data
   */
  validateModel(model: Model): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    
    // Check required fields based on type
    switch (model.type) {
      case 'pwerm':
        if (!model.data.scenarios || !Array.isArray(model.data.scenarios)) {
          errors.push('PWERM model must have scenarios array');
        }
        if (!model.data.expected_value) {
          errors.push('PWERM model must have expected value');
        }
        break;
        
      case 'waterfall':
        if (!model.data.preferences || !Array.isArray(model.data.preferences)) {
          errors.push('Waterfall model must have preferences array');
        }
        break;
        
      case 'dcf':
        if (!model.data.cash_flows || !Array.isArray(model.data.cash_flows)) {
          errors.push('DCF model must have cash flows');
        }
        if (!model.data.discount_rate) {
          errors.push('DCF model must have discount rate');
        }
        break;
    }
    
    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Clean up old/invalid models
   */
  cleanup() {
    const now = Date.now();
    const maxAge = 30 * 24 * 60 * 60 * 1000; // 30 days
    
    for (const [key, model] of this.models) {
      // Remove old, unvalidated models
      if (!model.metadata.validated && 
          now - model.modified.getTime() > maxAge) {
        this.models.delete(key);
        this.checksums.delete(model.checksum);
        
        const companySet = this.companyModels.get(model.company);
        if (companySet) {
          companySet.delete(key);
        }
      }
    }
    
    this.saveToStorage();
  }

  /**
   * Helper methods
   */
  private getModelKey(company: string, type: string): string {
    return `${company.toLowerCase()}_${type.toLowerCase()}`;
  }

  private generateId(company: string, type: string): string {
    return `${this.getModelKey(company, type)}_${Date.now()}`;
  }

  private calculateChecksum(data: any): string {
    const str = JSON.stringify(data, Object.keys(data).sort());
    return createHash('md5').update(str).digest('hex');
  }

  private isEqual(a: any, b: any): boolean {
    return JSON.stringify(a) === JSON.stringify(b);
  }

  /**
   * Storage methods
   */
  private saveToStorage() {
    try {
      if (typeof window !== 'undefined') {
        const data = {
          models: Array.from(this.models.entries()),
          checksums: Array.from(this.checksums.entries()),
          companyModels: Array.from(this.companyModels.entries()).map(([k, v]) => [k, Array.from(v)])
        };
        localStorage.setItem('model_consistency_guard', JSON.stringify(data));
      }
    } catch (error) {
      console.error('Failed to save model consistency data:', error);
    }
  }

  private loadFromStorage() {
    try {
      if (typeof window !== 'undefined') {
        const stored = localStorage.getItem('model_consistency_guard');
        if (stored) {
          const data = JSON.parse(stored);
          
          this.models = new Map(data.models.map(([k, v]: [string, any]) => [
            k,
            { ...v, created: new Date(v.created), modified: new Date(v.modified) }
          ]));
          
          this.checksums = new Map(data.checksums);
          this.companyModels = new Map(data.companyModels.map(([k, v]: [string, string[]]) => [k, new Set(v)]));
        }
      }
    } catch (error) {
      console.error('Failed to load model consistency data:', error);
    }
  }

  /**
   * Export for debugging
   */
  exportState() {
    return {
      totalModels: this.models.size,
      companies: this.companyModels.size,
      checksums: this.checksums.size,
      models: Array.from(this.models.values()).map(m => ({
        company: m.company,
        type: m.type,
        version: m.version,
        validated: m.metadata.validated
      }))
    };
  }
}

// Export singleton
export const modelConsistencyGuard = ModelConsistencyGuard.getInstance();

// React hook for model consistency
export function useModelConsistency(company: string, type: string) {
  const [hasModel, setHasModel] = React.useState(false);
  const [model, setModel] = React.useState<Model | null>(null);
  
  React.useEffect(() => {
    const existing = modelConsistencyGuard.getModel(company, type);
    setHasModel(!!existing);
    setModel(existing);
  }, [company, type]);
  
  const registerModel = async (data: any) => {
    const result = await modelConsistencyGuard.registerModel(company, type, data);
    if (result.success && result.model) {
      setModel(result.model);
      setHasModel(true);
    }
    return result;
  };
  
  return { hasModel, model, registerModel };
}