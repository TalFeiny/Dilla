#!/usr/bin/env python3
"""
GRPO Training with NumPy - Ultra Lightweight!
No PyTorch/TensorFlow needed - just NumPy
"""

import numpy as np
import json
import os
from typing import List, Dict, Tuple
from supabase import create_client
from datetime import datetime
import pickle

class NumpyGRPO:
    """
    Group Relative Policy Optimization using only NumPy
    Super lightweight - works on any machine!
    """
    
    def __init__(self, embedding_dim=512, learning_rate=0.01):
        self.embedding_dim = embedding_dim
        self.learning_rate = learning_rate
        
        # Initialize weight matrices with NumPy
        self.W_prompt = np.random.randn(embedding_dim, embedding_dim) * 0.01
        self.W_response = np.random.randn(embedding_dim, embedding_dim) * 0.01
        self.W_preference = np.random.randn(embedding_dim, 1) * 0.01
        
        # Supabase connection
        self.supabase = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        
        # Cache for embeddings
        self.embedding_cache = {}
    
    def text_to_embedding(self, text: str) -> np.ndarray:
        """
        Convert text to embedding using simple hashing
        No model needed - just hash functions!
        """
        if text in self.embedding_cache:
            return self.embedding_cache[text]
        
        # Simple but effective: hash words to create embedding
        words = text.lower().split()
        embedding = np.zeros(self.embedding_dim)
        
        for word in words:
            # Hash word to multiple dimensions
            for i in range(5):  # 5 hash functions
                hash_val = hash(word + str(i))
                idx = abs(hash_val) % self.embedding_dim
                # Use different hash for value
                val_hash = hash(word + "_val_" + str(i))
                embedding[idx] += np.sign(val_hash) * (1.0 / np.sqrt(len(words)))
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        self.embedding_cache[text] = embedding
        return embedding
    
    def compute_preference_score(self, prompt: str, response: str) -> float:
        """
        Compute preference score using learned weights
        """
        # Get embeddings
        prompt_emb = self.text_to_embedding(prompt)
        response_emb = self.text_to_embedding(response)
        
        # Neural network forward pass (all NumPy!)
        # Layer 1: Process prompt
        h1 = np.tanh(prompt_emb @ self.W_prompt)
        
        # Layer 2: Process response
        h2 = np.tanh(response_emb @ self.W_response)
        
        # Combine features
        combined = h1 * h2  # Element-wise multiplication
        
        # Output layer: preference score
        score = np.sigmoid(combined @ self.W_preference)
        
        return float(score[0])
    
    def grpo_loss(self, prompt: str, chosen: str, rejected: str, margin: float = 1.0) -> float:
        """
        GRPO loss: chosen should score higher than rejected by margin
        """
        score_chosen = self.compute_preference_score(prompt, chosen)
        score_rejected = self.compute_preference_score(prompt, rejected)
        
        # Hinge loss: max(0, margin - (score_chosen - score_rejected))
        loss = max(0, margin - (score_chosen - score_rejected))
        
        return loss, score_chosen, score_rejected
    
    def update_weights(self, prompt: str, chosen: str, rejected: str, margin: float = 1.0):
        """
        Update weights using gradient descent (NumPy only!)
        """
        # Compute gradients numerically (finite differences)
        epsilon = 1e-4
        
        # Get current loss
        loss, score_c, score_r = self.grpo_loss(prompt, chosen, rejected, margin)
        
        if loss == 0:
            return  # Already correct ranking
        
        # Update each weight matrix
        for W in [self.W_prompt, self.W_response, self.W_preference]:
            grad = np.zeros_like(W)
            
            # Compute gradient for each weight
            it = np.nditer(W, flags=['multi_index'])
            while not it.finished:
                idx = it.multi_index
                
                # Perturb weight
                old_val = W[idx]
                W[idx] = old_val + epsilon
                loss_plus, _, _ = self.grpo_loss(prompt, chosen, rejected, margin)
                
                W[idx] = old_val - epsilon
                loss_minus, _, _ = self.grpo_loss(prompt, chosen, rejected, margin)
                
                # Gradient
                grad[idx] = (loss_plus - loss_minus) / (2 * epsilon)
                
                # Restore
                W[idx] = old_val
                it.iternext()
            
            # Update weights
            W -= self.learning_rate * grad
    
    def train_grpo(self, num_epochs: int = 10):
        """
        Train GRPO using NumPy
        """
        print("🚀 Starting NumPy GRPO Training")
        print("=" * 50)
        
        # Get feedback from Supabase
        result = self.supabase.table('agent_feedback').select('*').execute()
        feedback = result.data if result.data else []
        
        if len(feedback) < 2:
            print("❌ Need at least 2 feedback entries")
            return
        
        # Create preference pairs
        pairs = []
        prompts = {}
        
        # Group by prompt
        for entry in feedback:
            prompt = entry.get('prompt', '')
            if prompt:
                if prompt not in prompts:
                    prompts[prompt] = []
                prompts[prompt].append(entry)
        
        # Create pairs from different scores
        for prompt, entries in prompts.items():
            entries.sort(key=lambda x: x.get('score', 0))
            
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    score_diff = entries[j].get('score', 0) - entries[i].get('score', 0)
                    if score_diff > 0.1:
                        chosen = entries[j].get('corrections') or entries[j].get('response', '')
                        rejected = entries[i].get('corrections') or entries[i].get('response', '')
                        
                        if chosen and rejected and chosen != rejected:
                            pairs.append({
                                'prompt': prompt,
                                'chosen': chosen,
                                'rejected': rejected,
                                'margin': min(2.0, score_diff * 2)  # Scale margin by score difference
                            })
        
        print(f"📊 Training on {len(pairs)} preference pairs")
        
        if len(pairs) == 0:
            print("❌ No valid preference pairs found")
            return
        
        # Training loop
        for epoch in range(num_epochs):
            total_loss = 0
            correct = 0
            
            # Shuffle pairs
            np.random.shuffle(pairs)
            
            for pair in pairs:
                # Update weights
                self.update_weights(
                    pair['prompt'],
                    pair['chosen'],
                    pair['rejected'],
                    pair['margin']
                )
                
                # Check if ranking is correct
                loss, score_c, score_r = self.grpo_loss(
                    pair['prompt'],
                    pair['chosen'],
                    pair['rejected'],
                    pair['margin']
                )
                
                total_loss += loss
                if score_c > score_r:
                    correct += 1
            
            accuracy = correct / len(pairs) * 100
            avg_loss = total_loss / len(pairs)
            
            print(f"Epoch {epoch+1}/{num_epochs} - Loss: {avg_loss:.4f}, Accuracy: {accuracy:.1f}%")
        
        # Save model
        self.save_model()
        
        print("\n✅ GRPO Training Complete!")
        print("Model saved to models/grpo_numpy.pkl")
    
    def save_model(self, path: str = "models/grpo_numpy.pkl"):
        """Save the NumPy GRPO model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        model_data = {
            'W_prompt': self.W_prompt,
            'W_response': self.W_response,
            'W_preference': self.W_preference,
            'embedding_dim': self.embedding_dim,
            'embedding_cache': self.embedding_cache,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"💾 Model saved to {path}")
    
    def load_model(self, path: str = "models/grpo_numpy.pkl"):
        """Load a trained NumPy GRPO model"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.W_prompt = model_data['W_prompt']
        self.W_response = model_data['W_response']
        self.W_preference = model_data['W_preference']
        self.embedding_dim = model_data['embedding_dim']
        self.embedding_cache = model_data.get('embedding_cache', {})
        
        print(f"📦 Model loaded from {path}")
    
    def rank_responses(self, prompt: str, responses: List[str]) -> List[Tuple[str, float]]:
        """
        Rank multiple responses using GRPO scores
        """
        scored = []
        for response in responses:
            score = self.compute_preference_score(prompt, response)
            scored.append((response, score))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored
    
    def test_model(self):
        """Test the GRPO model"""
        print("\n🧪 Testing NumPy GRPO Model")
        print("-" * 40)
        
        test_cases = [
            {
                'prompt': 'Create DCF model for @Ramp',
                'responses': [
                    'Simple DCF with 10% discount rate',
                    'Detailed DCF with scenario analysis and 15% WACC',
                    'Basic valuation using revenue multiples'
                ]
            },
            {
                'prompt': 'Compare @Deel and @Brex',
                'responses': [
                    'Deel is better',
                    'Comprehensive analysis: Deel has 85% gross margins vs Brex 70%, faster growth',
                    'Both are good companies'
                ]
            }
        ]
        
        for test in test_cases:
            print(f"\n📝 Prompt: {test['prompt']}")
            rankings = self.rank_responses(test['prompt'], test['responses'])
            
            print("Rankings (best to worst):")
            for i, (response, score) in enumerate(rankings, 1):
                print(f"{i}. [{score:.3f}] {response[:60]}...")


def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║     NUMPY GRPO TRAINING               ║
    ║   Ultra Lightweight - No GPU Needed!  ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Initialize GRPO
    grpo = NumpyGRPO(
        embedding_dim=256,  # Smaller for efficiency
        learning_rate=0.01
    )
    
    # Train
    grpo.train_grpo(num_epochs=20)
    
    # Test
    grpo.test_model()
    
    print("\n🎉 NumPy GRPO Complete!")
    print("This model can rank responses based on your preferences")
    print("Use it to filter/rerank any LLM output!")


if __name__ == "__main__":
    main()