"""
Numpy-based Deep RL Agent for Financial Modeling
Pure Python implementation without TensorFlow/PyTorch dependencies
"""

import numpy as np
import json
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from collections import deque
import pickle
from pathlib import Path

@dataclass
class SpreadsheetState:
    """Represents the current state of a spreadsheet"""
    grid_values: np.ndarray
    grid_formulas: np.ndarray
    cell_types: np.ndarray
    cell_formats: np.ndarray
    metadata: Dict[str, Any]

class NeuralNetwork:
    """Simple feedforward neural network using only NumPy"""
    
    def __init__(self, input_size, hidden_sizes, output_size, learning_rate=0.001):
        self.layers = []
        self.learning_rate = learning_rate
        
        # Initialize weights and biases
        sizes = [input_size] + hidden_sizes + [output_size]
        for i in range(len(sizes) - 1):
            # He initialization
            w = np.random.randn(sizes[i], sizes[i+1]) * np.sqrt(2.0 / sizes[i])
            b = np.zeros((1, sizes[i+1]))
            self.layers.append({'W': w, 'b': b})
    
    def relu(self, x):
        return np.maximum(0, x)
    
    def relu_derivative(self, x):
        return (x > 0).astype(float)
    
    def softmax(self, x):
        exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=1, keepdims=True)
    
    def forward(self, X):
        """Forward pass through the network"""
        self.activations = [X]
        current = X
        
        for i, layer in enumerate(self.layers):
            z = np.dot(current, layer['W']) + layer['b']
            if i < len(self.layers) - 1:
                current = self.relu(z)
            else:
                current = self.softmax(z)
            self.activations.append(current)
        
        return current
    
    def backward(self, X, y, output):
        """Backpropagation"""
        m = X.shape[0]
        gradients = []
        
        # Output layer gradient
        delta = output - y
        
        for i in reversed(range(len(self.layers))):
            gradients.append({
                'dW': np.dot(self.activations[i].T, delta) / m,
                'db': np.sum(delta, axis=0, keepdims=True) / m
            })
            
            if i > 0:
                delta = np.dot(delta, self.layers[i]['W'].T)
                delta *= self.relu_derivative(self.activations[i])
        
        gradients.reverse()
        
        # Update weights
        for i, (layer, grad) in enumerate(zip(self.layers, gradients)):
            layer['W'] -= self.learning_rate * grad['dW']
            layer['b'] -= self.learning_rate * grad['db']
    
    def train_step(self, X, y):
        """Single training step"""
        output = self.forward(X)
        self.backward(X, y, output)
        
        # Calculate loss
        epsilon = 1e-7
        loss = -np.mean(np.sum(y * np.log(output + epsilon), axis=1))
        return loss
    
    def predict(self, X):
        """Get predictions"""
        return self.forward(X)
    
    def save(self, path):
        """Save model weights"""
        with open(path, 'wb') as f:
            pickle.dump(self.layers, f)
    
    def load(self, path):
        """Load model weights"""
        if Path(path).exists():
            with open(path, 'rb') as f:
                self.layers = pickle.load(f)

class SpreadsheetEncoder:
    """Encodes spreadsheet state into feature vectors"""
    
    def __init__(self, max_rows=50, max_cols=20):
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.feature_dim = 256
    
    def encode(self, state: SpreadsheetState) -> np.ndarray:
        """Convert spreadsheet state to feature vector"""
        # Flatten grid representations
        values_flat = state.grid_values[:self.max_rows, :self.max_cols].flatten()
        formulas_flat = state.grid_formulas[:self.max_rows, :self.max_cols].flatten()
        types_flat = state.cell_types[:self.max_rows, :self.max_cols].flatten()
        
        # Normalize
        values_norm = (values_flat - np.mean(values_flat)) / (np.std(values_flat) + 1e-8)
        formulas_norm = formulas_flat / 1000.0  # Simple normalization
        types_norm = types_flat / 4.0  # Assuming 4 cell types
        
        # Concatenate all features
        features = np.concatenate([values_norm, formulas_norm, types_norm])
        
        # Reduce to fixed size using simple pooling
        if len(features) > self.feature_dim:
            # Average pooling to reduce dimension
            pool_size = len(features) // self.feature_dim
            pooled = []
            for i in range(self.feature_dim):
                start = i * pool_size
                end = min(start + pool_size, len(features))
                pooled.append(np.mean(features[start:end]))
            features = np.array(pooled)
        else:
            # Pad if necessary
            features = np.pad(features, (0, self.feature_dim - len(features)))
        
        return features

class PPOAgent:
    """Proximal Policy Optimization agent using NumPy"""
    
    def __init__(self, state_dim=256, action_dim=50, lr=0.0003):
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Policy network
        self.policy_net = NeuralNetwork(
            state_dim, [128, 64], action_dim, lr
        )
        
        # Value network
        self.value_net = NeuralNetwork(
            state_dim, [128, 64], 1, lr
        )
        
        # PPO hyperparameters
        self.gamma = 0.99
        self.lam = 0.95
        self.clip_ratio = 0.2
        self.entropy_coef = 0.01
        
        # Experience buffer
        self.buffer = ExperienceBuffer(capacity=5000)
        
        # Model paths
        self.model_dir = Path(__file__).parent / 'models'
        self.model_dir.mkdir(exist_ok=True)
        
        # Load existing models if available
        self.load_checkpoint()
    
    def select_action(self, state: np.ndarray, explore=True):
        """Select action using current policy"""
        # Get action probabilities
        state_batch = state.reshape(1, -1)
        action_probs = self.policy_net.predict(state_batch)[0]
        
        if explore:
            # Sample from distribution
            action = np.random.choice(self.action_dim, p=action_probs)
        else:
            # Greedy
            action = np.argmax(action_probs)
        
        # Map to spreadsheet action
        row = action // 20
        col = action % 20
        
        return {
            'action_type': action,
            'row': int(row),
            'col': int(col),
            'log_prob': np.log(action_probs[action] + 1e-8)
        }
    
    def compute_advantages(self, rewards, values, dones):
        """GAE (Generalized Advantage Estimation)"""
        advantages = np.zeros_like(rewards)
        last_advantage = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            last_advantage = delta + self.gamma * self.lam * (1 - dones[t]) * last_advantage
            advantages[t] = last_advantage
        
        return advantages
    
    def train(self, batch_size=32, epochs=4):
        """Train the agent on collected experience"""
        if len(self.buffer.buffer) < batch_size:
            return None
        
        # Sample batch
        batch = self.buffer.sample(batch_size)
        
        # Prepare data
        states = np.array([exp['state'] for exp in batch])
        actions = np.array([exp['action']['action_type'] for exp in batch])
        rewards = np.array([exp['reward'] for exp in batch])
        next_states = np.array([exp['next_state'] for exp in batch])
        dones = np.array([exp['done'] for exp in batch])
        
        # Get values
        values = self.value_net.predict(states).squeeze()
        
        # Compute advantages
        advantages = self.compute_advantages(rewards, values, dones)
        
        # Normalize advantages
        advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)
        
        # Convert actions to one-hot
        actions_onehot = np.zeros((len(actions), self.action_dim))
        actions_onehot[np.arange(len(actions)), actions] = 1
        
        # Training loop
        total_loss = 0
        for epoch in range(epochs):
            # Train policy network
            policy_loss = self.policy_net.train_step(states, actions_onehot)
            
            # Train value network
            value_targets = rewards + self.gamma * values  # Simple TD target
            value_targets = value_targets.reshape(-1, 1)
            value_loss = self.value_net.train_step(states, value_targets)
            
            total_loss += policy_loss + value_loss
        
        return total_loss / epochs
    
    def save_checkpoint(self, episode=None):
        """Save model checkpoint"""
        suffix = f'_{episode}' if episode else ''
        self.policy_net.save(self.model_dir / f'policy{suffix}.pkl')
        self.value_net.save(self.model_dir / f'value{suffix}.pkl')
    
    def load_checkpoint(self):
        """Load latest checkpoint"""
        policy_path = self.model_dir / 'policy.pkl'
        value_path = self.model_dir / 'value.pkl'
        
        self.policy_net.load(policy_path)
        self.value_net.load(value_path)

class ExperienceBuffer:
    """Experience replay buffer"""
    
    def __init__(self, capacity=5000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
    
    def add(self, state, action, reward, next_state, done, info=None):
        """Add experience"""
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done,
            'info': info or {}
        }
        
        self.buffer.append(experience)
        self.priorities.append(abs(reward) + 0.01)
    
    def sample(self, batch_size=32):
        """Sample batch"""
        if len(self.buffer) < batch_size:
            return list(self.buffer)
        
        # Prioritized sampling
        probs = np.array(self.priorities) / sum(self.priorities)
        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        
        return [self.buffer[i] for i in indices]
    
    def get_stats(self):
        """Get buffer statistics"""
        if not self.buffer:
            return {'size': 0}
        
        rewards = [exp['reward'] for exp in self.buffer]
        return {
            'size': len(self.buffer),
            'avg_reward': np.mean(rewards),
            'max_reward': np.max(rewards),
            'min_reward': np.min(rewards)
        }

class RewardShaper:
    """Multi-factor reward calculation"""
    
    def calculate_reward(self, state_before, state_after, action, user_feedback=None):
        """Calculate shaped reward"""
        base_reward = 0.1  # Small positive for any action
        
        # Check if action changed the grid
        if np.array_equal(state_before.grid_values, state_after.grid_values):
            base_reward -= 0.5  # Penalize no-op actions
        
        # Reward filling empty cells
        empty_before = np.sum(state_before.grid_values == 0)
        empty_after = np.sum(state_after.grid_values == 0)
        if empty_after < empty_before:
            base_reward += 0.3
        
        # Apply user feedback multiplier
        if user_feedback:
            multipliers = {
                'perfect': 2.0,
                'good': 1.5,
                'okay': 1.0,
                'poor': 0.5,
                'wrong': -1.0
            }
            base_reward *= multipliers.get(user_feedback, 1.0)
        
        return base_reward

# Main inference server
class RLInferenceServer:
    def __init__(self):
        self.encoder = SpreadsheetEncoder()
        self.agent = PPOAgent()
        self.reward_shaper = RewardShaper()
        self.training_steps = 0
    
    def predict(self, state_dict):
        """Get next action"""
        state = self._dict_to_state(state_dict)
        state_encoded = self.encoder.encode(state)
        action = self.agent.select_action(state_encoded)
        
        return {
            'action': self._decode_action(action),
            'confidence': float(np.exp(action.get('log_prob', 0))),
            'exploration_rate': 0.1
        }
    
    def train_online(self, experience_dict):
        """Add experience and train"""
        state = self._dict_to_state(experience_dict['state'])
        next_state = self._dict_to_state(experience_dict['next_state'])
        
        state_encoded = self.encoder.encode(state)
        next_state_encoded = self.encoder.encode(next_state)
        
        reward = self.reward_shaper.calculate_reward(
            state, next_state,
            experience_dict['action'],
            experience_dict.get('user_feedback')
        )
        
        self.agent.buffer.add(
            state_encoded,
            experience_dict['action'],
            reward,
            next_state_encoded,
            experience_dict['done']
        )
        
        # Train if enough experience
        loss = None
        if len(self.agent.buffer.buffer) >= 32:
            loss = self.agent.train()
            self.training_steps += 1
            
            # Save periodically
            if self.training_steps % 100 == 0:
                self.agent.save_checkpoint()
        
        return {
            'buffer_size': len(self.agent.buffer.buffer),
            'reward': reward,
            'training_steps': self.training_steps,
            'loss': loss
        }
    
    def get_status(self):
        """Get training status"""
        return {
            'training_steps': self.training_steps,
            'buffer_stats': self.agent.buffer.get_stats(),
            'ready': len(self.agent.buffer.buffer) > 0
        }
    
    def _dict_to_state(self, state_dict):
        """Convert dict to SpreadsheetState"""
        grid = state_dict.get('grid', [])
        max_rows, max_cols = 50, 20
        
        grid_values = np.zeros((max_rows, max_cols))
        grid_formulas = np.zeros((max_rows, max_cols))
        cell_types = np.zeros((max_rows, max_cols))
        cell_formats = np.zeros((max_rows, max_cols))
        
        for i, row in enumerate(grid[:max_rows]):
            for j, cell in enumerate(row[:max_cols]):
                if cell:
                    if isinstance(cell, dict):
                        grid_values[i, j] = cell.get('value', 0)
                    elif isinstance(cell, (int, float)):
                        grid_values[i, j] = float(cell)
        
        return SpreadsheetState(
            grid_values=grid_values,
            grid_formulas=grid_formulas,
            cell_types=cell_types,
            cell_formats=cell_formats,
            metadata=state_dict.get('metadata', {})
        )
    
    def _decode_action(self, action):
        """Convert action to executable format"""
        return {
            'type': 'set_value',
            'row': action['row'],
            'col': action['col'],
            'value': 0
        }

def main():
    """CLI interface"""
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'No command provided'}))
        sys.exit(1)
    
    command = sys.argv[1]
    server = RLInferenceServer()
    
    try:
        if command == 'predict':
            state = json.loads(sys.argv[2])
            result = server.predict(state)
            print(json.dumps(result))
            
        elif command == 'train':
            experience = json.loads(sys.argv[2])
            result = server.train_online(experience)
            print(json.dumps(result))
            
        elif command == 'status':
            result = server.get_status()
            print(json.dumps(result))
            
        else:
            print(json.dumps({'error': f'Unknown command: {command}'}))
            
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()