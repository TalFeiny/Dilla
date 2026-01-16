#!/usr/bin/env python3
"""
Vector RAG analysis on Supabase embeddings to find comparable companies
and analyze growth-adjusted revenue multiples from vectorized data
"""

import os
import json
import numpy as np
from supabase import create_client, Client

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    endpoint = os.getenv('NEXT_PUBLIC_SUPABASE_URL', '').replace('https://', 'https://')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(endpoint, key)

class VectorRAGAnalyzer:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    def find_similar_companies_by_vector(self, query_text: str, limit: int = 10):
        """Use vector similarity to find similar companies based on query text"""
        try:
            # This would typically use Supabase's vector search functionality
            # For now, we'll get all companies and do similarity search manually
            
            # Get all companies with embeddings
            result = self.supabase.table('companies').select(
                'name, sector, current_arr_usd, revenue_growth_annual_pct, revenue_growth_monthly_pct, amount_raised, total_invested_usd, embedding, data'
            ).not_.is_('embedding', 'null').limit(100).execute()
            
            if not result.data:
                return []
            
            # For demo purposes, let's analyze the vectorized data we have
            print(f"Found {len(result.data)} companies with embeddings")
            
            # Let's look at the embedding structure
            sample_embedding = result.data[0].get('embedding')
            if sample_embedding:
                print(f"Embedding dimension: {len(sample_embedding)}")
                print(f"Sample embedding values: {sample_embedding[:5]}...")
            
            return result.data
            
        except Exception as e:
            print(f"Error in vector search: {e}")
            return []
    
    def analyze_vectorized_companies(self):
        """Analyze the vectorized company data for growth-adjusted multiples"""
        try:
            # Get companies with embeddings and financial data
            result = self.supabase.table('companies').select(
                'name, sector, current_arr_usd, revenue_growth_annual_pct, revenue_growth_monthly_pct, amount_raised, total_invested_usd, embedding'
            ).not_.is_('embedding', 'null').gt('current_arr_usd', 1000000).execute()
            
            if not result.data:
                print("No companies found with embeddings and ARR data")
                return {}
            
            print(f"Analyzing {len(result.data)} vectorized companies...")
            
            companies_with_multiples = []
            embedding_analysis = []
            
            for company in result.data:
                name = company.get('name', 'Unknown')
                arr = company.get('current_arr_usd', 0) or 0
                annual_growth = company.get('revenue_growth_annual_pct', 0) or 0
                monthly_growth = company.get('revenue_growth_monthly_pct', 0) or 0
                embedding = company.get('embedding', [])
                
                # Calculate growth rate
                growth_rate = annual_growth or (monthly_growth * 12 if monthly_growth else 0)
                
                # Extract valuation from amount_raised
                amount_raised_data = company.get('amount_raised')
                total_invested = company.get('total_invested_usd', 0) or 0
                
                valuation = None
                if amount_raised_data and isinstance(amount_raised_data, dict):
                    total_raised_millions = amount_raised_data.get('total_raised', 0)
                    if total_raised_millions and total_raised_millions > 0:
                        valuation = total_raised_millions * 1_000_000
                
                # Use total_invested as fallback
                if not valuation and total_invested > 0:
                    valuation = total_invested * 4  # Estimate 4x multiple
                
                if valuation and valuation > 0:
                    revenue_multiple = valuation / arr
                    growth_adjusted_multiple = None
                    
                    if growth_rate > 0:
                        growth_adjusted_multiple = revenue_multiple / (growth_rate / 100)
                    
                    companies_with_multiples.append({
                        'name': name,
                        'sector': company.get('sector', 'Unknown'),
                        'arr': arr,
                        'valuation': valuation,
                        'growth_rate': growth_rate,
                        'revenue_multiple': revenue_multiple,
                        'growth_adjusted_multiple': growth_adjusted_multiple,
                        'embedding': embedding
                    })
                
                # Analyze embedding properties
                if embedding and len(embedding) > 0:
                    embedding_analysis.append({
                        'name': name,
                        'embedding_dim': len(embedding),
                        'embedding_norm': np.linalg.norm(embedding),
                        'embedding_mean': np.mean(embedding),
                        'embedding_std': np.std(embedding)
                    })
            
            print(f"Found {len(companies_with_multiples)} companies with complete financial data")
            print(f"Analyzed {len(embedding_analysis)} embeddings")
            
            # Vector similarity analysis
            if len(companies_with_multiples) > 1:
                similarity_analysis = self._analyze_embedding_similarity(companies_with_multiples)
            else:
                similarity_analysis = {}
            
            return {
                'companies_with_multiples': companies_with_multiples,
                'embedding_analysis': embedding_analysis,
                'similarity_analysis': similarity_analysis,
                'summary_stats': self._calculate_summary_stats(companies_with_multiples)
            }
            
        except Exception as e:
            print(f"Error analyzing vectorized companies: {e}")
            return {}
    
    def _analyze_embedding_similarity(self, companies):
        """Analyze similarity between company embeddings"""
        try:
            # Calculate pairwise similarities
            similarities = []
            company_names = [c['name'] for c in companies]
            embeddings = [np.array(c['embedding']) for c in companies if c['embedding']]
            
            if len(embeddings) < 2:
                return {}
            
            # Calculate cosine similarities
            for i in range(len(embeddings)):
                for j in range(i+1, len(embeddings)):
                    similarity = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append({
                        'company1': company_names[i],
                        'company2': company_names[j],
                        'similarity': similarity
                    })
            
            # Find most similar pairs
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            return {
                'most_similar_pairs': similarities[:5],
                'avg_similarity': np.mean([s['similarity'] for s in similarities]),
                'similarity_std': np.std([s['similarity'] for s in similarities])
            }
            
        except Exception as e:
            print(f"Error in similarity analysis: {e}")
            return {}
    
    def _calculate_summary_stats(self, companies):
        """Calculate summary statistics for the companies"""
        if not companies:
            return {}
        
        multiples = [c['revenue_multiple'] for c in companies]
        growth_adjusted_multiples = [c['growth_adjusted_multiple'] for c in companies if c['growth_adjusted_multiple']]
        growth_rates = [c['growth_rate'] for c in companies if c['growth_rate'] > 0]
        
        return {
            'total_companies': len(companies),
            'avg_revenue_multiple': np.mean(multiples) if multiples else 0,
            'median_revenue_multiple': np.median(multiples) if multiples else 0,
            'avg_growth_adjusted_multiple': np.mean(growth_adjusted_multiples) if growth_adjusted_multiples else 0,
            'median_growth_adjusted_multiple': np.median(growth_adjusted_multiples) if growth_adjusted_multiples else 0,
            'avg_growth_rate': np.mean(growth_rates) if growth_rates else 0,
            'median_growth_rate': np.median(growth_rates) if growth_rates else 0
        }
    
    def find_comparable_by_vector_similarity(self, target_company_name: str, limit: int = 5):
        """Find most similar companies to a target company using vector similarity"""
        try:
            # Get the target company's embedding
            target_result = self.supabase.table('companies').select(
                'name, embedding, current_arr_usd, revenue_growth_annual_pct, amount_raised'
            ).eq('name', target_company_name).single().execute()
            
            if not target_result.data or not target_result.data.get('embedding'):
                print(f"Target company {target_company_name} not found or no embedding")
                return []
            
            target_embedding = np.array(target_result.data['embedding'])
            
            # Get all other companies with embeddings
            all_companies = self.supabase.table('companies').select(
                'name, embedding, current_arr_usd, revenue_growth_annual_pct, amount_raised, sector'
            ).not_.is_('embedding', 'null').neq('name', target_company_name).execute()
            
            if not all_companies.data:
                return []
            
            # Calculate similarities
            similarities = []
            for company in all_companies.data:
                if company.get('embedding'):
                    embedding = np.array(company['embedding'])
                    similarity = np.dot(target_embedding, embedding) / (
                        np.linalg.norm(target_embedding) * np.linalg.norm(embedding)
                    )
                    similarities.append({
                        'name': company['name'],
                        'sector': company.get('sector', 'Unknown'),
                        'arr': company.get('current_arr_usd', 0),
                        'growth_rate': company.get('revenue_growth_annual_pct', 0),
                        'similarity': similarity,
                        'embedding': company['embedding']
                    })
            
            # Sort by similarity and return top matches
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            print(f"Error finding comparable companies: {e}")
            return []

def main():
    """Run vector RAG analysis on Supabase embeddings"""
    analyzer = VectorRAGAnalyzer()
    
    print("Running Vector RAG Analysis on Supabase Embeddings...")
    print("=" * 60)
    
    # Analyze all vectorized companies
    analysis = analyzer.analyze_vectorized_companies()
    
    if not analysis:
        print("No analysis results")
        return
    
    print(f"\nVector Analysis Results:")
    print(f"Companies with complete data: {analysis['summary_stats']['total_companies']}")
    print(f"Average Revenue Multiple: {analysis['summary_stats']['avg_revenue_multiple']:.2f}x")
    print(f"Average Growth-Adjusted Multiple: {analysis['summary_stats']['avg_growth_adjusted_multiple']:.2f}x")
    print(f"Average Growth Rate: {analysis['summary_stats']['avg_growth_rate']:.1f}%")
    
    if analysis['similarity_analysis']:
        sim_analysis = analysis['similarity_analysis']
        print(f"\nEmbedding Similarity Analysis:")
        print(f"Average Similarity: {sim_analysis['avg_similarity']:.3f}")
        print(f"Most Similar Company Pairs:")
        for pair in sim_analysis['most_similar_pairs']:
            print(f"  • {pair['company1']} ↔ {pair['company2']}: {pair['similarity']:.3f}")
    
    # Show top companies by revenue multiple
    companies = analysis['companies_with_multiples']
    if companies:
        companies.sort(key=lambda x: x['revenue_multiple'], reverse=True)
        
        print(f"\nTop 10 Companies by Revenue Multiple:")
        print("-" * 80)
        for i, company in enumerate(companies[:10], 1):
            print(f"{i:2d}. {company['name']} ({company['sector']})")
            print(f"    ARR: ${company['arr']:,.0f}")
            print(f"    Growth Rate: {company['growth_rate']:.1f}%")
            print(f"    Revenue Multiple: {company['revenue_multiple']:.2f}x")
            if company['growth_adjusted_multiple']:
                print(f"    Growth-Adjusted Multiple: {company['growth_adjusted_multiple']:.2f}x")
            print()
    
    # Example: Find comparable companies to a specific company
    print("Example: Finding comparable companies to 'Stripe' using vector similarity...")
    comparable = analyzer.find_comparable_by_vector_similarity('Stripe', limit=5)
    
    if comparable:
        print(f"\nMost similar companies to Stripe:")
        for comp in comparable:
            print(f"  • {comp['name']} ({comp['sector']}) - Similarity: {comp['similarity']:.3f}")
            print(f"    ARR: ${comp['arr']:,.0f}, Growth: {comp['growth_rate']:.1f}%")
    else:
        print("No comparable companies found")

if __name__ == "__main__":
    main()
