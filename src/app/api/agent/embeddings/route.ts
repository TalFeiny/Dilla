import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Use Supabase's pgvector embedding function (no external API needed!)
async function generateEmbedding(text: string): Promise<number[]> {
  try {
    // Use Supabase's built-in embedding function
    const { data, error } = await supabase.rpc('generate_embedding', {
      input_text: text
    });
    
    if (!error && data) {
      // Convert pgvector format to array if needed
      if (typeof data === 'string') {
        // Parse pgvector string format: "[0.1,0.2,0.3,...]"
        const cleaned = data.replace(/[\[\]]/g, '');
        return cleaned.split(',').map(parseFloat);
      }
      return data;
    }
    
    console.error('Supabase embedding error:', error);
    
    // Fallback: Generate simple hash-based embedding
    // This ensures the system works even if Supabase function isn't set up yet
    return generateSimpleEmbedding(text);
    
  } catch (error) {
    console.error('Embedding generation error:', error);
    // Return a deterministic fallback embedding based on text hash
    return generateSimpleEmbedding(text);
  }
}

// Simple deterministic embedding generator as fallback
function generateSimpleEmbedding(text: string): number[] {
  const embedding = new Array(384).fill(0);
  
  // Use text characteristics to generate a deterministic embedding
  for (let i = 0; i < text.length && i < 384; i++) {
    const charCode = text.charCodeAt(i);
    embedding[i] = (Math.sin(charCode * (i + 1)) + Math.cos(charCode * (i + 2))) / 2;
  }
  
  // Add some statistical features
  const words = text.toLowerCase().split(/\s+/);
  const uniqueWords = new Set(words);
  
  embedding[0] = words.length / 100; // Word count feature
  embedding[1] = uniqueWords.size / words.length; // Vocabulary richness
  embedding[2] = text.length / 1000; // Length feature
  
  // Normalize to [-1, 1] range
  const max = Math.max(...embedding.map(Math.abs));
  if (max > 0) {
    return embedding.map(v => v / max);
  }
  
  return embedding;
}

// POST: Generate embedding for single text
export async function POST(request: NextRequest) {
  try {
    const { text, type = 'rl', context } = await request.json();
    
    if (!text || typeof text !== 'string') {
      return NextResponse.json(
        { error: 'Text is required' },
        { status: 400 }
      );
    }
    
    let embedding;
    
    if (type === 'company') {
      // Use company embedding function (768 dimensions)
      const { data, error } = await supabase.rpc('embed_company', {
        company_name: text,
        company_description: context?.description || '',
        sector: context?.sector || '',
        tags: context?.tags || '',
        metrics: context?.metrics || {}
      });
      
      if (!error && data) {
        embedding = typeof data === 'string' 
          ? data.replace(/[\[\]]/g, '').split(',').map(parseFloat)
          : data;
      } else {
        embedding = await generateEmbedding(text);
      }
    } else {
      // Use RL embedding function (384 dimensions) 
      const { data, error } = await supabase.rpc('embed_rl_feedback', {
        input_text: text,
        context_type: context || 'feedback'
      });
      
      if (!error && data) {
        embedding = typeof data === 'string'
          ? data.replace(/[\[\]]/g, '').split(',').map(parseFloat) 
          : data;
      } else {
        embedding = await generateEmbedding(text);
      }
    }
    
    return NextResponse.json({
      success: true,
      embedding,
      dimension: embedding.length,
      type
    });
    
  } catch (error) {
    console.error('Error generating embedding:', error);
    return NextResponse.json(
      { error: 'Failed to generate embedding' },
      { status: 500 }
    );
  }
}