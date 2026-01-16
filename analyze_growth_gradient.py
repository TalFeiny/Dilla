#!/usr/bin/env python3
"""
Analyze Supabase dataset for growth-adjusted revenue multiples adjusted for company size
This script queries the companies table to extract revenue multiples, growth rates, and size metrics
to understand how valuation multiples correlate with growth and company size, enriching the 100m roadmap.
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from supabase import create_client, Client
import warnings
warnings.filterwarnings('ignore')

# Set up Supabase client
def get_supabase_client() -> Client:
    """Initialize Supabase client with environment variables"""
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        raise ValueError("Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    
    return create_client(url, key)

class GrowthAdjustedMultipleAnalyzer:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.companies_data = None
        self.analysis_results = {}
    
    def fetch_companies_data(self) -> pd.DataFrame:
        """Fetch all companies data from Supabase with valuation and multiple data"""
        print("Fetching companies data from Supabase...")
        
        try:
            # Fetch all companies with key metrics including valuation data
            response = self.supabase.table('companies').select(
                'id, name, website, sector, revenue_model, '
                'current_arr_usd, current_mrr_usd, '
                'revenue_growth_monthly_pct, revenue_growth_annual_pct, '
                'burn_rate_monthly_usd, runway_months, '
                'total_invested_usd, amount_raised, '
                'thesis_match_score, funnel_status, '
                'customer_segment_enterprise_pct, customer_segment_midmarket_pct, customer_segment_sme_pct, '
                'round_size, quarter_raised, '
                'created_at, updated_at, latest_update_date, '
                'has_pwerm_model, pwerm_scenarios_count, '
                'data, metrics, cached_funding_data, '
                'valuation, estimated_valuation'
            ).execute()
            
            if response.data:
                df = pd.DataFrame(response.data)
                print(f"Fetched {len(df)} companies")
                return df
            else:
                print("No companies found")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"Error fetching data: {e}")
            return pd.DataFrame()
    
    def clean_and_prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare the data for analysis"""
        print("Cleaning and preparing data...")
        
        # Convert numeric columns
        numeric_columns = [
            'current_arr_usd', 'current_mrr_usd', 
            'revenue_growth_monthly_pct', 'revenue_growth_annual_pct',
            'burn_rate_monthly_usd', 'runway_months',
            'total_invested_usd', 'thesis_match_score',
            'customer_segment_enterprise_pct', 'customer_segment_midmarket_pct', 'customer_segment_sme_pct',
            'valuation', 'estimated_valuation'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Extract funding data from JSONB fields
        df = self.extract_funding_data(df)
        
        # Calculate derived metrics
        df = self.calculate_derived_metrics(df)
        
        # Filter out companies with no meaningful data
        df = df.dropna(subset=['current_arr_usd'], how='all')
        
        print(f"Data cleaned. {len(df)} companies with meaningful data")
        return df
    
    def extract_funding_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract funding information from JSONB fields"""
        print("Extracting funding data...")
        
        # Extract from amount_raised
        if 'amount_raised' in df.columns:
            df['amount_raised_numeric'] = df['amount_raised'].apply(
                lambda x: float(x.get('amount', 0)) if isinstance(x, dict) else 0
            )
        
        # Extract from round_size
        if 'round_size' in df.columns:
            df['round_size_numeric'] = df['round_size'].apply(
                lambda x: float(x.get('amount', 0)) if isinstance(x, dict) else 0
            )
        
        # Extract from cached_funding_data
        if 'cached_funding_data' in df.columns:
            df['total_funding_from_cache'] = df['cached_funding_data'].apply(
                lambda x: float(x.get('total_funding', 0)) if isinstance(x, dict) else 0
            )
        
        # Extract valuation data from estimated_valuation
        if 'estimated_valuation' in df.columns:
            df['estimated_valuation_numeric'] = df['estimated_valuation'].apply(
                lambda x: float(x.get('estimated_valuation', 0)) if isinstance(x, dict) else 0
            )
        
        return df
    
    def calculate_derived_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate derived metrics for analysis"""
        print("Calculating derived metrics...")
        
        # ARR Growth Rate (annualized from monthly if available)
        df['arr_growth_annual'] = df['revenue_growth_annual_pct'].fillna(
            df['revenue_growth_monthly_pct'] * 12 if 'revenue_growth_monthly_pct' in df.columns else None
        )
        
        # Total Funding (combine different sources)
        funding_cols = ['total_invested_usd', 'amount_raised_numeric', 'total_funding_from_cache']
        df['total_funding_usd'] = df[funding_cols].max(axis=1)
        
        # Valuation (combine different sources)
        valuation_cols = ['valuation', 'estimated_valuation_numeric']
        df['current_valuation_usd'] = df[valuation_cols].max(axis=1)
        
        # Calculate Revenue Multiples
        df['revenue_multiple'] = df['current_valuation_usd'] / df['current_arr_usd'].replace(0, np.nan)
        
        # Growth-Adjusted Revenue Multiple (PEG-like ratio)
        df['growth_adjusted_multiple'] = df['revenue_multiple'] / (df['arr_growth_annual'] / 100).replace(0, np.nan)
        
        # Size-adjusted metrics
        df['log_arr'] = np.log10(df['current_arr_usd'].replace(0, 1))  # Log transform for size
        df['log_valuation'] = np.log10(df['current_valuation_usd'].replace(0, 1))
        
        # Revenue efficiency metrics
        df['revenue_efficiency'] = df['current_arr_usd'] / df['total_funding_usd'].replace(0, np.nan)
        
        # Burn efficiency (ARR / Monthly Burn)
        df['burn_efficiency'] = df['current_arr_usd'] / (df['burn_rate_monthly_usd'] * 12).replace(0, np.nan)
        
        # Customer segment concentration
        customer_cols = ['customer_segment_enterprise_pct', 'customer_segment_midmarket_pct', 'customer_segment_sme_pct']
        df['enterprise_concentration'] = df['customer_segment_enterprise_pct'].fillna(0)
        df['midmarket_concentration'] = df['customer_segment_midmarket_pct'].fillna(0)
        df['sme_concentration'] = df['customer_segment_sme_pct'].fillna(0)
        
        return df
    
    def analyze_growth_stages(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze companies by growth stages based on ARR"""
        print("Analyzing growth stages...")
        
        # Define growth stages based on ARR
        stage_definitions = {
            'Pre-Seed (0-100K)': (0, 100_000),
            'Seed (100K-1M)': (100_000, 1_000_000),
            'Series A (1M-10M)': (1_000_000, 10_000_000),
            'Series B (10M-50M)': (10_000_000, 50_000_000),
            'Growth (50M+)': (50_000_000, float('inf'))
        }
        
        # Categorize companies
        def get_stage(arr):
            if pd.isna(arr):
                return 'Unknown'
            for stage, (min_arr, max_arr) in stage_definitions.items():
                if min_arr <= arr < max_arr:
                    return stage
            return 'Unknown'
        
        df['growth_stage'] = df['current_arr_usd'].apply(get_stage)
        
        # Analyze by stage
        stage_analysis = {}
        for stage in stage_definitions.keys():
            stage_data = df[df['growth_stage'] == stage]
            if len(stage_data) > 0:
                stage_analysis[stage] = {
                    'count': len(stage_data),
                    'avg_arr': stage_data['current_arr_usd'].mean(),
                    'median_arr': stage_data['current_arr_usd'].median(),
                    'avg_growth_rate': stage_data['arr_growth_annual'].mean(),
                    'median_growth_rate': stage_data['arr_growth_annual'].median(),
                    'avg_funding': stage_data['total_funding_usd'].mean(),
                    'median_funding': stage_data['total_funding_usd'].median(),
                    'avg_burn_rate': stage_data['burn_rate_monthly_usd'].mean(),
                    'avg_runway': stage_data['runway_months'].mean(),
                    'enterprise_concentration': stage_data['enterprise_concentration'].mean(),
                    'companies': stage_data['name'].tolist()[:10]  # Top 10 companies in stage
                }
        
        return stage_analysis
    
    def analyze_growth_adjusted_multiples(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze growth-adjusted revenue multiples adjusted for company size"""
        print("Analyzing growth-adjusted revenue multiples...")
        
        # Filter companies with valid data for multiple analysis
        multiple_data = df[
            (df['revenue_multiple'].notna()) & 
            (df['revenue_multiple'] > 0) & 
            (df['revenue_multiple'] < 100) &  # Remove outliers
            (df['arr_growth_annual'].notna()) & 
            (df['arr_growth_annual'] > 0) &
            (df['current_arr_usd'].notna()) & 
            (df['current_arr_usd'] > 0)
        ].copy()
        
        if len(multiple_data) == 0:
            return {'error': 'No valid data for multiple analysis'}
        
        # Calculate size-adjusted multiples using regression
        from scipy import stats
        
        # Log transform for better regression fit
        multiple_data['log_arr'] = np.log10(multiple_data['current_arr_usd'])
        multiple_data['log_multiple'] = np.log10(multiple_data['revenue_multiple'])
        
        # Fit regression: log_multiple = a + b*log_arr + c*growth_rate
        X = multiple_data[['log_arr', 'arr_growth_annual']].values
        y = multiple_data['log_multiple'].values
        
        # Remove any infinite or NaN values
        valid_mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
        X_clean = X[valid_mask]
        y_clean = y[valid_mask]
        
        if len(X_clean) < 3:
            return {'error': 'Insufficient data for regression analysis'}
        
        # Multiple regression
        from sklearn.linear_model import LinearRegression
        reg = LinearRegression().fit(X_clean, y_clean)
        
        # Predict size and growth-adjusted multiples
        multiple_data_clean = multiple_data[valid_mask].copy()
        multiple_data_clean['predicted_log_multiple'] = reg.predict(X_clean)
        multiple_data_clean['predicted_multiple'] = 10 ** multiple_data_clean['predicted_log_multiple']
        
        # Calculate size and growth-adjusted multiple (actual / predicted)
        multiple_data_clean['size_growth_adjusted_multiple'] = (
            multiple_data_clean['revenue_multiple'] / multiple_data_clean['predicted_multiple']
        )
        
        # Analysis by size buckets
        size_buckets = [0, 1_000_000, 5_000_000, 10_000_000, 25_000_000, float('inf')]
        size_labels = ['0-1M', '1-5M', '5-10M', '10-25M', '25M+']
        
        size_analysis = {}
        for i, (min_arr, max_arr) in enumerate(zip(size_buckets[:-1], size_buckets[1:])):
            bucket_data = multiple_data_clean[
                (multiple_data_clean['current_arr_usd'] >= min_arr) & 
                (multiple_data_clean['current_arr_usd'] < max_arr)
            ]
            if len(bucket_data) > 0:
                size_analysis[size_labels[i]] = {
                    'count': len(bucket_data),
                    'avg_revenue_multiple': bucket_data['revenue_multiple'].mean(),
                    'median_revenue_multiple': bucket_data['revenue_multiple'].median(),
                    'avg_growth_rate': bucket_data['arr_growth_annual'].mean(),
                    'avg_growth_adjusted_multiple': bucket_data['growth_adjusted_multiple'].mean(),
                    'avg_size_growth_adjusted_multiple': bucket_data['size_growth_adjusted_multiple'].mean(),
                    'companies': bucket_data[['name', 'revenue_multiple', 'arr_growth_annual', 'size_growth_adjusted_multiple']].to_dict('records')
                }
        
        # Analysis by growth rate buckets
        growth_buckets = [0, 25, 50, 100, 200, float('inf')]
        growth_labels = ['0-25%', '25-50%', '50-100%', '100-200%', '200%+']
        
        growth_analysis = {}
        for i, (min_growth, max_growth) in enumerate(zip(growth_buckets[:-1], growth_buckets[1:])):
            bucket_data = multiple_data_clean[
                (multiple_data_clean['arr_growth_annual'] >= min_growth) & 
                (multiple_data_clean['arr_growth_annual'] < max_growth)
            ]
            if len(bucket_data) > 0:
                growth_analysis[growth_labels[i]] = {
                    'count': len(bucket_data),
                    'avg_revenue_multiple': bucket_data['revenue_multiple'].mean(),
                    'median_revenue_multiple': bucket_data['revenue_multiple'].median(),
                    'avg_arr': bucket_data['current_arr_usd'].mean(),
                    'avg_size_growth_adjusted_multiple': bucket_data['size_growth_adjusted_multiple'].mean(),
                    'companies': bucket_data[['name', 'revenue_multiple', 'arr_growth_annual', 'size_growth_adjusted_multiple']].to_dict('records')
                }
        
        # Sector analysis
        sector_analysis = {}
        if 'sector' in multiple_data_clean.columns:
            for sector in multiple_data_clean['sector'].dropna().unique():
                sector_data = multiple_data_clean[multiple_data_clean['sector'] == sector]
                if len(sector_data) > 0:
                    sector_analysis[sector] = {
                        'count': len(sector_data),
                        'avg_revenue_multiple': sector_data['revenue_multiple'].mean(),
                        'median_revenue_multiple': sector_data['revenue_multiple'].median(),
                        'avg_growth_rate': sector_data['arr_growth_annual'].mean(),
                        'avg_size_growth_adjusted_multiple': sector_data['size_growth_adjusted_multiple'].mean(),
                        'companies': sector_data[['name', 'revenue_multiple', 'arr_growth_annual', 'size_growth_adjusted_multiple']].to_dict('records')
                    }
        
        # Regression coefficients and R-squared
        regression_stats = {
            'r_squared': reg.score(X_clean, y_clean),
            'coefficients': {
                'intercept': reg.intercept_,
                'log_arr_coefficient': reg.coef_[0],
                'growth_rate_coefficient': reg.coef_[1]
            },
            'equation': f"log(multiple) = {reg.intercept_:.3f} + {reg.coef_[0]:.3f}*log(arr) + {reg.coef_[1]:.6f}*growth_rate"
        }
        
        # Overall statistics
        overall_stats = {
            'total_companies': len(multiple_data_clean),
            'avg_revenue_multiple': multiple_data_clean['revenue_multiple'].mean(),
            'median_revenue_multiple': multiple_data_clean['revenue_multiple'].median(),
            'avg_growth_rate': multiple_data_clean['arr_growth_annual'].mean(),
            'avg_growth_adjusted_multiple': multiple_data_clean['growth_adjusted_multiple'].mean(),
            'avg_size_growth_adjusted_multiple': multiple_data_clean['size_growth_adjusted_multiple'].mean(),
            'std_size_growth_adjusted_multiple': multiple_data_clean['size_growth_adjusted_multiple'].std()
        }
        
        return {
            'overall_stats': overall_stats,
            'regression_stats': regression_stats,
            'size_analysis': size_analysis,
            'growth_analysis': growth_analysis,
            'sector_analysis': sector_analysis,
            'data': multiple_data_clean[['name', 'current_arr_usd', 'arr_growth_annual', 'revenue_multiple', 'growth_adjusted_multiple', 'size_growth_adjusted_multiple']].to_dict('records')
        }
    
    def analyze_growth_gradients(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze growth gradients and patterns"""
        print("Analyzing growth gradients...")
        
        # Growth rate analysis
        growth_data = df[df['arr_growth_annual'].notna() & (df['arr_growth_annual'] > 0)]
        
        gradient_analysis = {
            'growth_rate_stats': {
                'mean': growth_data['arr_growth_annual'].mean(),
                'median': growth_data['arr_growth_annual'].median(),
                'std': growth_data['arr_growth_annual'].std(),
                'percentiles': {
                    '25th': growth_data['arr_growth_annual'].quantile(0.25),
                    '75th': growth_data['arr_growth_annual'].quantile(0.75),
                    '90th': growth_data['arr_growth_annual'].quantile(0.90),
                    '95th': growth_data['arr_growth_annual'].quantile(0.95)
                }
            },
            'growth_by_arr_bucket': {},
            'growth_by_sector': {},
            'growth_by_customer_segment': {}
        }
        
        # Growth by ARR bucket
        arr_buckets = [0, 1_000_000, 5_000_000, 10_000_000, 25_000_000, float('inf')]
        arr_labels = ['0-1M', '1-5M', '5-10M', '10-25M', '25M+']
        
        for i, (min_arr, max_arr) in enumerate(zip(arr_buckets[:-1], arr_buckets[1:])):
            bucket_data = growth_data[
                (growth_data['current_arr_usd'] >= min_arr) & 
                (growth_data['current_arr_usd'] < max_arr)
            ]
            if len(bucket_data) > 0:
                gradient_analysis['growth_by_arr_bucket'][arr_labels[i]] = {
                    'count': len(bucket_data),
                    'avg_growth': bucket_data['arr_growth_annual'].mean(),
                    'median_growth': bucket_data['arr_growth_annual'].median(),
                    'avg_arr': bucket_data['current_arr_usd'].mean()
                }
        
        # Growth by sector
        if 'sector' in df.columns:
            for sector in df['sector'].dropna().unique():
                sector_data = growth_data[growth_data['sector'] == sector]
                if len(sector_data) > 0:
                    gradient_analysis['growth_by_sector'][sector] = {
                        'count': len(sector_data),
                        'avg_growth': sector_data['arr_growth_annual'].mean(),
                        'median_growth': sector_data['arr_growth_annual'].median(),
                        'avg_arr': sector_data['current_arr_usd'].mean()
                    }
        
        # Growth by customer segment concentration
        high_enterprise = growth_data[growth_data['enterprise_concentration'] > 70]
        high_midmarket = growth_data[growth_data['midmarket_concentration'] > 70]
        high_sme = growth_data[growth_data['sme_concentration'] > 70]
        
        if len(high_enterprise) > 0:
            gradient_analysis['growth_by_customer_segment']['High Enterprise'] = {
                'count': len(high_enterprise),
                'avg_growth': high_enterprise['arr_growth_annual'].mean(),
                'median_growth': high_enterprise['arr_growth_annual'].median()
            }
        
        if len(high_midmarket) > 0:
            gradient_analysis['growth_by_customer_segment']['High Midmarket'] = {
                'count': len(high_midmarket),
                'avg_growth': high_midmarket['arr_growth_annual'].mean(),
                'median_growth': high_midmarket['arr_growth_annual'].median()
            }
        
        if len(high_sme) > 0:
            gradient_analysis['growth_by_customer_segment']['High SME'] = {
                'count': len(high_sme),
                'avg_growth': high_sme['arr_growth_annual'].mean(),
                'median_growth': high_sme['arr_growth_annual'].median()
            }
        
        return gradient_analysis
    
    def identify_path_to_100m(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Identify the path to $100M ARR based on data patterns"""
        print("Identifying path to $100M ARR...")
        
        # Companies with high ARR (>25M) - closest to 100M
        high_arr_companies = df[df['current_arr_usd'] >= 25_000_000].copy()
        
        # Companies with high growth rates (>100% annually)
        high_growth_companies = df[df['arr_growth_annual'] >= 100].copy()
        
        # Companies with good growth and decent ARR (5M+ ARR, 50%+ growth)
        promising_companies = df[
            (df['current_arr_usd'] >= 5_000_000) & 
            (df['arr_growth_annual'] >= 50)
        ].copy()
        
        path_analysis = {
            'high_arr_leaders': {
                'count': len(high_arr_companies),
                'companies': high_arr_companies[['name', 'current_arr_usd', 'arr_growth_annual', 'sector']].to_dict('records') if len(high_arr_companies) > 0 else [],
                'avg_growth_rate': high_arr_companies['arr_growth_annual'].mean() if len(high_arr_companies) > 0 else 0,
                'avg_funding': high_arr_companies['total_funding_usd'].mean() if len(high_arr_companies) > 0 else 0
            },
            'high_growth_rockets': {
                'count': len(high_growth_companies),
                'companies': high_growth_companies[['name', 'current_arr_usd', 'arr_growth_annual', 'sector']].to_dict('records') if len(high_growth_companies) > 0 else [],
                'avg_arr': high_growth_companies['current_arr_usd'].mean() if len(high_growth_companies) > 0 else 0,
                'avg_funding': high_growth_companies['total_funding_usd'].mean() if len(high_growth_companies) > 0 else 0
            },
            'promising_candidates': {
                'count': len(promising_companies),
                'companies': promising_companies[['name', 'current_arr_usd', 'arr_growth_annual', 'sector']].to_dict('records') if len(promising_companies) > 0 else [],
                'time_to_100m_estimate': self.estimate_time_to_100m(promising_companies)
            }
        }
        
        return path_analysis
    
    def estimate_time_to_100m(self, companies: pd.DataFrame) -> Dict[str, float]:
        """Estimate time to reach $100M ARR for promising companies"""
        if len(companies) == 0:
            return {'avg_years': 0, 'median_years': 0}
        
        # Calculate years to reach $100M based on current ARR and growth rate
        def years_to_100m(row):
            if pd.isna(row['current_arr_usd']) or pd.isna(row['arr_growth_annual']) or row['arr_growth_annual'] <= 0:
                return float('inf')
            
            current_arr = row['current_arr_usd']
            growth_rate = row['arr_growth_annual'] / 100  # Convert percentage to decimal
            
            if current_arr >= 100_000_000:
                return 0  # Already there
            
            # Using compound growth formula: ARR_future = ARR_current * (1 + growth_rate)^years
            # Solving for years: years = log(ARR_future / ARR_current) / log(1 + growth_rate)
            try:
                years = np.log(100_000_000 / current_arr) / np.log(1 + growth_rate)
                return max(0, years)  # Don't return negative years
            except:
                return float('inf')
        
        companies['years_to_100m'] = companies.apply(years_to_100m, axis=1)
        
        # Filter out infinite values
        valid_estimates = companies[companies['years_to_100m'] != float('inf')]['years_to_100m']
        
        if len(valid_estimates) > 0:
            return {
                'avg_years': valid_estimates.mean(),
                'median_years': valid_estimates.median(),
                'min_years': valid_estimates.min(),
                'max_years': valid_estimates.max()
            }
        else:
            return {'avg_years': 0, 'median_years': 0}
    
    def generate_insights_for_slide(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights specifically for the 100m roadmap slide"""
        print("Generating insights for 100m roadmap slide...")
        
        insights = {
            'executive_summary': {
                'total_companies_analyzed': len(self.companies_data) if self.companies_data is not None else 0,
                'companies_with_growth_data': len(self.companies_data[self.companies_data['arr_growth_annual'].notna()]) if self.companies_data is not None else 0,
                'companies_with_multiple_data': len(self.companies_data[(self.companies_data['revenue_multiple'].notna()) & (self.companies_data['revenue_multiple'] > 0)]) if self.companies_data is not None else 0,
                'companies_over_25m_arr': len(self.companies_data[self.companies_data['current_arr_usd'] >= 25_000_000]) if self.companies_data is not None else 0,
                'companies_over_100_percent_growth': len(self.companies_data[self.companies_data['arr_growth_annual'] >= 100]) if self.companies_data is not None else 0
            },
            'growth_stage_insights': {},
            'multiple_insights': {},
            'gradient_insights': {},
            'path_to_100m_insights': {},
            'recommendations': []
        }
        
        # Extract key insights from stage analysis
        if 'stage_analysis' in analysis_results:
            stage_analysis = analysis_results['stage_analysis']
            for stage, data in stage_analysis.items():
                insights['growth_stage_insights'][stage] = {
                    'company_count': data['count'],
                    'average_arr': f"${data['avg_arr']:,.0f}" if not pd.isna(data['avg_arr']) else "N/A",
                    'average_growth_rate': f"{data['avg_growth_rate']:.1f}%" if not pd.isna(data['avg_growth_rate']) else "N/A",
                    'average_funding': f"${data['avg_funding']:,.0f}" if not pd.isna(data['avg_funding']) else "N/A",
                    'key_companies': data['companies'][:5]  # Top 5 companies in each stage
                }
        
        # Extract multiple insights
        if 'multiple_analysis' in analysis_results and 'error' not in analysis_results['multiple_analysis']:
            multiple_analysis = analysis_results['multiple_analysis']
            insights['multiple_insights'] = {
                'overall_stats': multiple_analysis['overall_stats'],
                'regression_equation': multiple_analysis['regression_stats']['equation'],
                'r_squared': f"{multiple_analysis['regression_stats']['r_squared']:.3f}",
                'size_analysis': multiple_analysis['size_analysis'],
                'growth_analysis': multiple_analysis['growth_analysis'],
                'sector_analysis': multiple_analysis['sector_analysis'],
                'top_performers': sorted(
                    multiple_analysis['data'], 
                    key=lambda x: x['size_growth_adjusted_multiple'], 
                    reverse=True
                )[:10]
            }
        
        # Extract gradient insights
        if 'gradient_analysis' in analysis_results:
            gradient = analysis_results['gradient_analysis']
            insights['gradient_insights'] = {
                'median_growth_rate': f"{gradient['growth_rate_stats']['median']:.1f}%",
                'top_quartile_growth': f"{gradient['growth_rate_stats']['percentiles']['75th']:.1f}%",
                'top_10_percent_growth': f"{gradient['growth_rate_stats']['percentiles']['90th']:.1f}%",
                'fastest_growing_sectors': sorted(
                    [(sector, data['avg_growth']) for sector, data in gradient['growth_by_sector'].items()],
                    key=lambda x: x[1], reverse=True
                )[:5],
                'growth_by_arr_bucket': gradient['growth_by_arr_bucket']
            }
        
        # Extract path to 100m insights
        if 'path_analysis' in analysis_results:
            path = analysis_results['path_analysis']
            insights['path_to_100m_insights'] = {
                'high_arr_leaders_count': path['high_arr_leaders']['count'],
                'high_growth_rockets_count': path['high_growth_rockets']['count'],
                'promising_candidates_count': path['promising_candidates']['count'],
                'estimated_time_to_100m': path['promising_candidates']['time_to_100m_estimate']
            }
        
        # Generate recommendations
        insights['recommendations'] = self.generate_recommendations(analysis_results)
        
        return insights
    
    def generate_recommendations(self, analysis_results: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        # Multiple analysis recommendations
        if 'multiple_analysis' in analysis_results and 'error' not in analysis_results['multiple_analysis']:
            multiple_analysis = analysis_results['multiple_analysis']
            
            # Size-adjusted multiple insights
            if multiple_analysis['overall_stats']['avg_size_growth_adjusted_multiple'] > 1.2:
                recommendations.append(f"Portfolio shows strong size-adjusted multiples ({multiple_analysis['overall_stats']['avg_size_growth_adjusted_multiple']:.2f}x) - focus on maintaining premium valuations")
            elif multiple_analysis['overall_stats']['avg_size_growth_adjusted_multiple'] < 0.8:
                recommendations.append(f"Portfolio multiples below market-adjusted levels ({multiple_analysis['overall_stats']['avg_size_growth_adjusted_multiple']:.2f}x) - consider growth acceleration strategies")
            
            # Regression insights
            r_squared = multiple_analysis['regression_stats']['r_squared']
            if r_squared > 0.7:
                recommendations.append(f"Strong correlation between size, growth, and multiples (R²={r_squared:.3f}) - predictable valuation framework established")
            else:
                recommendations.append(f"Moderate correlation in valuation factors (R²={r_squared:.3f}) - consider additional value drivers")
            
            # Size bucket recommendations
            if multiple_analysis['size_analysis']:
                best_size_bucket = max(multiple_analysis['size_analysis'].items(), key=lambda x: x[1]['avg_size_growth_adjusted_multiple'])
                recommendations.append(f"Focus on {best_size_bucket[0]} ARR companies - they show highest size-adjusted multiples ({best_size_bucket[1]['avg_size_growth_adjusted_multiple']:.2f}x)")
        
        if 'stage_analysis' in analysis_results:
            stage_analysis = analysis_results['stage_analysis']
            
            # Find the stage with highest growth rates
            best_growth_stage = max(stage_analysis.items(), key=lambda x: x[1]['avg_growth_rate'] if not pd.isna(x[1]['avg_growth_rate']) else 0)
            recommendations.append(f"Focus on {best_growth_stage[0]} companies - they show the highest average growth rate of {best_growth_stage[1]['avg_growth_rate']:.1f}%")
        
        if 'gradient_analysis' in analysis_results:
            gradient = analysis_results['gradient_analysis']
            
            # Find best performing sector
            if gradient['growth_by_sector']:
                best_sector = max(gradient['growth_by_sector'].items(), key=lambda x: x[1]['avg_growth'])
                recommendations.append(f"Prioritize {best_sector[0]} sector companies - they average {best_sector[1]['avg_growth']:.1f}% annual growth")
            
            # Growth rate recommendations
            if gradient['growth_rate_stats']['median'] > 50:
                recommendations.append("Your portfolio shows strong median growth rates - focus on scaling existing high-performers")
            else:
                recommendations.append("Consider more aggressive growth strategies - median growth rates could be higher")
        
        if 'path_analysis' in analysis_results:
            path = analysis_results['path_analysis']
            
            if path['promising_candidates']['count'] > 0:
                avg_time = path['promising_candidates']['time_to_100m_estimate']['avg_years']
                recommendations.append(f"Focus resources on your {path['promising_candidates']['count']} promising candidates - they could reach $100M ARR in ~{avg_time:.1f} years")
        
        return recommendations
    
    def create_visualizations(self, df: pd.DataFrame, output_dir: str = 'analysis_output'):
        """Create visualizations for the analysis"""
        print("Creating visualizations...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8')
        
        # 1. Growth rate distribution
        fig, ax = plt.subplots(figsize=(12, 8))
        growth_data = df[df['arr_growth_annual'].notna() & (df['arr_growth_annual'] > 0)]['arr_growth_annual']
        if len(growth_data) > 0:
            ax.hist(growth_data, bins=30, alpha=0.7, edgecolor='black')
            ax.axvline(growth_data.median(), color='red', linestyle='--', label=f'Median: {growth_data.median():.1f}%')
            ax.axvline(growth_data.mean(), color='orange', linestyle='--', label=f'Mean: {growth_data.mean():.1f}%')
            ax.set_xlabel('Annual Growth Rate (%)')
            ax.set_ylabel('Number of Companies')
            ax.set_title('Distribution of Annual Growth Rates')
            ax.legend()
            plt.tight_layout()
            plt.savefig(f'{output_dir}/growth_rate_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 2. ARR vs Growth Rate scatter
        fig, ax = plt.subplots(figsize=(12, 8))
        scatter_data = df[(df['current_arr_usd'].notna()) & (df['arr_growth_annual'].notna()) & 
                         (df['current_arr_usd'] > 0) & (df['arr_growth_annual'] > 0)]
        if len(scatter_data) > 0:
            ax.scatter(scatter_data['current_arr_usd'], scatter_data['arr_growth_annual'], alpha=0.6)
            ax.set_xlabel('Current ARR (USD)')
            ax.set_ylabel('Annual Growth Rate (%)')
            ax.set_title('ARR vs Growth Rate')
            ax.set_xscale('log')
            plt.tight_layout()
            plt.savefig(f'{output_dir}/arr_vs_growth_rate.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 3. Growth by stage
        if 'growth_stage' in df.columns:
            fig, ax = plt.subplots(figsize=(12, 8))
            stage_growth = df.groupby('growth_stage')['arr_growth_annual'].agg(['mean', 'count']).reset_index()
            stage_growth = stage_growth[stage_growth['count'] >= 3]  # Only stages with 3+ companies
            
            if len(stage_growth) > 0:
                bars = ax.bar(stage_growth['growth_stage'], stage_growth['mean'])
                ax.set_ylabel('Average Annual Growth Rate (%)')
                ax.set_title('Average Growth Rate by Stage')
                ax.tick_params(axis='x', rotation=45)
                
                # Add count labels on bars
                for bar, count in zip(bars, stage_growth['count']):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                           f'n={count}', ha='center', va='bottom')
                
                plt.tight_layout()
                plt.savefig(f'{output_dir}/growth_by_stage.png', dpi=300, bbox_inches='tight')
                plt.close()
        
        # 4. Revenue Multiple vs Growth Rate scatter
        fig, ax = plt.subplots(figsize=(12, 8))
        multiple_data = df[(df['revenue_multiple'].notna()) & (df['revenue_multiple'] > 0) & 
                          (df['revenue_multiple'] < 100) & (df['arr_growth_annual'].notna()) & 
                          (df['arr_growth_annual'] > 0)]
        if len(multiple_data) > 0:
            scatter = ax.scatter(multiple_data['arr_growth_annual'], multiple_data['revenue_multiple'], 
                               alpha=0.6, s=50)
            ax.set_xlabel('Annual Growth Rate (%)')
            ax.set_ylabel('Revenue Multiple')
            ax.set_title('Revenue Multiple vs Growth Rate')
            plt.tight_layout()
            plt.savefig(f'{output_dir}/revenue_multiple_vs_growth.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 5. Size-Adjusted Multiple Distribution
        fig, ax = plt.subplots(figsize=(12, 8))
        size_adjusted_data = df[df['size_growth_adjusted_multiple'].notna() & 
                               (df['size_growth_adjusted_multiple'] > 0) & 
                               (df['size_growth_adjusted_multiple'] < 5)]  # Remove outliers
        if len(size_adjusted_data) > 0:
            ax.hist(size_adjusted_data['size_growth_adjusted_multiple'], bins=30, alpha=0.7, edgecolor='black')
            ax.axvline(size_adjusted_data['size_growth_adjusted_multiple'].median(), 
                      color='red', linestyle='--', 
                      label=f'Median: {size_adjusted_data["size_growth_adjusted_multiple"].median():.2f}x')
            ax.axvline(1.0, color='green', linestyle='--', label='Market Average (1.0x)')
            ax.set_xlabel('Size-Growth-Adjusted Multiple')
            ax.set_ylabel('Number of Companies')
            ax.set_title('Distribution of Size-Growth-Adjusted Revenue Multiples')
            ax.legend()
            plt.tight_layout()
            plt.savefig(f'{output_dir}/size_adjusted_multiples_distribution.png', dpi=300, bbox_inches='tight')
            plt.close()
        
        # 6. 3D scatter plot: ARR vs Growth vs Multiple (if we have enough data)
        if len(multiple_data) > 10:
            fig = plt.figure(figsize=(15, 10))
            ax = fig.add_subplot(111, projection='3d')
            
            scatter = ax.scatter(multiple_data['current_arr_usd'], 
                               multiple_data['arr_growth_annual'], 
                               multiple_data['revenue_multiple'],
                               c=multiple_data['size_growth_adjusted_multiple'] if 'size_growth_adjusted_multiple' in multiple_data.columns else multiple_data['revenue_multiple'],
                               cmap='viridis', alpha=0.6, s=50)
            
            ax.set_xlabel('ARR (USD)')
            ax.set_ylabel('Growth Rate (%)')
            ax.set_zlabel('Revenue Multiple')
            ax.set_title('3D View: ARR vs Growth vs Multiple')
            ax.set_xscale('log')
            
            plt.colorbar(scatter, label='Size-Adjusted Multiple')
            plt.tight_layout()
            plt.savefig(f'{output_dir}/3d_arr_growth_multiple.png', dpi=300, bbox_inches='tight')
            plt.close()
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run the complete analysis"""
        print("Starting Growth Gradient Analysis...")
        
        # Fetch and clean data
        self.companies_data = self.fetch_companies_data()
        if len(self.companies_data) == 0:
            print("No data available for analysis")
            return {}
        
        self.companies_data = self.clean_and_prepare_data(self.companies_data)
        
        # Run analyses
        self.analysis_results = {
            'stage_analysis': self.analyze_growth_stages(self.companies_data),
            'multiple_analysis': self.analyze_growth_adjusted_multiples(self.companies_data),
            'gradient_analysis': self.analyze_growth_gradients(self.companies_data),
            'path_analysis': self.identify_path_to_100m(self.companies_data)
        }
        
        # Generate insights
        insights = self.generate_insights_for_slide(self.analysis_results)
        
        # Create visualizations
        self.create_visualizations(self.companies_data)
        
        # Save results
        output_dir = 'analysis_output'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f'{output_dir}/growth_gradient_analysis.json', 'w') as f:
            json.dump({
                'analysis_results': self.analysis_results,
                'insights': insights,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2, default=str)
        
        print(f"Analysis complete! Results saved to {output_dir}/")
        return insights
    
    def print_summary(self, insights: Dict[str, Any]):
        """Print a summary of the analysis"""
        print("\n" + "="*80)
        print("GROWTH GRADIENT ANALYSIS SUMMARY")
        print("="*80)
        
        exec_summary = insights['executive_summary']
        print(f"\nDataset Overview:")
        print(f"  • Total companies analyzed: {exec_summary['total_companies_analyzed']}")
        print(f"  • Companies with growth data: {exec_summary['companies_with_growth_data']}")
        print(f"  • Companies over $25M ARR: {exec_summary['companies_over_25m_arr']}")
        print(f"  • Companies with 100%+ growth: {exec_summary['companies_over_100_percent_growth']}")
        
        if 'gradient_insights' in insights:
            gradient = insights['gradient_insights']
            print(f"\nGrowth Gradient Insights:")
            print(f"  • Median growth rate: {gradient['median_growth_rate']}")
            print(f"  • Top quartile growth: {gradient['top_quartile_growth']}")
            print(f"  • Top 10% growth: {gradient['top_10_percent_growth']}")
        
        if 'path_to_100m_insights' in insights:
            path = insights['path_to_100m_insights']
            print(f"\nPath to $100M ARR:")
            print(f"  • High ARR leaders (25M+): {path['high_arr_leaders_count']}")
            print(f"  • High growth rockets (100%+): {path['high_growth_rockets_count']}")
            print(f"  • Promising candidates (5M+ ARR, 50%+ growth): {path['promising_candidates_count']}")
        
        if insights['recommendations']:
            print(f"\nKey Recommendations:")
            for i, rec in enumerate(insights['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "="*80)

def main():
    """Main execution function"""
    analyzer = GrowthGradientAnalyzer()
    
    try:
        insights = analyzer.run_analysis()
        analyzer.print_summary(insights)
        
        print(f"\nDetailed results saved to: analysis_output/growth_gradient_analysis.json")
        print(f"Visualizations saved to: analysis_output/")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
