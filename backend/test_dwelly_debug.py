import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    print("\n=== Debugging Dwelly Website Selection ===\n")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Mock search results to see what happens
    mock_search_results = {
        'general': {
            'success': True,
            'data': {
                'results': [
                    {
                        'title': 'Dwelly acquires Lime Property Management',
                        'url': 'https://techcrunch.com/dwelly-lime-acquisition',
                        'content': 'UK-based proptech startup Dwelly has acquired Lime Property Management as part of its AI-powered roll-up strategy in the home services sector. The company, founded by ex-Uber executives, is building an AI-enhanced property management platform. Visit their website at dwelly.group for more information.'
                    },
                    {
                        'title': 'Dwelly raises Series A for property tech roll-up',
                        'url': 'https://news.com/dwelly-funding',
                        'content': 'Dwelly, the London-based property technology company, has raised $15M Series A to accelerate its roll-up of home services companies. The startup uses AI to modernize traditional property management.'
                    }
                ]
            }
        },
        'website': {
            'success': True,
            'data': {
                'results': [
                    {
                        'title': 'Dwelly App - Condo Management',
                        'url': 'https://dwelly.app',
                        'content': 'Dwelly app provides condominium management software for HOAs in Rhode Island and Massachusetts. Simple tools for managing your condo association.'
                    },
                    {
                        'title': 'Dwelly Group - AI Property Management',
                        'url': 'https://dwelly.group',
                        'content': 'Dwelly Group is revolutionizing property management through AI and strategic acquisitions. Our platform combines the best of traditional property management with cutting-edge AI technology.'
                    }
                ]
            }
        }
    }
    
    # Extract profile from these results
    profile = await orchestrator._extract_company_profile("Dwelly", mock_search_results)
    print("Extracted Profile:")
    print(json.dumps(profile, indent=2)[:1000])
    
    # Now extract website
    website = await orchestrator._extract_website_url("Dwelly", mock_search_results, profile)
    print(f"\n✅ Selected Website: {website}")
    
    if website and 'dwelly.app' in website:
        print("❌ WRONG: Selected dwelly.app (US condo app)")
    elif website and 'dwelly.group' in website:
        print("✅ CORRECT: Selected dwelly.group (UK PropTech roll-up)")
    elif website is None:
        print("⚠️ Claude rejected all candidates")

if __name__ == "__main__":
    asyncio.run(test())