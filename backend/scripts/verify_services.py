#!/usr/bin/env python3
"""
Service Verification Script
Verifies that all services are properly initialized and hardcoded values are replaced
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_service_initialization():
    """Verify all services are initialized"""
    print("🔍 Checking service initialization...")
    
    try:
        from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
        
        orchestrator = UnifiedMCPOrchestrator()
        
        checks = {
            'config_loader': hasattr(orchestrator, 'config_loader') and orchestrator.config_loader is not None,
            'gap_filler': hasattr(orchestrator, 'gap_filler') and orchestrator.gap_filler is not None,
            'valuation_engine': hasattr(orchestrator, 'valuation_engine') and orchestrator.valuation_engine is not None,
            'data_extractor': hasattr(orchestrator, 'data_extractor') and orchestrator.data_extractor is not None,
        }
        
        all_passed = all(checks.values())
        
        for service, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {service}: {'Initialized' if passed else 'MISSING'}")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        return False

def check_config_loader_methods():
    """Verify ConfigLoader methods are accessible"""
    print("\n🔍 Checking ConfigLoader methods...")
    
    try:
        from app.services.config_loader import ConfigLoader
        
        config = ConfigLoader()
        
        methods = {
            'get_stage_defaults': callable(getattr(config, 'get_stage_defaults', None)),
            'get_scoring_thresholds': callable(getattr(config, 'get_scoring_thresholds', None)),
            'get_tam_thresholds': callable(getattr(config, 'get_tam_thresholds', None)),
            'get_revenue_thresholds': callable(getattr(config, 'get_revenue_thresholds', None)),
            'get_exit_scenarios': callable(getattr(config, 'get_exit_scenarios', None)),
        }
        
        all_passed = all(methods.values())
        
        for method, passed in methods.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {method}(): {'Available' if passed else 'MISSING'}")
        
        # Test actual calls
        if all_passed:
            print("\n  Testing method calls...")
            try:
                stage_defaults = config.get_stage_defaults('Series A')
                print(f"    ✅ get_stage_defaults('Series A'): {list(stage_defaults.keys())}")
                
                scoring = config.get_scoring_thresholds()
                print(f"    ✅ get_scoring_thresholds(): {list(scoring.keys())}")
                
                tam = config.get_tam_thresholds()
                print(f"    ✅ get_tam_thresholds(): {list(tam.keys())}")
            except Exception as e:
                print(f"    ❌ Method call failed: {e}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Failed to test ConfigLoader: {e}")
        return False

def check_gap_filler_methods():
    """Verify IntelligentGapFiller methods are accessible"""
    print("\n🔍 Checking IntelligentGapFiller methods...")
    
    try:
        from app.services.intelligent_gap_filler import IntelligentGapFiller
        
        gap_filler = IntelligentGapFiller()
        
        methods = {
            'score_fund_fit': callable(getattr(gap_filler, 'score_fund_fit', None)),
            'calculate_gpu_adjusted_metrics': callable(getattr(gap_filler, 'calculate_gpu_adjusted_metrics', None)),
        }
        
        all_passed = all(methods.values())
        
        for method, passed in methods.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {method}(): {'Available' if passed else 'MISSING'}")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Failed to test IntelligentGapFiller: {e}")
        return False

def check_hardcoded_values():
    """Check for remaining hardcoded values in orchestrator"""
    print("\n🔍 Checking for remaining hardcoded values...")
    
    orchestrator_file = project_root / "app" / "services" / "unified_mcp_orchestrator.py"
    
    if not orchestrator_file.exists():
        print(f"❌ File not found: {orchestrator_file}")
        return False
    
    content = orchestrator_file.read_text()
    lines = content.split('\n')
    
    import re
    issues = []
    
    # Patterns that indicate hardcoded business logic values
    # Exclude lines that use config_loader, _get_config, or _get_stage_defaults_safe
    problematic_patterns = [
        (r'=\s*260_000_000\b', 'Hardcoded $260M fund size'),
        (r'=\s*250_000_000\b', 'Hardcoded $250M fund size'),
        (r'=\s*50_000_000\b', 'Hardcoded $50M value'),
        (r'=\s*5_000_000\b', 'Hardcoded $5M check size'),
        (r'=\s*10_000_000\b', 'Hardcoded $10M value'),
        (r'=\s*100_000_000\b', 'Hardcoded $100M valuation'),
    ]
    
    # Exclude patterns - lines that use service calls are OK
    exclude_patterns = [
        r'config_loader\.get',
        r'_get_config\(',
        r'_get_stage_defaults_safe\(',
        r'stage_defaults\.get\(',
        r'#.*config',
        r'#.*service',
        r'#.*fallback',
    ]
    
    for pattern, description in problematic_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            line_content = lines[line_num - 1].strip()
            
            # Skip if this line uses a service call (config_loader, _get_config, etc.)
            is_excluded = False
            for exclude_pattern in exclude_patterns:
                if re.search(exclude_pattern, line_content, re.IGNORECASE):
                    is_excluded = True
                    break
            
            # Also check surrounding context (3 lines before and after)
            context_start = max(0, line_num - 4)
            context_end = min(len(lines), line_num + 3)
            context = '\n'.join(lines[context_start:context_end])
            
            for exclude_pattern in exclude_patterns:
                if re.search(exclude_pattern, context, re.IGNORECASE):
                    is_excluded = True
                    break
            
            if not is_excluded:
                issues.append((line_num, description, line_content[:100]))
    
    if issues:
        print(f"  ⚠️  Found {len(issues)} potential hardcoded values:")
        for line_num, desc, content in issues[:10]:  # Show first 10
            print(f"    Line {line_num}: {desc}")
            print(f"      {content}")
        if len(issues) > 10:
            print(f"    ... and {len(issues) - 10} more")
        return False
    else:
        print("  ✅ No obvious hardcoded business logic values found")
        return True

def main():
    """Run all verification checks"""
    print("=" * 60)
    print("Service Verification Report")
    print("=" * 60)
    
    results = {
        'Service Initialization': check_service_initialization(),
        'ConfigLoader Methods': check_config_loader_methods(),
        'GapFiller Methods': check_gap_filler_methods(),
        'Hardcoded Values Check': check_hardcoded_values(),
    }
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All checks passed! Services are properly configured.")
        return 0
    else:
        print("❌ Some checks failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

