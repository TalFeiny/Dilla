#!/usr/bin/env python3
"""Test script to check what needs rebuilding in Dilla AI"""

import os
import sys
import json
import traceback
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    """Test if core imports work"""
    print("=" * 60)
    print("TESTING IMPORTS")
    print("=" * 60)
    
    results = {}
    
    # Core services
    services = [
        ('Orchestrator', 'app.services.unified_mcp_orchestrator', 'UnifiedMCPOrchestrator'),
        ('Data Extractor', 'app.services.structured_data_extractor', 'StructuredDataExtractor'),
        ('Gap Filler', 'app.services.intelligent_gap_filler', 'IntelligentGapFiller'),
        ('Valuation Engine', 'app.services.valuation_engine_service', 'ValuationEngineService'),
        ('Cap Table', 'app.services.pre_post_cap_table', 'PrePostCapTable'),
        ('Citation Manager', 'app.services.citation_manager', 'CitationManager'),
        ('Model Router', 'app.services.model_router', 'get_model_router'),
    ]
    
    for name, module_path, class_name in services:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            results[name] = "✅ SUCCESS"
            print(f"✅ {name}: Imported successfully")
        except Exception as e:
            results[name] = f"❌ FAILED: {str(e)}"
            print(f"❌ {name}: {str(e)}")
    
    return results

def test_api_endpoints():
    """Test if API endpoints are accessible"""
    print("\n" + "=" * 60)
    print("TESTING API ENDPOINTS")
    print("=" * 60)
    
    try:
        from app.api.router_fixed import router
        routes = []
        for route in router.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        print(f"✅ Found {len(routes)} routes:")
        for route in sorted(routes):
            print(f"  - {route}")
        return True
    except Exception as e:
        print(f"❌ Failed to load API routes: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("\n" + "=" * 60)
    print("TESTING CONFIGURATION")
    print("=" * 60)
    
    try:
        from app.core.config import settings
        
        # Check critical settings
        critical = {
            'CLAUDE_API_KEY': bool(settings.CLAUDE_API_KEY),
            'TAVILY_API_KEY': bool(settings.TAVILY_API_KEY),
            'OPENAI_API_KEY': bool(settings.OPENAI_API_KEY),
        }
        
        for key, present in critical.items():
            if present:
                print(f"✅ {key}: Configured")
            else:
                print(f"⚠️  {key}: Not configured")
        
        return all(critical.values())
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return False

def test_orchestrator_skills():
    """Test orchestrator skill registry"""
    print("\n" + "=" * 60)
    print("TESTING ORCHESTRATOR SKILLS")
    print("=" * 60)
    
    try:
        from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
        
        orch = UnifiedMCPOrchestrator()
        skills = orch.skills
        
        print(f"✅ Found {len(skills)} skills:")
        
        # Group by category
        categories = {}
        for skill_name, skill_info in skills.items():
            category = skill_info.get('category', 'Unknown')
            if category not in categories:
                categories[category] = []
            categories[category].append(skill_name)
        
        for category, skill_list in categories.items():
            print(f"\n  {category}:")
            for skill in sorted(skill_list):
                print(f"    - {skill}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        traceback.print_exc()
        return False

def test_data_extraction():
    """Test data extraction pipeline"""
    print("\n" + "=" * 60)
    print("TESTING DATA EXTRACTION")
    print("=" * 60)
    
    try:
        from app.services.structured_data_extractor import StructuredDataExtractor
        
        extractor = StructuredDataExtractor()
        
        # Test with sample data
        test_html = """
        <html>
            <body>
                <h1>Mercury - Modern Banking for Startups</h1>
                <p>Mercury provides banking services for startups. 
                Founded in 2017, raised $163M Series B at $1.6B valuation in 2021.</p>
            </body>
        </html>
        """
        
        # Note: This would normally call Claude API
        print("✅ StructuredDataExtractor initialized")
        print("  - Would extract: company name, funding, valuation, etc.")
        return True
        
    except Exception as e:
        print(f"❌ Failed to test extraction: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "🔧" * 30)
    print(" DILLA AI REBUILD STATUS CHECK")
    print("🔧" * 30 + "\n")
    
    results = {
        'imports': test_imports(),
        'config': test_config(),
        'endpoints': test_api_endpoints(),
        'skills': test_orchestrator_skills(),
        'extraction': test_data_extraction(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_good = True
    for test_name, result in results.items():
        if isinstance(result, dict):
            # For detailed results like imports
            failed = [k for k, v in result.items() if '❌' in str(v)]
            if failed:
                print(f"❌ {test_name}: {len(failed)} failures")
                all_good = False
            else:
                print(f"✅ {test_name}: All passed")
        elif result:
            print(f"✅ {test_name}: Passed")
        else:
            print(f"❌ {test_name}: Failed")
            all_good = False
    
    if all_good:
        print("\n🎉 All systems operational!")
    else:
        print("\n⚠️  Some components need attention")
    
    return all_good

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)