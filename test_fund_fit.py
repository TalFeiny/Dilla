#!/usr/bin/env python3
"""Test fund fit scoring integration in deck generation"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_fund_fit():
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test prompt from prompt.md
    prompt = "compare @Adarga to @firefliesai for my 126m fund in year 3 q4 with 49m more to deploy. we have 0.2 dpi with 9 portcos, 4.5 tvpi with one exit and 1 unicorn, we invest in late seed to series B and can lead or follow"
    
    print("Testing fund fit integration...")
    print(f"Prompt: {prompt}")
    print("-" * 50)
    
    # Process request
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="deck",
        context={}
    )
    
    # Check if successful
    if result.get("success"):
        deck_data = result.get("results", {})
        
        # Look for companies data
        if "companies" in orchestrator.shared_data:
            companies = orchestrator.shared_data["companies"]
            print(f"\nFound {len(companies)} companies in shared_data")
            
            for company in companies:
                print(f"\nCompany: {company.get('company', 'Unknown')}")
                print(f"  Stage: {company.get('stage', 'Unknown')}")
                print(f"  Valuation: ${company.get('valuation', 0):,.0f}")
                print(f"  Revenue: ${company.get('revenue', 0):,.0f}")
                print(f"  Inferred Revenue: ${company.get('inferred_revenue', 0):,.0f}")
                print(f"  Business Model: {company.get('business_model', 'Unknown')}")
                print(f"  Sector: {company.get('sector', 'Unknown')}")
                print(f"  Total Funding: ${company.get('total_funding', 0):,.0f}")
                
                # Show funding rounds
                rounds = company.get('funding_rounds', [])
                if rounds:
                    print(f"\n  Funding Rounds ({len(rounds)} total):")
                    for r in rounds[:3]:
                        print(f"    {r.get('round', 'Unknown')}: ${r.get('amount', 0):,.0f} on {r.get('date', 'Unknown')}")
                
                print("\n  Fund Fit Metrics:")
                print(f"    Fund Fit Score: {company.get('fund_fit_score', 0):.1%}")
                print(f"    Optimal Check Size: ${company.get('optimal_check_size', 0):,.0f}")
                print(f"    Target Ownership: {company.get('target_ownership_pct', 0):.1%}")
                print(f"    Actual Ownership: {company.get('actual_ownership_pct', 0):.1%}")
                print(f"    Total Capital Required: ${company.get('total_capital_required', 0):,.0f}")
                print(f"    Exit Ownership: {company.get('exit_ownership_pct', 0):.1%}")
                print(f"    Exit Proceeds: ${company.get('exit_proceeds', 0):,.0f}")
                print(f"    Expected IRR: {company.get('expected_irr', 0):.0f}%")
                
                # Show fund fit reasoning
                reasons = company.get('fund_fit_reasons', [])
                if reasons:
                    print("\n  Fund Fit Reasoning:")
                    for reason in reasons[:3]:
                        print(f"    - {reason}")
        
        # Check deck slides
        if "deck-storytelling" in deck_data:
            deck = deck_data["deck-storytelling"]
            if "slides" in deck:
                print(f"\nGenerated {len(deck['slides'])} slides")
                
                # Show all slides
                for i, slide in enumerate(deck['slides'], 1):
                    print(f"\n{'='*60}")
                    print(f"Slide {i}: {slide.get('type', 'unknown')}")
                    print(f"{'='*60}")
                    
                    content = slide.get('content', {})
                    if slide.get('type') == 'title':
                        print(f"Title: {content.get('title', '')}")
                        print(f"Subtitle: {content.get('subtitle', '')}")
                        print(f"Date: {content.get('date', '')}")
                        
                    elif slide.get('type') == 'summary':
                        print(f"Title: {content.get('title', '')}")
                        print("Bullets:")
                        for bullet in content.get('bullets', []):
                            print(f"  • {bullet}")
                            
                    elif slide.get('type') == 'company':
                        print(f"Company: {content.get('title', '')}")
                        print(f"Business Model: {content.get('business_model', '')}")
                        print("Metrics:")
                        for key, value in content.get('metrics', {}).items():
                            print(f"  {key}: {value}")
                            
                    elif slide.get('type') == 'investment_thesis':
                        print(f"Title: {content.get('title', '')}")
                        print(f"Recommendation: {content.get('recommendation', '')}")
                        
                        scores = content.get('scores', {})
                        print("\nScores:")
                        for key, value in scores.items():
                            print(f"  {key}: {value}")
                        
                        bullets = content.get('bullets', [])
                        print("\nInvestment Details:")
                        for bullet in bullets:
                            print(f"  {bullet}")
                            
                        risks = [r for r in content.get('risks', []) if r]
                        if risks:
                            print("\nRisks:")
                            for risk in risks:
                                print(f"  • {risk}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(test_fund_fit())