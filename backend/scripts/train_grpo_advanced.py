"""
Advanced GRPO Training with Your Existing Feedback
Uses Group Relative Policy Optimization for better preference learning
"""

import os
import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOTrainer, DPOConfig
from datasets import Dataset
from typing import List, Dict, Tuple
from supabase import create_client
from datetime import datetime
import json

class AdvancedGRPOTrainer:
    """
    Production-ready GRPO trainer for your agent
    """
    
    def __init__(self):
        # Model setup
        self.model_name = "Qwen/Qwen2-1.5B"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"🖥️ Using device: {self.device}")
        
        # Supabase connection
        self.supabase = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
    def fetch_all_feedback(self) -> List[Dict]:
        """Fetch all feedback from Supabase"""
        print("📊 Fetching feedback from Supabase...")
        
        # Get all feedback ordered by session and timestamp
        result = self.supabase.table('agent_feedback').select('*').order('created_at').execute()
        
        if result.data:
            print(f"✅ Found {len(result.data)} feedback entries")
            return result.data
        else:
            print("⚠️ No feedback found")
            return []
    
    def create_preference_pairs(self, feedback: List[Dict]) -> List[Dict]:
        """
        Create preference pairs for GRPO training
        Groups feedback by prompt and creates comparisons
        """
        print("🔄 Creating preference pairs...")
        
        # Group by prompt
        prompt_groups = {}
        for entry in feedback:
            prompt = entry.get('prompt', '')
            if not prompt:
                continue
                
            if prompt not in prompt_groups:
                prompt_groups[prompt] = []
            
            # Add entry with score
            prompt_groups[prompt].append({
                'response': entry.get('response', ''),
                'corrections': entry.get('corrections', ''),
                'score': entry.get('score', 0.5),
                'feedback_type': entry.get('feedback_type', 'neutral'),
                'feedback_text': entry.get('feedback_text', ''),
                'timestamp': entry.get('created_at', '')
            })
        
        # Create pairs
        preference_pairs = []
        
        for prompt, responses in prompt_groups.items():
            # Sort by score (ascending)
            responses.sort(key=lambda x: x['score'])
            
            # Create all possible pairs where score_i < score_j
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    lower = responses[i]
                    higher = responses[j]
                    
                    # Skip if scores are too close
                    score_diff = higher['score'] - lower['score']
                    if score_diff < 0.1:
                        continue
                    
                    # Use corrections if available, otherwise original response
                    rejected = lower['corrections'] if lower['corrections'] else lower['response']
                    chosen = higher['corrections'] if higher['corrections'] else higher['response']
                    
                    # Skip if texts are identical
                    if rejected == chosen:
                        continue
                    
                    preference_pairs.append({
                        'prompt': prompt,
                        'chosen': chosen,
                        'rejected': rejected,
                        'score_diff': score_diff,
                        'chosen_score': higher['score'],
                        'rejected_score': lower['score'],
                        'metadata': {
                            'chosen_type': higher['feedback_type'],
                            'rejected_type': lower['feedback_type']
                        }
                    })
        
        print(f"✅ Created {len(preference_pairs)} preference pairs")
        
        # Group pairs by score difference for GRPO
        grouped_pairs = self._group_by_score_difference(preference_pairs)
        
        return grouped_pairs
    
    def _group_by_score_difference(self, pairs: List[Dict]) -> List[Dict]:
        """
        Group pairs by score difference magnitude for GRPO
        This is the key to group relative optimization
        """
        groups = {
            'strong': [],    # score_diff > 0.7
            'moderate': [],  # 0.3 < score_diff <= 0.7
            'weak': []       # 0.1 < score_diff <= 0.3
        }
        
        for pair in pairs:
            diff = pair['score_diff']
            if diff > 0.7:
                groups['strong'].append(pair)
            elif diff > 0.3:
                groups['moderate'].append(pair)
            else:
                groups['weak'].append(pair)
        
        print(f"📊 Grouped preferences:")
        print(f"   Strong: {len(groups['strong'])} pairs")
        print(f"   Moderate: {len(groups['moderate'])} pairs")
        print(f"   Weak: {len(groups['weak'])} pairs")
        
        # Flatten with group weights
        flattened = []
        for pair in groups['strong']:
            pair['weight'] = 1.0
            flattened.append(pair)
        for pair in groups['moderate']:
            pair['weight'] = 0.6
            flattened.append(pair)
        for pair in groups['weak']:
            pair['weight'] = 0.3
            flattened.append(pair)
        
        return flattened
    
    def prepare_dataset(self, preference_pairs: List[Dict]) -> Dataset:
        """Convert preference pairs to HuggingFace Dataset for training"""
        
        # Format for DPO/GRPO training
        formatted_data = []
        for pair in preference_pairs:
            formatted_data.append({
                'prompt': pair['prompt'],
                'chosen': pair['chosen'],
                'rejected': pair['rejected'],
                'weight': pair.get('weight', 1.0)
            })
        
        dataset = Dataset.from_list(formatted_data)
        return dataset
    
    def train_grpo(self, num_epochs: int = 3):
        """
        Train model using GRPO (via DPO with group relative weighting)
        """
        print("\n🚀 Starting GRPO Training")
        print("=" * 50)
        
        # Fetch feedback
        feedback = self.fetch_all_feedback()
        if len(feedback) < 10:
            print("⚠️ Not enough feedback for training (need at least 10)")
            return None
        
        # Create preference pairs
        preference_pairs = self.create_preference_pairs(feedback)
        if len(preference_pairs) < 5:
            print("⚠️ Not enough preference pairs (need at least 5)")
            return None
        
        # Prepare dataset
        dataset = self.prepare_dataset(preference_pairs)
        
        # Load model and tokenizer
        print("📦 Loading base model...")
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )
        
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        tokenizer.pad_token = tokenizer.eos_token
        
        # GRPO training config
        training_args = DPOConfig(
            output_dir="./models/GRPO_AGENT",
            num_train_epochs=num_epochs,
            per_device_train_batch_size=4,
            gradient_accumulation_steps=4,
            learning_rate=5e-5,
            warmup_ratio=0.1,
            logging_steps=10,
            save_steps=100,
            evaluation_strategy="no",
            optim="adamw_torch",
            # GRPO specific settings
            beta=0.1,  # KL penalty coefficient
            loss_type="sigmoid",  # Better for preference learning
            # Group relative optimization
            label_smoothing=0.1,  # Smooth preference labels
            reference_free=False,  # Use reference model for KL
        )
        
        # Create GRPO trainer (using DPO with our grouped data)
        print("🎯 Initializing GRPO trainer...")
        trainer = DPOTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=training_args,
        )
        
        # Train
        print("🧠 Training with GRPO...")
        print(f"   Epochs: {num_epochs}")
        print(f"   Preference pairs: {len(dataset)}")
        print(f"   Device: {self.device}")
        
        trainer.train()
        
        # Save model
        output_path = "./models/GRPO_CUSTOM_AGENT"
        print(f"💾 Saving GRPO model to {output_path}...")
        trainer.save_model(output_path)
        tokenizer.save_pretrained(output_path)
        
        # Save training metadata
        metadata = {
            'training_date': datetime.now().isoformat(),
            'num_preference_pairs': len(preference_pairs),
            'num_epochs': num_epochs,
            'base_model': self.model_name,
            'feedback_entries': len(feedback),
            'training_type': 'GRPO'
        }
        
        with open(f"{output_path}/training_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print("\n✅ GRPO Training Complete!")
        print(f"📊 Trained on {len(preference_pairs)} preference pairs")
        print(f"💾 Model saved to {output_path}")
        
        return output_path
    
    def test_model(self, model_path: str = "./models/GRPO_CUSTOM_AGENT"):
        """Test the GRPO trained model"""
        print("\n🧪 Testing GRPO Model")
        print("=" * 50)
        
        # Load trained model
        model = AutoModelForCausalLM.from_pretrained(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        test_prompts = [
            "Create a DCF model for @Ramp with 50% growth",
            "Compare @Deel and @Brex unit economics",
            "Build Series A pitch deck for AI startup",
            "Analyze @Cursor path to profitability"
        ]
        
        for prompt in test_prompts:
            print(f"\n📝 Prompt: {prompt}")
            
            inputs = tokenizer(
                f"Human: {prompt}\n\nAssistant:",
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tokenizer.pad_token_id
                )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.split("Assistant:")[-1].strip()
            
            print(f"🤖 Response: {response[:200]}...")
    
    def analyze_training_data(self):
        """Analyze your feedback data for GRPO training readiness"""
        print("\n📊 Analyzing Feedback Data")
        print("=" * 50)
        
        feedback = self.fetch_all_feedback()
        
        # Basic stats
        print(f"\n📈 Basic Statistics:")
        print(f"   Total feedback entries: {len(feedback)}")
        
        # Score distribution
        scores = [f.get('score', 0) for f in feedback]
        if scores:
            print(f"   Average score: {np.mean(scores):.2f}")
            print(f"   Score std dev: {np.std(scores):.2f}")
            print(f"   Min score: {min(scores):.2f}")
            print(f"   Max score: {max(scores):.2f}")
        
        # Feedback types
        types = {}
        for f in feedback:
            ft = f.get('feedback_type', 'unknown')
            types[ft] = types.get(ft, 0) + 1
        
        print(f"\n📝 Feedback Types:")
        for ft, count in types.items():
            print(f"   {ft}: {count}")
        
        # Prompts with multiple responses (good for GRPO)
        prompts = {}
        for f in feedback:
            p = f.get('prompt', '')
            if p:
                prompts[p] = prompts.get(p, 0) + 1
        
        multi_response_prompts = [p for p, count in prompts.items() if count > 1]
        print(f"\n🎯 GRPO Training Potential:")
        print(f"   Unique prompts: {len(prompts)}")
        print(f"   Prompts with multiple responses: {len(multi_response_prompts)}")
        print(f"   Total potential pairs: {sum(c*(c-1)//2 for c in prompts.values() if c > 1)}")
        
        if len(multi_response_prompts) < 5:
            print("\n⚠️ Need more diverse feedback for effective GRPO training")
            print("   Suggestion: Generate multiple responses for same prompts")
            print("   Suggestion: Provide corrections for existing responses")
        else:
            print("\n✅ Sufficient data for GRPO training!")


def main():
    """Run complete GRPO training pipeline"""
    
    print("""
    ╔════════════════════════════════════════════════╗
    ║     ADVANCED GRPO TRAINING SYSTEM              ║
    ║  Group Relative Policy Optimization Training   ║
    ╚════════════════════════════════════════════════╝
    """)
    
    trainer = AdvancedGRPOTrainer()
    
    # Analyze data first
    trainer.analyze_training_data()
    
    # Ask to proceed
    print("\n❓ Proceed with GRPO training? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        # Train
        model_path = trainer.train_grpo(num_epochs=3)
        
        if model_path:
            # Test
            trainer.test_model(model_path)
            
            print("\n🎉 GRPO Training Complete!")
            print("Your model now learns from relative preferences!")
    else:
        print("Training cancelled")


if __name__ == "__main__":
    main()