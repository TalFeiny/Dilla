"""
Train Your Own Custom Agent Model from Feedback
This creates YOUR weights based on YOUR feedback - not just prompting
"""

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType
import json
import os
from typing import Dict, List
from supabase import create_client

class CustomAgentTrainer:
    """
    Train a model that becomes YOUR agent with YOUR decision-making
    """
    
    def __init__(self):
        # Your model - small enough to train locally
        self.base_model = "Qwen/Qwen2-1.5B"  # Or "mistralai/Mistral-7B-v0.1"
        
        # These will be YOUR weights after training
        self.model_weights_path = "models/MY_CUSTOM_AGENT"
        
    def get_your_feedback(self) -> List[Dict]:
        """Pull YOUR feedback from Supabase"""
        supabase = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
        # Get YOUR corrections and scores
        feedback = supabase.table('agent_feedback').select('*').execute()
        
        training_data = []
        for entry in feedback.data:
            # Only use entries YOU corrected/scored highly
            if entry.get('score', 0) > 0.7 or entry.get('corrections'):
                training_data.append({
                    "input": entry['prompt'],
                    "output": entry['corrections'] or entry['response'],
                    "score": entry['score']
                })
        
        return training_data
    
    def train_your_agent(self):
        """
        This trains the actual neural network weights based on YOUR feedback
        Not just prompting - actual weight updates
        """
        
        print("🧠 Training YOUR custom agent model...")
        
        # Load base model
        model = AutoModelForCausalLM.from_pretrained(
            self.base_model,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        
        tokenizer = AutoTokenizer.from_pretrained(self.base_model)
        
        # LoRA config - this determines which weights to update
        peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,  # Rank - higher = more parameters = better but slower
            lora_alpha=32,
            lora_dropout=0.1,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]  # Attention weights
        )
        
        model = get_peft_model(model, peft_config)
        
        # Get YOUR training data
        your_data = self.get_your_feedback()
        
        # Train on YOUR examples
        optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4)
        
        for epoch in range(3):  # 3 passes through your data
            for example in your_data:
                # Tokenize
                inputs = tokenizer(
                    f"Human: {example['input']}\n\nAssistant: {example['output']}",
                    return_tensors="pt",
                    truncation=True,
                    max_length=2048
                )
                
                # Forward pass
                outputs = model(**inputs, labels=inputs["input_ids"])
                loss = outputs.loss
                
                # YOUR feedback influences the loss
                # Higher scores = lower loss = model learns this is good
                weighted_loss = loss * (2 - example['score'])
                
                # Backprop - THIS UPDATES THE WEIGHTS
                weighted_loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                
                print(f"Training on your example: loss={loss.item():.4f}")
        
        # Save YOUR custom weights
        model.save_pretrained(self.model_weights_path)
        tokenizer.save_pretrained(self.model_weights_path)
        
        print(f"✅ YOUR agent weights saved to {self.model_weights_path}")
        
    def run_your_agent(self, prompt: str) -> str:
        """
        Run YOUR custom agent with YOUR weights
        """
        from peft import PeftModel
        
        # Load YOUR trained weights
        base = AutoModelForCausalLM.from_pretrained(self.base_model)
        model = PeftModel.from_pretrained(base, self.model_weights_path)
        tokenizer = AutoTokenizer.from_pretrained(self.model_weights_path)
        
        # Generate using YOUR learned behavior
        inputs = tokenizer(f"Human: {prompt}\n\nAssistant:", return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=1000,
            temperature=0.7,
            do_sample=True
        )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.split("Assistant:")[-1].strip()


# The actual deployment
class DeployYourAgent:
    """
    Replace Claude with YOUR custom model
    """
    
    def __init__(self):
        self.custom_model_path = "models/MY_CUSTOM_AGENT"
        self.model = None
        self.tokenizer = None
        
    def load_your_model(self):
        """Load YOUR weights"""
        from peft import PeftModel
        
        base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2-1.5B")
        self.model = PeftModel.from_pretrained(base, self.custom_model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(self.custom_model_path)
        
    async def generate(self, prompt: str) -> str:
        """
        This replaces Claude API calls with YOUR model
        """
        if not self.model:
            self.load_your_model()
        
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(**inputs, max_new_tokens=1500)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    """
    Train and deploy YOUR agent
    """
    trainer = CustomAgentTrainer()
    
    # Step 1: Train on YOUR feedback
    print("Training on YOUR feedback to create YOUR agent...")
    trainer.train_your_agent()
    
    # Step 2: Test YOUR agent
    print("\nTesting YOUR custom agent:")
    response = trainer.run_your_agent("Analyze @Ramp's unit economics")
    print(f"Your agent says: {response}")
    
    print("\n🎯 Your custom weights are ready!")
    print("These weights encode YOUR decision-making")
    print("Deploy with: python deploy_custom_agent.py")

if __name__ == "__main__":
    main()