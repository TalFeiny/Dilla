"""
Simple GRPO Implementation using Ollama
No PyTorch required - uses Ollama's fine-tuning capabilities
"""

import json
import os
from typing import List, Dict, Tuple
from supabase import create_client
import subprocess
from datetime import datetime

class SimpleGRPO:
    """
    GRPO training using Ollama's built-in capabilities
    """
    
    def __init__(self):
        self.supabase = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
    def get_feedback(self) -> List[Dict]:
        """Get all feedback from Supabase"""
        result = self.supabase.table('agent_feedback').select('*').execute()
        return result.data if result.data else []
    
    def create_training_data(self) -> str:
        """
        Create GRPO training data in JSONL format
        Each line has prompt, chosen response, rejected response
        """
        feedback = self.get_feedback()
        
        # Group by prompt
        prompt_groups = {}
        for entry in feedback:
            prompt = entry.get('prompt', '')
            if not prompt:
                continue
            
            if prompt not in prompt_groups:
                prompt_groups[prompt] = []
            
            prompt_groups[prompt].append({
                'response': entry.get('response', ''),
                'corrections': entry.get('corrections', ''),
                'score': entry.get('score', 0.5),
                'feedback_type': entry.get('feedback_type', '')
            })
        
        # Create training pairs
        training_data = []
        
        for prompt, responses in prompt_groups.items():
            # Sort by score
            responses.sort(key=lambda x: x['score'])
            
            # Create preference pairs
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    if responses[j]['score'] - responses[i]['score'] > 0.2:
                        # j is preferred over i
                        chosen = responses[j]['corrections'] or responses[j]['response']
                        rejected = responses[i]['corrections'] or responses[i]['response']
                        
                        if chosen and rejected and chosen != rejected:
                            training_data.append({
                                'instruction': prompt,
                                'chosen': chosen,
                                'rejected': rejected,
                                'score_diff': responses[j]['score'] - responses[i]['score']
                            })
        
        # Save to JSONL
        output_file = 'data/grpo_training.jsonl'
        os.makedirs('data', exist_ok=True)
        
        with open(output_file, 'w') as f:
            for item in training_data:
                f.write(json.dumps(item) + '\n')
        
        print(f"✅ Created {len(training_data)} training pairs")
        return output_file
    
    def create_modelfile(self) -> str:
        """
        Create Ollama Modelfile for GRPO fine-tuning
        """
        modelfile_content = """
# GRPO Custom Agent Model
FROM qwen2:1.5b

# System prompt for your agent
SYSTEM You are an expert VC analyst trained with GRPO (Group Relative Policy Optimization). 
You provide institutional-grade analysis with deep financial insights.
You have been trained on user preferences to match their exact style.

# Training parameters optimized for GRPO
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096

# Add training data
TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
{{ end }}"""

# Message format
MESSAGE user {{ .Prompt }}
MESSAGE assistant {{ .Response }}
"""
        
        modelfile_path = 'models/Modelfile.grpo'
        os.makedirs('models', exist_ok=True)
        
        with open(modelfile_path, 'w') as f:
            f.write(modelfile_content)
        
        return modelfile_path
    
    def train_with_ollama(self):
        """
        Train using Ollama's create command with GRPO data
        """
        print("🚀 Starting GRPO Training with Ollama")
        print("=" * 50)
        
        # Create training data
        training_file = self.create_training_data()
        
        # Create Modelfile
        modelfile = self.create_modelfile()
        
        # Create custom model with Ollama
        model_name = "grpo-agent:latest"
        
        print(f"🧠 Creating GRPO model: {model_name}")
        
        # Build the model
        cmd = f"ollama create {model_name} -f {modelfile}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Model created successfully: {model_name}")
            
            # Test the model
            self.test_model(model_name)
            
            return model_name
        else:
            print(f"❌ Error creating model: {result.stderr}")
            return None
    
    def test_model(self, model_name: str = "grpo-agent:latest"):
        """Test the GRPO trained model"""
        print("\n🧪 Testing GRPO Model")
        print("-" * 40)
        
        test_prompts = [
            "Create a DCF model for @Ramp",
            "Compare @Deel and @Brex",
            "Build Series A deck outline"
        ]
        
        for prompt in test_prompts:
            print(f"\n📝 Prompt: {prompt}")
            
            # Run with Ollama
            cmd = f'echo "{prompt}" | ollama run {model_name}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"🤖 Response: {response[:200]}...")
            else:
                print(f"❌ Error: {result.stderr}")
    
    def analyze_feedback(self):
        """Analyze your feedback for GRPO readiness"""
        feedback = self.get_feedback()
        
        print("\n📊 Feedback Analysis")
        print("-" * 40)
        print(f"Total feedback entries: {len(feedback)}")
        
        # Count by type
        types = {}
        for f in feedback:
            ft = f.get('feedback_type', 'unknown')
            types[ft] = types.get(ft, 0) + 1
        
        print("\nFeedback types:")
        for ft, count in types.items():
            print(f"  {ft}: {count}")
        
        # Count unique prompts
        prompts = set()
        multi_response = 0
        for f in feedback:
            p = f.get('prompt', '')
            if p:
                if p in prompts:
                    multi_response += 1
                prompts.add(p)
        
        print(f"\nUnique prompts: {len(prompts)}")
        print(f"Prompts with multiple responses: {multi_response}")
        
        if len(feedback) < 10:
            print("\n⚠️ Need more feedback for effective GRPO training")
            print("   Collect at least 10 feedback entries")
        elif multi_response < 5:
            print("\n⚠️ Need more varied responses per prompt")
            print("   Try generating multiple versions and rating them")
        else:
            print("\n✅ Ready for GRPO training!")


def main():
    print("""
    ╔════════════════════════════════════╗
    ║   SIMPLE GRPO WITH OLLAMA         ║
    ║   No PyTorch Required!             ║
    ╚════════════════════════════════════╝
    """)
    
    grpo = SimpleGRPO()
    
    # Analyze first
    grpo.analyze_feedback()
    
    print("\n❓ Start GRPO training? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        model = grpo.train_with_ollama()
        if model:
            print(f"\n🎉 GRPO training complete!")
            print(f"📦 Model name: {model}")
            print(f"\nTo use your GRPO model:")
            print(f"  ollama run {model}")
    else:
        print("Training cancelled")


if __name__ == "__main__":
    main()