#!/usr/bin/env python3
"""Test website extraction specifically"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_website_extraction():
    """Test the website extraction logic directly"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Simulate search results with multiple domains
    mock_search_results = {
        'general': {
            'success': True,
            'data': {
                'results': [
                    {
                        'url': 'https://techcrunch.com/article-about-dwelly',
                        'content': 'Dwelly, the UK lettings agency platform at dwelly.group, has raised funding...',
                        'title': 'Dwelly raises funding'
                    },
                    {
                        'url': 'https://news.com/dwelly-app', 
                        'content': 'A different company called Dwelly (dwelly.app) offers condominium management software...',
                        'title': 'Condominium app launches'
                    }
                ]
            }
        },
        'website': {
            'success': True,
            'data': {
                'results': [
                    {
                        'url': 'https://dwelly.group/',
                        'content': 'Dwelly - Acquisitions, software, and succession planning for UK lettings agents. We help independent lettings agency owners exit smoothly...',
                        'title': 'Dwelly Group'
                    },
                    {
                        'url': 'https://dwelly.app/',
                        'content': 'Dwelly - Condominium management platform. Unify all condominium information into a single platform...',
                        'title': 'Dwelly App'  
                    }
                ]
            }
        }
    }
    
    # Test the extraction
    print("Testing website extraction for @Dwelly...")
    website = await orchestrator._extract_website_url("@Dwelly", mock_search_results)
    print(f"Extracted website: {website}")
    
    return website

if __name__ == "__main__":
    result = asyncio.run(test_website_extraction())
    print(f"\nFinal result: {result}")