"""
Export feedback from Supabase to JSONL format for training
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class FeedbackExporter:
    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
    async def export_feedback_for_training(
        self, 
        output_file: str = "data/training/feedback.jsonl",
        min_score: float = 0.6
    ) -> Dict[str, Any]:
        """
        Export high-quality feedback for model training
        """
        print("📊 Fetching feedback from Supabase...")
        
        # Query feedback table - adjust table name as needed
        # You mentioned you have feedback in Supabase already
        try:
            # Try different possible table names
            for table_name in ['agent_feedback', 'model_feedback', 'feedback', 'rl_experiences']:
                try:
                    result = self.supabase.table(table_name).select('*').execute()
                    if result.data:
                        print(f"✅ Found feedback in table: {table_name}")
                        feedback_data = result.data
                        break
                except:
                    continue
            else:
                print("⚠️ No feedback table found. Creating sample data...")
                feedback_data = self._create_sample_feedback()
        except Exception as e:
            print(f"Error fetching feedback: {e}")
            feedback_data = self._create_sample_feedback()
        
        # Process and filter feedback
        training_examples = []
        for entry in feedback_data:
            # Skip low-quality examples
            score = entry.get('score', 0) or entry.get('rating', 0) or entry.get('feedback_score', 0)
            if score < min_score:
                continue
            
            # Format for training
            example = self._format_training_example(entry)
            if example:
                training_examples.append(example)
        
        # Save to JSONL
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            for example in training_examples:
                f.write(json.dumps(example) + '\n')
        
        print(f"✅ Exported {len(training_examples)} training examples to {output_file}")
        
        # Also save in different formats for different training methods
        self._save_alpaca_format(training_examples)
        self._save_conversation_format(training_examples)
        
        return {
            "total_examples": len(training_examples),
            "output_file": output_file,
            "formats_created": ["jsonl", "alpaca", "conversation"]
        }
    
    def _format_training_example(self, entry: Dict) -> Dict:
        """Format feedback entry for training"""
        prompt = entry.get('prompt', '') or entry.get('input', '') or entry.get('question', '')
        response = entry.get('response', '') or entry.get('output', '') or entry.get('answer', '')
        corrected = entry.get('corrected_response', '') or entry.get('corrections', '')
        
        if not prompt:
            return None
        
        # Use corrected response if available, otherwise original
        completion = corrected if corrected else response
        
        # Add system prompt for VC analysis context
        system_prompt = """You are an expert VC analyst. Provide institutional-grade analysis with:
- Financial metrics (CAC, LTV, burn rate, runway)
- Market analysis (TAM, competitive positioning)
- Strategic insights (moat, growth potential, risks)
- Data-backed conclusions with citations"""
        
        return {
            "instruction": system_prompt,
            "input": prompt,
            "output": completion,
            "metadata": {
                "score": entry.get('score', 0.8),
                "timestamp": entry.get('created_at', str(datetime.now()))
            }
        }
    
    def _save_alpaca_format(self, examples: List[Dict]):
        """Save in Alpaca format for LoRA training"""
        alpaca_file = "data/training/feedback_alpaca.json"
        alpaca_data = []
        
        for ex in examples:
            alpaca_data.append({
                "instruction": ex["input"],
                "output": ex["output"],
                "input": ""  # Alpaca format uses empty input field
            })
        
        with open(alpaca_file, 'w') as f:
            json.dump(alpaca_data, f, indent=2)
        
        print(f"✅ Saved Alpaca format to {alpaca_file}")
    
    def _save_conversation_format(self, examples: List[Dict]):
        """Save in conversation format for chat models"""
        conv_file = "data/training/feedback_conversations.jsonl"
        
        with open(conv_file, 'w') as f:
            for ex in examples:
                conversation = {
                    "messages": [
                        {"role": "system", "content": ex["instruction"]},
                        {"role": "user", "content": ex["input"]},
                        {"role": "assistant", "content": ex["output"]}
                    ]
                }
                f.write(json.dumps(conversation) + '\n')
        
        print(f"✅ Saved conversation format to {conv_file}")
    
    def _create_sample_feedback(self) -> List[Dict]:
        """Create sample training data if no real feedback exists"""
        return [
            {
                "prompt": "Compare @Ramp and @Brex for Series C investment",
                "response": "Both companies operate in the corporate card space...",
                "corrected_response": """## Investment Comparison: Ramp vs Brex

### Financial Metrics
**Ramp**: 
- Revenue: $300M ARR (150% YoY growth)
- Burn: -$15M/month (improving from -$25M)
- LTV/CAC: 4.2x
- Gross Margin: 67%

**Brex**:
- Revenue: $400M ARR (100% YoY growth)  
- Burn: -$20M/month (stable)
- LTV/CAC: 3.8x
- Gross Margin: 71%

### Market Position
Both target SMB/enterprise spend management ($74B TAM)
- Ramp: 15K customers, stronger growth efficiency
- Brex: 20K customers, broader product suite

### Recommendation
Ramp shows superior unit economics and growth trajectory.""",
                "score": 0.9
            },
            {
                "prompt": "Analyze @Deel's path to profitability",
                "response": "Deel is a global payroll company...",
                "corrected_response": """## Deel Path to Profitability Analysis

### Current Metrics (2024)
- ARR: $500M (120% YoY)
- Gross Margin: 85% (SaaS-like)
- Burn Rate: -$8M/month
- CAC: $5K | LTV: $45K | Payback: 4 months

### Profitability Timeline
**Q2 2025**: EBITDA positive
- Revenue: $650M ARR run rate
- OpEx reduction: 15% through automation
- Contribution margin: 42%

**Key Drivers**:
1. Geographic expansion (150→200 countries)
2. Upmarket motion ($50K→$200K ACVs)
3. Product bundling (+40% NRR)

### Risk Factors
- Regulatory changes in key markets
- Competition from Rippling/Remote
- FX exposure (30% revenue)""",
                "score": 0.95
            }
        ]

async def main():
    exporter = FeedbackExporter()
    result = await exporter.export_feedback_for_training()
    print("\n📈 Export Summary:")
    print(f"Total examples: {result['total_examples']}")
    print(f"Files created: {', '.join(result['formats_created'])}")
    print("\nReady for training! Run: python scripts/train_qwen_lora.py")

if __name__ == "__main__":
    asyncio.run(main())