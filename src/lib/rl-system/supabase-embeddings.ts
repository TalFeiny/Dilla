'use client';

// Supabase-based embeddings using server-side generation
export class SupabaseEmbeddings {
  private static instance: SupabaseEmbeddings;
  
  private constructor() {}
  
  static getInstance(): SupabaseEmbeddings {
    if (!SupabaseEmbeddings.instance) {
      SupabaseEmbeddings.instance = new SupabaseEmbeddings();
    }
    return SupabaseEmbeddings.instance;
  }
  
  // Generate embeddings via API call to Supabase
  async embed(text: string): Promise<number[]> {
    try {
      const response = await fetch('/api/agent/embeddings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      
      if (!response.ok) {
        throw new Error('Failed to generate embedding');
      }
      
      const { embedding } = await response.json();
      return embedding;
    } catch (error) {
      console.error('Embedding generation failed:', error);
      // Fallback to zero vector if API fails
      return new Array(384).fill(0);
    }
  }
  
  // Batch embed multiple texts
  async embedBatch(texts: string[]): Promise<number[][]> {
    try {
      const response = await fetch('/api/agent/embeddings/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texts })
      });
      
      if (!response.ok) {
        throw new Error('Failed to generate batch embeddings');
      }
      
      const { embeddings } = await response.json();
      return embeddings;
    } catch (error) {
      console.error('Batch embedding generation failed:', error);
      // Return zero vectors as fallback
      return texts.map(() => new Array(384).fill(0));
    }
  }
  
  // Convert grid state to text representation for embedding
  gridToText(grid: Record<string, any>): string {
    const entries = Object.entries(grid)
      .filter(([_, cell]) => cell?.value !== undefined && cell?.value !== '')
      .map(([addr, cell]) => {
        const value = cell.formula || cell.value;
        const type = cell.type || 'text';
        const format = cell.format ? `[${cell.format}]` : '';
        return `${addr}:${value}${format}`;
      })
      .slice(0, 50); // Limit to first 50 cells
    
    return `Spreadsheet state: ${entries.join(', ')}`;
  }
  
  // Embed a grid state
  async embedGrid(grid: Record<string, any>): Promise<number[]> {
    const gridText = this.gridToText(grid);
    return this.embed(gridText);
  }
  
  // Embed an action with context
  async embedAction(action: string, context?: string): Promise<number[]> {
    // Add context to make embeddings more meaningful
    const actionText = context 
      ? `Action in ${context}: ${action}`
      : `Spreadsheet action: ${action}`;
    
    return this.embed(actionText);
  }
  
  // Calculate similarity between two embeddings
  cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length) {
      console.error('Embeddings must have same dimension');
      return 0;
    }
    
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    
    if (normA === 0 || normB === 0) return 0;
    
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }
  
  // Search similar experiences using Supabase vector search
  async searchSimilar(
    embedding: number[],
    tableName: string = 'experience_replay',
    limit: number = 10,
    threshold: number = 0.7
  ): Promise<any[]> {
    try {
      const response = await fetch('/api/agent/embeddings/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding,
          tableName,
          limit,
          threshold
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to search similar embeddings');
      }
      
      const { results } = await response.json();
      return results;
    } catch (error) {
      console.error('Similarity search failed:', error);
      return [];
    }
  }
}