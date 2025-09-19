"""
GRPO (Group Relative Policy Optimization) Training
Train your model using relative preferences from feedback
"""

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import Dataset
import json
from typing import List, Dict, Tuple
import os
from supabase import create_client

class GRPOTrainer:
    """
    Group Relative Policy Optimization for your custom agent
    """
    
    def __init__(self, model_name="Qwen/Qwen2-1.5B"):
        self.model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
    def get_feedback_pairs(self) -> List[Tuple[str, str, str, float]]:
        """
        Get preference pairs from your feedback
        Returns: [(prompt, chosen, rejected, score_diff)]
        """
        supabase = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
        # Get your feedback
        feedback = supabase.table('agent_feedback').select('*').order('created_at').execute()
        
        pairs = []
        feedback_by_prompt = {}
        
        # Group by prompt
        for entry in feedback.data:
            prompt = entry['prompt']
            if prompt not in feedback_by_prompt:
                feedback_by_prompt[prompt] = []
            feedback_by_prompt[prompt].append(entry)
        
        # Create preference pairs
        for prompt, responses in feedback_by_prompt.items():
            if len(responses) >= 2:
                # Sort by score
                responses.sort(key=lambda x: x.get('score', 0))
                
                # Create pairs: low score = rejected, high score = chosen
                for i in range(len(responses) - 1):
                    rejected = responses[i]
                    chosen = responses[i + 1]
                    
                    # Only use if there's a meaningful difference
                    score_diff = chosen.get('score', 0) - rejected.get('score', 0)
                    if score_diff > 0.2:
                        pairs.append((
                            prompt,
                            chosen.get('corrections') or chosen.get('response'),
                            rejected.get('response'),
                            score_diff
                        ))
        
        return pairs
    
    def compute_grpo_loss(self, chosen_logits, rejected_logits, score_diff):
        """
        GRPO loss: maximize log(P(chosen) / P(rejected)) weighted by score difference
        """
        # Get log probabilities
        chosen_logprobs = torch.log_softmax(chosen_logits, dim=-1)
        rejected_logprobs = torch.log_softmax(rejected_logits, dim=-1)
        
        # Compute preference loss
        # Higher score_diff = stronger preference
        beta = 0.1  # KL penalty coefficient
        
        # GRPO objective: maximize relative probability of chosen over rejected
        reward = chosen_logprobs.mean() - rejected_logprobs.mean()
        
        # Scale by score difference (group relative weight)
        scaled_reward = reward * score_diff
        
        # Add KL penalty to prevent model from deviating too much
        kl_penalty = torch.nn.functional.kl_div(chosen_logprobs, rejected_logprobs, reduction='mean')
        
        loss = -scaled_reward + beta * kl_penalty
        
        return loss
    
    def train_grpo(self, num_epochs=3):
        """
        Train using GRPO algorithm
        """
        print("🎯 Starting GRPO Training...")
        
        # Get preference pairs
        pairs = self.get_feedback_pairs()
        print(f"📊 Found {len(pairs)} preference pairs")
        
        if len(pairs) == 0:
            print("⚠️ No feedback pairs found. Collect more feedback first!")
            return
        
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=5e-5)
        
        for epoch in range(num_epochs):
            print(f"\n📈 Epoch {epoch + 1}/{num_epochs}")
            
            total_loss = 0
            # Group pairs by prompt for relative scoring
            grouped_pairs = {}
            for prompt, chosen, rejected, score_diff in pairs:
                if prompt not in grouped_pairs:
                    grouped_pairs[prompt] = []
                grouped_pairs[prompt].append((chosen, rejected, score_diff))
            
            for prompt, group in grouped_pairs.items():
                # GRPO: Compare within groups
                group_losses = []
                
                for chosen, rejected, score_diff in group:
                    # Tokenize
                    prompt_text = f"Human: {prompt}\n\nAssistant: "
                    chosen_text = prompt_text + chosen
                    rejected_text = prompt_text + rejected
                    
                    chosen_inputs = self.tokenizer(chosen_text, return_tensors="pt", truncation=True, max_length=2048)
                    rejected_inputs = self.tokenizer(rejected_text, return_tensors="pt", truncation=True, max_length=2048)
                    
                    # Forward pass
                    chosen_outputs = self.model(**chosen_inputs)
                    rejected_outputs = self.model(**rejected_inputs)
                    
                    # Compute GRPO loss
                    loss = self.compute_grpo_loss(
                        chosen_outputs.logits,
                        rejected_outputs.logits,
                        score_diff
                    )
                    
                    group_losses.append(loss)
                
                # Average loss for the group (relative comparison)
                if group_losses:
                    group_loss = torch.stack(group_losses).mean()
                    
                    # Backprop
                    group_loss.backward()
                    optimizer.step()
                    optimizer.zero_grad()
                    
                    total_loss += group_loss.item()
                    
            avg_loss = total_loss / len(grouped_pairs)
            print(f"Average GRPO Loss: {avg_loss:.4f}")
        
        # Save the GRPO-trained model
        output_path = "models/GRPO_CUSTOM_AGENT"
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        
        print(f"\n✅ GRPO Training Complete!")
        print(f"📦 Model saved to {output_path}")
        print(f"\n🎯 Your model now reflects your preferences through GRPO!")
        
        return output_path
    
    def test_model(self, prompt: str):
        """Test the GRPO-trained model"""
        inputs = self.tokenizer(f"Human: {prompt}\n\nAssistant:", return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=500,
                temperature=0.7,
                do_sample=True
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.split("Assistant:")[-1].strip()


def main():
    """Run GRPO training"""
    
    print("""
    ╔══════════════════════════════════════════╗
    ║         GRPO TRAINING SYSTEM             ║
    ║   Group Relative Policy Optimization     ║
    ╚══════════════════════════════════════════╝
    """)
    
    trainer = GRPOTrainer()
    
    # Train with GRPO
    model_path = trainer.train_grpo(num_epochs=3)
    
    # Test the model
    print("\n🧪 Testing GRPO-trained model:")
    test_prompts = [
        "Create a DCF model for @Ramp",
        "Compare @Deel and @Brex unit economics",
        "Build a Series A pitch deck"
    ]
    
    for prompt in test_prompts:
        print(f"\n📝 Prompt: {prompt}")
        response = trainer.test_model(prompt)
        print(f"🤖 Response: {response[:200]}...")
    
    print("\n✨ GRPO training complete! Your model now uses relative preferences.")
    print("📈 The more feedback you provide, the better it gets!")


if __name__ == "__main__":
    main()