import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_pylon():
    """Test Pylon extraction to see what's in the data"""
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with just fetching and extraction
    companies_data = await orchestrator._execute_company_fetch(
        prompt="@Pylon",
        companies=["@Pylon"],
        context={}
    )
    
    if companies_data and len(companies_data) > 0:
        pylon = companies_data[0]
        print("=== PYLON DATA KEYS ===")
        print(list(pylon.keys()))
        print("\n=== FUNDING ROUNDS ===")
        print(json.dumps(pylon.get('funding_rounds', []), indent=2))
        print("\n=== FUNDING ANALYSIS ===")
        print(json.dumps(pylon.get('funding_analysis', {}), indent=2))
    else:
        print("No data returned")

if __name__ == "__main__":
    asyncio.run(test_pylon())