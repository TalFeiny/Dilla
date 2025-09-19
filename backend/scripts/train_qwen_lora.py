"""
Fine-tune Qwen model using LoRA (Low-Rank Adaptation)
Optimized for Mac M1/M2 or small GPUs
"""

import os
import json
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    prepare_model_for_kbit_training
)
from datasets import Dataset
import numpy as np
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QwenLoRATrainer:
    """
    Fine-tune Qwen using LoRA for efficient training on consumer hardware
    """
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2-1.5B",  # Small model for local training
        output_dir: str = "models/fine-tuned/qwen-vc-analyst",
        use_mlx: bool = False  # Set True for Mac optimization
    ):
        self.model_name = model_name
        self.output_dir = output_dir
        self.use_mlx = use_mlx
        
        # Check if MPS (Mac GPU) is available
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
    def load_training_data(self, data_path: str = "data/training/feedback.jsonl") -> Dataset:
        """Load and prepare training data"""
        logger.info(f"Loading training data from {data_path}")
        
        examples = []
        with open(data_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                # Format as instruction-following
                text = f"""### Instruction:
{data.get('instruction', 'Analyze the following request:')}

### Input:
{data['input']}

### Response:
{data['output']}"""
                examples.append({"text": text})
        
        dataset = Dataset.from_list(examples)
        logger.info(f"Loaded {len(dataset)} training examples")
        return dataset
    
    def prepare_model_and_tokenizer(self):
        """Load model with LoRA configuration"""
        logger.info(f"Loading model: {self.model_name}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Load model in 8-bit for memory efficiency
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_8bit=False,  # Set True if you have bitsandbytes
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
            device_map="auto" if self.device != "cpu" else None
        )
        
        # Configure LoRA
        peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            inference_mode=False,
            r=8,  # Low rank - smaller = less parameters to train
            lora_alpha=32,  # LoRA scaling parameter
            lora_dropout=0.1,
            target_modules=[
                "q_proj", "v_proj", "k_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj"
            ]  # Which layers to apply LoRA to
        )
        
        # Apply LoRA
        self.model = get_peft_model(self.model, peft_config)
        self.model.print_trainable_parameters()
        
        return self.model, self.tokenizer
    
    def tokenize_function(self, examples):
        """Tokenize examples for training"""
        return self.tokenizer(
            examples["text"],
            truncation=True,
            padding=True,
            max_length=1024,  # Reduced for memory
            return_tensors="pt"
        )
    
    def train(self, num_epochs: int = 3):
        """Run the training loop"""
        # Load data
        dataset = self.load_training_data()
        
        # Prepare model
        model, tokenizer = self.prepare_model_and_tokenizer()
        
        # Tokenize dataset
        tokenized_dataset = dataset.map(self.tokenize_function, batched=True)
        
        # Training arguments optimized for small hardware
        training_args = TrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=1,  # Small batch for memory
            gradient_accumulation_steps=4,  # Accumulate gradients
            gradient_checkpointing=True,  # Save memory
            warmup_steps=100,
            logging_steps=10,
            save_steps=500,
            save_total_limit=2,
            learning_rate=2e-4,
            fp16=self.device != "cpu",  # Mixed precision if GPU
            optim="adamw_torch",
            report_to=["tensorboard"],
            push_to_hub=False,
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=tokenizer,
            mlm=False
        )
        
        # Create trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_dataset,
            data_collator=data_collator,
        )
        
        # Train!
        logger.info("🚀 Starting training...")
        trainer.train()
        
        # Save the model
        logger.info(f"💾 Saving model to {self.output_dir}")
        trainer.model.save_pretrained(self.output_dir)
        tokenizer.save_pretrained(self.output_dir)
        
        logger.info("✅ Training complete!")
        
    def inference_test(self, prompt: str):
        """Test the fine-tuned model"""
        from peft import PeftModel
        
        # Load fine-tuned model
        base_model = AutoModelForCausalLM.from_pretrained(self.model_name)
        model = PeftModel.from_pretrained(base_model, self.output_dir)
        tokenizer = AutoTokenizer.from_pretrained(self.output_dir)
        
        # Format prompt
        formatted_prompt = f"""### Instruction:
Provide VC investment analysis

### Input:
{prompt}

### Response:
"""
        
        # Generate
        inputs = tokenizer(formatted_prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=500,
                temperature=0.7,
                do_sample=True,
                top_p=0.9
            )
        
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response.split("### Response:")[-1].strip()


def main():
    """Main training pipeline"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2-1.5B", help="Base model")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--test", action="store_true", help="Run inference test after training")
    args = parser.parse_args()
    
    # Initialize trainer
    trainer = QwenLoRATrainer(model_name=args.model)
    
    # Check if training data exists
    if not os.path.exists("data/training/feedback.jsonl"):
        logger.warning("Training data not found. Run export_feedback.py first!")
        logger.info("Creating sample data for testing...")
        os.makedirs("data/training", exist_ok=True)
        
        # Create minimal sample
        sample = {
            "instruction": "Analyze this startup",
            "input": "Analyze @Ramp",
            "output": "Ramp is a high-growth fintech with $300M ARR, 150% YoY growth, and strong unit economics."
        }
        with open("data/training/feedback.jsonl", "w") as f:
            f.write(json.dumps(sample) + "\n")
    
    # Train
    trainer.train(num_epochs=args.epochs)
    
    # Test
    if args.test:
        logger.info("\n🧪 Testing fine-tuned model...")
        test_prompt = "Compare @Stripe and @Square for investment"
        response = trainer.inference_test(test_prompt)
        print(f"\nPrompt: {test_prompt}")
        print(f"Response: {response}")

if __name__ == "__main__":
    main()