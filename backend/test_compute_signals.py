#!/usr/bin/env python3
"""
Test if compute signals are working
"""

import asyncio
from app.services.intelligent_gap_filler import IntelligentGapFiller

def test_compute_signals():
    """Test compute intensity detection for various companies"""
    
    gap_filler = IntelligentGapFiller()
    
    test_cases = [
        {
            "company": "Cursor",
            "business_model": "AI-powered code editor and IDE for developers",
            "expected": "extreme"
        },
        {
            "company": "Perplexity", 
            "business_model": "AI-powered conversational search engine",
            "expected": "high"
        },
        {
            "company": "Midjourney",
            "business_model": "AI image generation platform",
            "expected": "extreme"
        },
        {
            "company": "Mercury",
            "business_model": "Digital banking for startups",
            "expected": "none"
        },
        {
            "company": "ChatGPT Wrapper",
            "business_model": "AI chatbot for customer service",
            "expected": "moderate"
        },
        {
            "company": "AgentForce",
            "business_model": "Autonomous AI agents for workflow automation",
            "expected": "high"
        }
    ]
    
    print("\n" + "="*60)
    print("COMPUTE SIGNALS TEST")
    print("="*60)
    
    all_working = True
    
    for test in test_cases:
        company_data = {
            "company": test["company"],
            "business_model": test["business_model"],
            "sector": "Technology"
        }
        
        # Detect compute intensity
        result = gap_filler.detect_compute_intensity(company_data)
        detected = result.get("compute_intensity", "unknown")
        
        # Check if it matches expected
        status = "✅" if detected == test["expected"] else "❌"
        if detected != test["expected"]:
            all_working = False
            
        print(f"\n{status} {test['company']}:")
        print(f"   Business: {test['business_model']}")
        print(f"   Expected: {test['expected']}")
        print(f"   Detected: {detected}")
        print(f"   Cost Range: ${result.get('cost_range', [0,0])[0]}-${result.get('cost_range', [0,0])[1]}")
        print(f"   Margin Impact: -{result.get('margin_impact', 0)*100:.0f}%")
    
    print("\n" + "="*60)
    if all_working:
        print("✅ ALL COMPUTE SIGNALS WORKING CORRECTLY!")
    else:
        print("❌ SOME COMPUTE SIGNALS NOT WORKING AS EXPECTED")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_compute_signals()