#!/usr/bin/env python3
"""
Quick script to switch from Qwen to Mistral
"""

import os
import fileinput
import sys

def switch_to_mistral():
    """Update all references from Qwen to Mistral"""
    
    print("🔄 Switching from Qwen to Mistral...")
    
    # Files to update
    files_to_update = [
        "backend/app/services/local_llm_service.py",
        "backend/app/services/unified_mcp_orchestrator.py"
    ]
    
    replacements = [
        ('QWEN2_7B = "qwen2:7b"', 'MISTRAL_7B = "mistral:7b"'),
        ('QWEN2_5_CODER_7B = "qwen2.5-coder:7b"', 'MISTRAL_NEMO = "mistral-nemo"'),
        ('QWEN2_1_5B = "qwen2:1.5b"', 'LLAMA3_SMALL = "llama3.2:3b"'),
        ('qwen2:7b', 'mistral:7b'),
        ('qwen2.5-coder:7b', 'mistral-nemo'),
        ('qwen2:1.5b', 'llama3.2:3b'),
        ('Using local Qwen', 'Using local Mistral'),
        ('Qwen', 'Mistral')  # Generic replacement
    ]
    
    for filepath in files_to_update:
        if os.path.exists(filepath):
            print(f"  Updating {filepath}...")
            
            with open(filepath, 'r') as f:
                content = f.read()
            
            for old, new in replacements:
                content = content.replace(old, new)
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            print(f"  ✅ Updated {filepath}")
        else:
            print(f"  ⚠️ {filepath} not found")
    
    print("\n✅ Switch complete! Now run:")
    print("  1. ollama pull mistral:7b")
    print("  2. ollama pull mistral-nemo")
    print("  3. Restart your backend")
    print("\nMistral will give you:")
    print("  - Better tool calling")
    print("  - Smarter orchestration")
    print("  - Less hallucination")
    print("  - Faster inference")

if __name__ == "__main__":
    switch_to_mistral()