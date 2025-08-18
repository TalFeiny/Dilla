/**
 * RAG Memory System using Supabase pgvector
 * Stores and retrieves financial model patterns for training
 */

import { createClient } from '@supabase/supabase-js';
import OpenAI from 'openai';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY!
});

export class RAGMemorySystem {
  
  // Generate embedding for text
  async generateEmbedding(text: string): Promise<number[]> {
    const response = await openai.embeddings.create({
      model: 'text-embedding-ada-002',
      input: text,
    });
    
    return response.data[0].embedding;
  }

  // Store a successful model in memory
  async storeModelMemory(params: {
    company: string;
    modelType: 'DCF' | 'PWERM' | 'Comparables' | 'P&L' | 'BalanceSheet';
    prompt: string;
    dataContext: Record<string, any>;
    modelCommands: string[];
    accuracy: number;
  }) {
    // Create searchable text from all components
    const searchableText = `
      Company: ${params.company}
      Model Type: ${params.modelType}
      Prompt: ${params.prompt}
      Data: ${JSON.stringify(params.dataContext)}
      Commands: ${params.modelCommands.join(' ')}
    `;
    
    // Generate embedding
    const embedding = await this.generateEmbedding(searchableText);
    
    // Store in database
    const { data, error } = await supabase
      .from('model_memories')
      .insert({
        company_name: params.company,
        model_type: params.modelType,
        prompt: params.prompt,
        data_context: params.dataContext,
        model_commands: params.modelCommands,
        accuracy_score: params.accuracy,
        embedding,
        searchable_text: searchableText
      });
    
    if (error) {
      console.error('Failed to store model memory:', error);
      throw error;
    }
    
    return data;
  }

  // Retrieve similar models for a new prompt
  async retrieveSimilarModels(prompt: string, limit = 5): Promise<any[]> {
    // Generate embedding for the query
    const embedding = await this.generateEmbedding(prompt);
    
    // Call the similarity search function
    const { data, error } = await supabase
      .rpc('search_similar_models', {
        query_embedding: embedding,
        match_count: limit,
        match_threshold: 0.7
      });
    
    if (error) {
      console.error('Failed to search similar models:', error);
      return [];
    }
    
    return data || [];
  }

  // Get best examples for a specific company
  async getCompanyModels(company: string): Promise<any[]> {
    const { data, error } = await supabase
      .rpc('search_model_patterns', {
        search_company: company,
        limit_count: 10
      });
    
    if (error) {
      console.error('Failed to get company models:', error);
      return [];
    }
    
    return data || [];
  }

  // Build context for the agent from similar models
  async buildRAGContext(prompt: string, company?: string): Promise<string> {
    // Get similar models
    const similarModels = await this.retrieveSimilarModels(prompt, 3);
    
    // Get company-specific models if company is provided
    const companyModels = company ? await this.getCompanyModels(company) : [];
    
    // Build context string
    let context = 'Similar successful models:\n\n';
    
    // Add similar models
    similarModels.forEach((model, i) => {
      context += `Example ${i + 1} (${model.model_type} for ${model.company_name}):\n`;
      context += `Prompt: ${model.prompt}\n`;
      context += `Commands used:\n${model.model_commands.join('\n')}\n`;
      context += `Similarity: ${(model.similarity * 100).toFixed(1)}%\n\n`;
    });
    
    // Add company-specific patterns
    if (companyModels.length > 0) {
      context += `\nPrevious models for ${company}:\n`;
      companyModels.forEach(model => {
        context += `- ${model.model_type}: Accuracy ${model.accuracy_score}%\n`;
        context += `  Data used: ${Object.keys(model.data_context).join(', ')}\n`;
      });
    }
    
    return context;
  }

  // Export training data for fine-tuning
  async exportTrainingData(minAccuracy = 85): Promise<any[]> {
    const { data, error } = await supabase
      .from('fine_tuning_dataset')
      .select('*')
      .gte('accuracy_score', minAccuracy);
    
    if (error) {
      console.error('Failed to export training data:', error);
      return [];
    }
    
    // Format for OpenAI fine-tuning
    return data?.map(row => row.training_example) || [];
  }

  // Analyze model performance patterns
  async analyzeModelPatterns(): Promise<any> {
    // Get all models grouped by type
    const { data: modelStats } = await supabase
      .from('model_memories')
      .select('model_type, accuracy_score');
    
    // Calculate stats by model type
    const stats: Record<string, any> = {};
    
    modelStats?.forEach(model => {
      if (!stats[model.model_type]) {
        stats[model.model_type] = {
          count: 0,
          totalAccuracy: 0,
          accuracies: []
        };
      }
      
      stats[model.model_type].count++;
      stats[model.model_type].totalAccuracy += model.accuracy_score;
      stats[model.model_type].accuracies.push(model.accuracy_score);
    });
    
    // Calculate averages and insights
    Object.keys(stats).forEach(modelType => {
      const s = stats[modelType];
      s.avgAccuracy = s.totalAccuracy / s.count;
      s.minAccuracy = Math.min(...s.accuracies);
      s.maxAccuracy = Math.max(...s.accuracies);
      delete s.accuracies; // Clean up
    });
    
    return stats;
  }

  // Smart model selection based on context
  async selectBestModelTemplate(params: {
    company: string;
    modelType: string;
    hasRevenue: boolean;
    hasFunding: boolean;
  }): Promise<any> {
    // Build a query to find the best matching template
    let query = supabase
      .from('model_memories')
      .select('*')
      .eq('model_type', params.modelType)
      .gte('accuracy_score', 80);
    
    // Filter by data availability
    if (params.hasRevenue) {
      query = query.contains('data_context', { revenue: true });
    }
    if (params.hasFunding) {
      query = query.contains('data_context', { funding: true });
    }
    
    const { data } = await query
      .order('accuracy_score', { ascending: false })
      .limit(1)
      .single();
    
    return data;
  }
}

export const ragMemory = new RAGMemorySystem();