import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { processSemanticQuery, toSQL, toWebSearchQuery } from '@/lib/semantic-query-processor';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Tavily search for web data
async function searchWeb(query: string) {
  try {
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: query,
        search_depth: 'advanced',
        max_results: 5,
        include_domains: [
          'techcrunch.com',
          'forbes.com',
          'bloomberg.com',
          'reuters.com',
          'crunchbase.com',
          'pitchbook.com'
        ]
      })
    });
    
    if (!response.ok) return null;
    const data = await response.json();
    return data.results || [];
  } catch (error) {
    console.error('Web search error:', error);
    return [];
  }
}

// Extract structured data from web results
function extractWebData(webResults: any[], metrics: string[]) {
  const extractedData: any[] = [];
  
  webResults.forEach(result => {
    const content = result.content || '';
    const data: any = {
      source: result.url,
      title: result.title,
      confidence: 0.7 // Web data has lower confidence
    };
    
    // Try to extract metrics from content
    metrics.forEach(metric => {
      // Look for patterns like "revenue of $X" or "$X in revenue"
      const patterns = [
        new RegExp(`${metric}[\\s\\w]*?\\$?([\\d,]+\\.?\\d*)\\s*(million|billion|M|B)?`, 'i'),
        new RegExp(`\\$?([\\d,]+\\.?\\d*)\\s*(million|billion|M|B)?[\\s\\w]*?${metric}`, 'i')
      ];
      
      for (const pattern of patterns) {
        const match = content.match(pattern);
        if (match) {
          let value = parseFloat(match[1].replace(/,/g, ''));
          const unit = match[2]?.toLowerCase();
          if (unit?.startsWith('b')) value *= 1e9;
          else if (unit?.startsWith('m')) value *= 1e6;
          
          data[metric] = value;
          break;
        }
      }
    });
    
    if (Object.keys(data).length > 3) { // Has more than just source/title/confidence
      extractedData.push(data);
    }
  });
  
  return extractedData;
}

// Merge data from multiple sources
function mergeResults(dbData: any[], webData: any[], apiData: any[] = []) {
  const merged = new Map();
  
  // Start with database data (highest confidence)
  dbData.forEach(row => {
    const key = row.name || row.id;
    merged.set(key, {
      ...row,
      sources: [{
        type: 'database',
        confidence: 0.95,
        timestamp: new Date().toISOString()
      }]
    });
  });
  
  // Merge web data
  webData.forEach(item => {
    // Try to match with existing data
    let matched = false;
    for (const [key, value] of merged.entries()) {
      if (item.title?.toLowerCase().includes(key.toLowerCase())) {
        // Merge the data
        Object.keys(item).forEach(field => {
          if (!value[field] && item[field]) {
            value[field] = item[field];
            value.sources.push({
              type: 'web',
              url: item.source,
              confidence: 0.7
            });
          }
        });
        matched = true;
        break;
      }
    }
    
    // If no match, add as new entry
    if (!matched && item.title) {
      merged.set(item.title, {
        ...item,
        sources: [{
          type: 'web',
          url: item.source,
          confidence: 0.7
        }]
      });
    }
  });
  
  return Array.from(merged.values());
}

export async function POST(request: NextRequest) {
  try {
    const { query } = await request.json();
    
    if (!query) {
      return NextResponse.json(
        { error: 'Query is required' },
        { status: 400 }
      );
    }
    
    console.log('Processing semantic query:', query);
    
    // Process the query to get structured format
    const structured = processSemanticQuery(query);
    console.log('Structured query:', structured);
    
    // Execute across different sources in parallel
    const promises: Promise<any>[] = [];
    
    // 1. Database query
    if (structured.sources.includes('database')) {
      const sql = toSQL(structured);
      console.log('SQL query:', sql);
      
      // For now, use simpler Supabase query builder
      let dbQuery = supabase.from('companies').select('*');
      
      // Apply filters
      if (structured.entities.companies?.length > 0) {
        dbQuery = dbQuery.in('name', structured.entities.companies);
      }
      
      if (structured.entities.filters?.sector) {
        dbQuery = dbQuery.eq('sector', structured.entities.filters.sector);
      }
      
      if (structured.entities.filters?.revenue?.$gt) {
        dbQuery = dbQuery.gt('revenue', structured.entities.filters.revenue.$gt);
      }
      
      if (structured.entities.filters?.growth_rate?.$gt) {
        dbQuery = dbQuery.gt('growth_rate', structured.entities.filters.growth_rate.$gt);
      }
      
      if (structured.output.limit) {
        dbQuery = dbQuery.limit(structured.output.limit);
      }
      
      promises.push(dbQuery.then(result => result.data || []));
    } else {
      promises.push(Promise.resolve([]));
    }
    
    // 2. Web search
    if (structured.sources.includes('web')) {
      const webQuery = toWebSearchQuery(structured);
      console.log('Web search query:', webQuery);
      promises.push(
        searchWeb(webQuery).then(results => 
          extractWebData(results, structured.entities.metrics || [])
        )
      );
    } else {
      promises.push(Promise.resolve([]));
    }
    
    // 3. API calls (placeholder for now)
    if (structured.sources.includes('api')) {
      promises.push(Promise.resolve([]));
    }
    
    // Wait for all sources
    const [dbData, webData, apiData] = await Promise.all(promises);
    
    console.log('Database results:', dbData?.length || 0);
    console.log('Web results:', webData?.length || 0);
    
    // Merge results from all sources
    const mergedResults = mergeResults(dbData, webData, apiData);
    
    // Build response with metadata
    const response = {
      query: query,
      structured: structured,
      results: mergedResults,
      metadata: {
        total: mergedResults.length,
        sources: {
          database: dbData?.length || 0,
          web: webData?.length || 0,
          api: apiData?.length || 0
        },
        sql: structured.sources.includes('database') ? toSQL(structured) : null,
        webQuery: structured.sources.includes('web') ? toWebSearchQuery(structured) : null
      }
    };
    
    return NextResponse.json(response);
    
  } catch (error) {
    console.error('Semantic query error:', error);
    return NextResponse.json(
      { error: 'Failed to process semantic query', details: error },
      { status: 500 }
    );
  }
}