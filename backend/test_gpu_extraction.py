#!/usr/bin/env python3
"""Test GPU extraction for key AI companies"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_gpu_extraction():
    orchestrator = UnifiedMCPOrchestrator()
    
    test_companies = ['@Cursor', '@Perplexity', '@Midjourney']
    
    for company_name in test_companies:
        print(f"\n{'='*50}")
        print(f"Testing: {company_name}")
        print('='*50)
        
        try:
            result = await orchestrator.process_request({
                'prompt': f'Analyze {company_name}',
                'output_format': 'analysis'
            })
            
            if 'companies' in result and result['companies']:
                company = result['companies'][0]
                
                # GPU extraction fields
                print(f"\n📊 GPU EXTRACTION:")
                print(f"  Unit of Work: {company.get('gpu_unit_of_work', 'NOT FOUND')}")
                print(f"  Workload Description: {company.get('gpu_workload_description', 'NOT FOUND')}")
                print(f"  Compute Intensity: {company.get('compute_intensity', 'NOT FOUND')}")
                print(f"  Compute Signals: {company.get('compute_signals', 'NOT FOUND')}")
                
                # Business model
                print(f"\n💼 BUSINESS MODEL:")
                print(f"  Category: {company.get('category', 'NOT FOUND')}")
                print(f"  Business Model: {company.get('business_model', 'NOT FOUND')}")
                print(f"  Vertical: {company.get('vertical', 'NOT FOUND')}")
                
                # Unit economics
                if 'unit_economics' in company:
                    ue = company['unit_economics']
                    print(f"\n💰 UNIT ECONOMICS:")
                    print(f"  GPU Cost per Unit: ${ue.get('gpu_cost_per_unit', 'NOT FOUND')}")
                    print(f"  Units per Customer/Month: {ue.get('units_per_customer_per_month', 'NOT FOUND')}")
                    print(f"  Reasoning: {ue.get('reasoning', 'NOT FOUND')}")
                
                # GPU metrics from gap filler
                if 'gpu_metrics' in company:
                    gpu = company['gpu_metrics']
                    print(f"\n🔥 GPU METRICS (Gap Filler):")
                    print(f"  Cost per Unit: ${gpu.get('cost_per_unit', 'NOT FOUND')}")
                    print(f"  Unit of Work: {gpu.get('unit_of_work', 'NOT FOUND')}")
                    print(f"  Monthly GPU Costs: ${gpu.get('monthly_gpu_costs', 'NOT FOUND'):,.0f}")
                    print(f"  Annual GPU Costs: ${gpu.get('annual_gpu_costs', 'NOT FOUND'):,.0f}")
                    print(f"  Investment Thesis: {gpu.get('investment_thesis', 'NOT FOUND')}")
            else:
                print("❌ No company data returned")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gpu_extraction())