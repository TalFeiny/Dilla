/**
 * Model Learning System
 * Tracks agent performance and builds fine-tuning dataset
 */

import { supabaseService } from '@/lib/supabase';

export interface ModelSession {
  id: string;
  company: string;
  prompt: string;
  data_retrieved: Record<string, any>;
  initial_model: string[];  // Grid commands
  user_corrections: string[];
  final_model: string[];
  accuracy_score: number;  // 0-100
  created_at: Date;
}

export class ModelLearningSystem {
  private currentSession: Partial<ModelSession> | null = null;

  // Start tracking a new model building session
  async startSession(prompt: string, company?: string) {
    this.currentSession = {
      id: crypto.randomUUID(),
      company: company || 'unknown',
      prompt,
      data_retrieved: {},
      initial_model: [],
      user_corrections: [],
      created_at: new Date()
    };
    
    return this.currentSession.id;
  }

  // Record data retrieved from sources
  async recordDataRetrieval(source: string, data: any) {
    if (!this.currentSession) return;
    
    this.currentSession.data_retrieved = {
      ...this.currentSession.data_retrieved,
      [source]: data
    };
  }

  // Record the initial model generated
  async recordInitialModel(commands: string[]) {
    if (!this.currentSession) return;
    this.currentSession.initial_model = commands;
  }

  // Record user corrections
  async recordCorrection(correction: string) {
    if (!this.currentSession) return;
    this.currentSession.user_corrections?.push(correction);
  }

  // Calculate accuracy based on corrections needed
  calculateAccuracy(): number {
    if (!this.currentSession) return 0;
    
    const initial = this.currentSession.initial_model?.length || 0;
    const corrections = this.currentSession.user_corrections?.length || 0;
    
    if (initial === 0) return 0;
    
    // Fewer corrections = higher accuracy
    const accuracy = Math.max(0, 100 - (corrections / initial) * 100);
    return Math.round(accuracy);
  }

  // Save session to database for fine-tuning
  async saveSession() {
    if (!this.currentSession) return;
    
    this.currentSession.accuracy_score = this.calculateAccuracy();
    
    // Save to Supabase for later fine-tuning
    if (!supabaseService) return;
    const { error } = await supabaseService
      .from('model_learning_sessions')
      .insert(this.currentSession);
    
    if (error) {
      console.error('Failed to save learning session:', error);
    }
    
    // Generate fine-tuning example if accuracy is high
    if (this.currentSession.accuracy_score > 80) {
      await this.generateFineTuningExample();
    }
    
    this.currentSession = null;
  }

  // Generate fine-tuning data from good sessions
  async generateFineTuningExample() {
    if (!this.currentSession || !supabaseService) return;
    
    const example = {
      messages: [
        {
          role: "system",
          content: "You are a financial modeling expert. Build models using real data and standard valuation methods."
        },
        {
          role: "user",
          content: this.currentSession.prompt
        },
        {
          role: "assistant",
          content: this.currentSession.final_model?.join('\n') || this.currentSession.initial_model?.join('\n')
        }
      ]
    };
    
    // Save to fine-tuning dataset
    await supabaseService
      .from('fine_tuning_examples')
      .insert({
        example,
        accuracy: this.currentSession.accuracy_score,
        company: this.currentSession.company,
        created_at: new Date()
      });
  }

  // Get insights on common mistakes
  async getCommonMistakes(): Promise<any> {
    if (!supabaseService) return {};
    const { data } = await supabaseService
      .from('model_learning_sessions')
      .select('user_corrections')
      .order('created_at', { ascending: false })
      .limit(100);
    
    // Analyze patterns in corrections
    const mistakes: Record<string, number> = {};
    
    data?.forEach(session => {
      session.user_corrections?.forEach((correction: string) => {
        // Extract type of mistake (e.g., "wrong growth rate", "missing discount")
        if (correction.includes('growth')) mistakes['growth_rate'] = (mistakes['growth_rate'] || 0) + 1;
        if (correction.includes('discount')) mistakes['discount_rate'] = (mistakes['discount_rate'] || 0) + 1;
        if (correction.includes('multiple')) mistakes['valuation_multiple'] = (mistakes['valuation_multiple'] || 0) + 1;
      });
    });
    
    return mistakes;
  }

  // Get best performing model templates
  async getBestTemplates(modelType: string): Promise<any> {
    if (!supabaseService) return [];
    const { data } = await supabaseService
      .from('model_learning_sessions')
      .select('*')
      .ilike('prompt', `%${modelType}%`)
      .gte('accuracy_score', 90)
      .order('accuracy_score', { ascending: false })
      .limit(5);
    
    return data?.map(session => ({
      prompt: session.prompt,
      model: session.final_model || session.initial_model,
      accuracy: session.accuracy_score
    }));
  }
}

// Singleton instance
export const modelLearning = new ModelLearningSystem();