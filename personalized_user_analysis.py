#!/usr/bin/env python3
"""
Personalized user analysis using RAG to query Supabase embeddings
and analyze user-specific funding patterns and growth-adjusted multiples
"""

import os
import json
from supabase import create_client, Client
import numpy as np

def get_supabase_client() -> Client:
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    return create_client(url, key)

class PersonalizedUserAnalyzer:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    def get_user_companies(self, user_id: str):
        """Get companies associated with a specific user"""
        try:
            result = self.supabase.table('companies').select(
                'name, sector, current_arr_usd, revenue_growth_annual_pct, amount_raised, total_invested_usd, embedding, data'
            ).eq('user_id', user_id).execute()
            
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching user companies: {e}")
            return []
    
    def find_comparable_companies(self, user_company, limit=10):
        """Use RAG to find comparable companies based on embeddings"""
        try:
            # Get the embedding of the user's company
            user_embedding = user_company.get('embedding')
            if not user_embedding:
                return []
            
            # Query for similar companies using vector similarity
            # This would use Supabase's vector similarity search
            # For now, we'll get companies in the same sector with similar ARR ranges
            sector = user_company.get('sector')
            arr = user_company.get('current_arr_usd', 0)
            
            # Find companies in similar ARR range (±50%)
            min_arr = arr * 0.5
            max_arr = arr * 1.5
            
            comparable_result = self.supabase.table('companies').select(
                'name, sector, current_arr_usd, revenue_growth_annual_pct, amount_raised, total_invested_usd, embedding'
            ).eq('sector', sector).gte('current_arr_usd', min_arr).lte('current_arr_usd', max_arr).limit(limit).execute()
            
            return comparable_result.data if comparable_result.data else []
            
        except Exception as e:
            print(f"Error finding comparable companies: {e}")
            return []
    
    def analyze_user_patterns(self, user_id: str):
        """Analyze user's specific funding and growth patterns"""
        user_companies = self.get_user_companies(user_id)
        
        if not user_companies:
            return {"error": "No companies found for user"}
        
        analysis = {
            "user_id": user_id,
            "total_companies": len(user_companies),
            "sectors": {},
            "funding_patterns": {},
            "growth_patterns": {},
            "size_distribution": {},
            "personalized_insights": []
        }
        
        # Analyze by sector
        for company in user_companies:
            sector = company.get('sector', 'Unknown')
            if sector not in analysis["sectors"]:
                analysis["sectors"][sector] = []
            analysis["sectors"][sector].append(company)
        
        # Analyze funding patterns
        total_invested = 0
        arr_values = []
        growth_rates = []
        
        for company in user_companies:
            arr = company.get('current_arr_usd', 0)
            growth = company.get('revenue_growth_annual_pct', 0)
            invested = company.get('total_invested_usd', 0)
            
            if arr > 0:
                arr_values.append(arr)
            if growth > 0:
                growth_rates.append(growth)
            if invested > 0:
                total_invested += invested
        
        analysis["funding_patterns"] = {
            "total_invested": total_invested,
            "avg_investment_per_company": total_invested / len(user_companies) if user_companies else 0,
            "investment_concentration": self._calculate_concentration(user_companies, 'total_invested_usd')
        }
        
        analysis["growth_patterns"] = {
            "avg_growth_rate": np.mean(growth_rates) if growth_rates else 0,
            "median_growth_rate": np.median(growth_rates) if growth_rates else 0,
            "growth_consistency": np.std(growth_rates) if growth_rates else 0
        }
        
        # Size distribution
        small_companies = [c for c in user_companies if c.get('current_arr_usd', 0) < 10_000_000]
        medium_companies = [c for c in user_companies if 10_000_000 <= c.get('current_arr_usd', 0) < 50_000_000]
        large_companies = [c for c in user_companies if c.get('current_arr_usd', 0) >= 50_000_000]
        
        analysis["size_distribution"] = {
            "small": len(small_companies),
            "medium": len(medium_companies),
            "large": len(large_companies)
        }
        
        # Generate personalized insights
        analysis["personalized_insights"] = self._generate_personalized_insights(analysis)
        
        return analysis
    
    def _calculate_concentration(self, companies, field):
        """Calculate concentration (Herfindahl index) for a field"""
        values = [company.get(field, 0) for company in companies]
        total = sum(values)
        if total == 0:
            return 0
        
        # Calculate Herfindahl index
        proportions = [v/total for v in values]
        hhi = sum(p**2 for p in proportions)
        return hhi
    
    def _generate_personalized_insights(self, analysis):
        """Generate personalized insights based on user patterns"""
        insights = []
        
        # Sector concentration
        if len(analysis["sectors"]) <= 2:
            insights.append("High sector concentration - consider diversifying across more sectors")
        elif len(analysis["sectors"]) > 5:
            insights.append("Diversified sector approach - good risk management")
        
        # Growth patterns
        avg_growth = analysis["growth_patterns"]["avg_growth_rate"]
        if avg_growth > 100:
            insights.append("High-growth portfolio - focus on scaling and maintaining growth rates")
        elif avg_growth < 25:
            insights.append("Conservative growth portfolio - consider higher-growth opportunities")
        
        # Size distribution
        size_dist = analysis["size_distribution"]
        if size_dist["small"] > size_dist["large"] * 3:
            insights.append("Early-stage focused - consider adding later-stage companies for balance")
        elif size_dist["large"] > size_dist["small"]:
            insights.append("Later-stage focused - consider early-stage opportunities for higher returns")
        
        return insights
    
    def generate_100m_roadmap(self, user_id: str):
        """Generate personalized 100m roadmap based on user's data"""
        analysis = self.analyze_user_patterns(user_id)
        
        if "error" in analysis:
            return analysis
        
        roadmap = {
            "user_analysis": analysis,
            "roadmap_to_100m": {},
            "recommendations": []
        }
        
        # Find companies closest to 100m
        user_companies = self.get_user_companies(user_id)
        companies_over_25m = [c for c in user_companies if c.get('current_arr_usd', 0) >= 25_000_000]
        
        roadmap["roadmap_to_100m"] = {
            "companies_closest_to_100m": companies_over_25m[:5],
            "estimated_time_to_100m": self._estimate_time_to_100m(companies_over_25m),
            "growth_requirements": self._calculate_growth_requirements(companies_over_25m)
        }
        
        # Generate recommendations
        roadmap["recommendations"] = self._generate_roadmap_recommendations(analysis, companies_over_25m)
        
        return roadmap
    
    def _estimate_time_to_100m(self, companies):
        """Estimate time to reach 100m ARR for high-ARR companies"""
        estimates = []
        for company in companies:
            arr = company.get('current_arr_usd', 0)
            growth = company.get('revenue_growth_annual_pct', 0)
            
            if arr > 0 and growth > 0:
                # Calculate years to reach 100m
                years = np.log(100_000_000 / arr) / np.log(1 + growth/100)
                estimates.append({
                    "company": company.get('name'),
                    "current_arr": arr,
                    "growth_rate": growth,
                    "years_to_100m": years
                })
        
        return estimates
    
    def _calculate_growth_requirements(self, companies):
        """Calculate growth requirements to reach 100m in different timeframes"""
        requirements = []
        for timeframe in [2, 3, 5]:  # 2, 3, 5 years
            for company in companies:
                arr = company.get('current_arr_usd', 0)
                if arr > 0:
                    required_growth = (100_000_000 / arr) ** (1/timeframe) - 1
                    requirements.append({
                        "company": company.get('name'),
                        "current_arr": arr,
                        "timeframe_years": timeframe,
                        "required_annual_growth": required_growth * 100
                    })
        
        return requirements
    
    def _generate_roadmap_recommendations(self, analysis, high_arr_companies):
        """Generate specific recommendations for the 100m roadmap"""
        recommendations = []
        
        # Based on user's sector concentration
        if len(analysis["sectors"]) <= 2:
            recommendations.append("Focus on your concentrated sectors but add 1-2 companies in adjacent markets")
        
        # Based on growth rates
        avg_growth = analysis["growth_patterns"]["avg_growth_rate"]
        if avg_growth < 50:
            recommendations.append("Accelerate growth strategies - current portfolio growth below 50% annual")
        
        # Based on size distribution
        if len(high_arr_companies) == 0:
            recommendations.append("No companies over $25M ARR - focus on scaling existing portfolio companies")
        elif len(high_arr_companies) >= 3:
            recommendations.append("Strong pipeline to $100M - maintain growth rates and consider exits")
        
        return recommendations

def main():
    """Example usage of the personalized analyzer"""
    analyzer = PersonalizedUserAnalyzer()
    
    # Example with a user ID (you'd get this from the session)
    user_id = "example-user-id"
    
    print("Generating personalized 100m roadmap...")
    
    roadmap = analyzer.generate_100m_roadmap(user_id)
    
    if "error" in roadmap:
        print(f"Error: {roadmap['error']}")
        return
    
    print(f"\nPersonalized Analysis for User: {user_id}")
    print("=" * 60)
    
    analysis = roadmap["user_analysis"]
    print(f"Total Companies: {analysis['total_companies']}")
    print(f"Sectors: {list(analysis['sectors'].keys())}")
    print(f"Average Growth Rate: {analysis['growth_patterns']['avg_growth_rate']:.1f}%")
    print(f"Total Invested: ${analysis['funding_patterns']['total_invested']:,.0f}")
    
    print(f"\nPersonalized Insights:")
    for insight in analysis["personalized_insights"]:
        print(f"  • {insight}")
    
    print(f"\nRoadmap to $100M:")
    roadmap_data = roadmap["roadmap_to_100m"]
    print(f"Companies closest to $100M: {len(roadmap_data['companies_closest_to_100m'])}")
    
    if roadmap_data["estimated_time_to_100m"]:
        print(f"Estimated time to $100M for top companies:")
        for est in roadmap_data["estimated_time_to_100m"][:3]:
            print(f"  • {est['company']}: {est['years_to_100m']:.1f} years at current growth")
    
    print(f"\nRecommendations:")
    for rec in roadmap["recommendations"]:
        print(f"  • {rec}")

if __name__ == "__main__":
    main()
