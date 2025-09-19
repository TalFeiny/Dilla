#!/usr/bin/env python3
"""
Batch training script for GRPO from collected feedback
Run this periodically (daily/weekly) to improve model based on user feedback
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.grpo_training_system import get_grpo_system, ToolCallingExample
from app.core.database import supabase_service

async def fetch_recent_feedback(days: int = 7) -> List[Dict[str, Any]]:
    """Fetch preference pairs from last N days"""
    supabase = supabase_service.get_client()
    
    # Get feedback from last N days
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    result = supabase.table('preference_pairs')\
        .select('*')\
        .gte('created_at', since_date)\
        .execute()
    
    return result.data if result.data else []

def convert_feedback_to_examples(feedback_items: List[Dict]) -> List[ToolCallingExample]:
    """Convert user feedback to training examples"""
    examples = []
    
    for item in feedback_items:
        # Only use corrections where user provided better response
        if item.get('score_diff', 0) > 0:
            example = ToolCallingExample(
                prompt=item['prompt'],
                tools_available=[],  # Will be populated based on prompt analysis
                correct_tool_call={},  # Extract from chosen response
                correct_response=item['chosen'],
                incorrect_responses=[item['rejected']],
                feedback_score=item.get('score_diff', 0.5)
            )
            examples.append(example)
    
    return examples

async def train_on_user_feedback():
    """Main training function"""
    print("=" * 60)
    print("GRPO BATCH TRAINING FROM USER FEEDBACK")
    print("=" * 60)
    
    # 1. Fetch recent feedback
    print("\n📊 Fetching recent feedback...")
    feedback = await fetch_recent_feedback(days=7)
    print(f"   Found {len(feedback)} preference pairs")
    
    if not feedback:
        print("   ⚠️  No feedback to train on. Collect more feedback first!")
        return
    
    # 2. Convert to training examples
    print("\n🔄 Converting to training examples...")
    examples = convert_feedback_to_examples(feedback)
    print(f"   Created {len(examples)} training examples")
    
    # 3. Add synthetic examples for diversity
    print("\n🎯 Adding synthetic examples...")
    grpo = get_grpo_system()
    synthetic = grpo.generate_tool_calling_examples()
    examples.extend(synthetic[:5])  # Add 5 synthetic examples
    print(f"   Total examples: {len(examples)}")
    
    # 4. Train GRPO
    print("\n🚀 Training GRPO model...")
    results = await grpo.train_on_examples(examples)
    
    print("\n✅ Training Complete!")
    print(f"   - Examples processed: {results['examples_processed']}")
    print(f"   - New success rate: {results['new_success_rate']}")
    print(f"   - Improvements: {len(results['improvements'])}")
    
    # 5. Save training metadata
    print("\n💾 Saving training metadata...")
    stats = grpo.get_training_stats()
    print(f"   Model: {stats['model']}")
    print(f"   Success rates: {stats['success_rates']}")
    print(f"   Total training batches: {stats['total_examples']}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("1. Model improvements are now active")
    print("2. Continue collecting feedback")
    print("3. Run training again in a week")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(train_on_user_feedback())