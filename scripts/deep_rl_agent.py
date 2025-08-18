"""
Deep Reinforcement Learning Agent for Financial Modeling
Uses PPO (Proximal Policy Optimization) for stable learning
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from typing import Dict, List, Tuple, Any
import json
from dataclasses import dataclass
from collections import deque
import random

@dataclass
class SpreadsheetState:
    """Represents the current state of a spreadsheet"""
    grid_values: np.ndarray  # Raw cell values
    grid_formulas: np.ndarray  # Formula encodings
    cell_types: np.ndarray  # Type of each cell (number, formula, text, empty)
    cell_formats: np.ndarray  # Formatting info
    metadata: Dict[str, Any]  # Company info, context
    
class SpreadsheetStateEncoder:
    """Encodes spreadsheet state into feature vectors"""
    
    def __init__(self, max_rows=50, max_cols=20):
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.feature_dim = 512
        
        # Build encoding network
        self.encoder = self._build_encoder()
        
    def _build_encoder(self):
        """CNN + Attention for grid understanding"""
        grid_input = keras.Input(shape=(self.max_rows, self.max_cols, 4))  # 4 channels
        
        # Convolutional layers to understand spatial patterns
        x = keras.layers.Conv2D(32, 3, padding='same', activation='relu')(grid_input)
        x = keras.layers.Conv2D(64, 3, padding='same', activation='relu')(x)
        x = keras.layers.MaxPooling2D(2)(x)
        x = keras.layers.Conv2D(128, 3, padding='same', activation='relu')(x)
        
        # Attention mechanism to focus on important cells
        attention = keras.layers.MultiHeadAttention(num_heads=4, key_dim=128)(x, x)
        x = keras.layers.Add()([x, attention])
        
        # Flatten and encode
        x = keras.layers.GlobalAveragePooling2D()(x)
        x = keras.layers.Dense(self.feature_dim, activation='relu')(x)
        state_encoding = keras.layers.LayerNormalization()(x)
        
        return keras.Model(inputs=grid_input, outputs=state_encoding)
    
    def encode(self, state: SpreadsheetState) -> np.ndarray:
        """Convert spreadsheet state to feature vector"""
        # Stack different representations as channels
        grid_tensor = np.stack([
            state.grid_values[:self.max_rows, :self.max_cols],
            state.grid_formulas[:self.max_rows, :self.max_cols],
            state.cell_types[:self.max_rows, :self.max_cols],
            state.cell_formats[:self.max_rows, :self.max_cols]
        ], axis=-1)
        
        # Normalize values
        grid_tensor = (grid_tensor - np.mean(grid_tensor)) / (np.std(grid_tensor) + 1e-8)
        
        return self.encoder(grid_tensor[np.newaxis, ...])[0]

class ActionSpace:
    """Defines possible actions the agent can take"""
    
    def __init__(self):
        self.actions = {
            # Cell operations
            'set_value': {'params': ['row', 'col', 'value']},
            'set_formula': {'params': ['row', 'col', 'formula_type', 'references']},
            'copy_cell': {'params': ['src_row', 'src_col', 'dst_row', 'dst_col']},
            'fill_down': {'params': ['row', 'col', 'num_rows']},
            'fill_right': {'params': ['row', 'col', 'num_cols']},
            
            # Formula templates
            'create_sum': {'params': ['target_row', 'target_col', 'range']},
            'create_growth': {'params': ['target_row', 'target_col', 'base_ref', 'rate']},
            'create_ratio': {'params': ['target_row', 'target_col', 'numerator', 'denominator']},
            'create_dcf': {'params': ['target_range', 'cashflows', 'discount_rate']},
            
            # Structure operations  
            'add_row': {'params': ['position', 'label']},
            'add_column': {'params': ['position', 'label']},
            'create_section': {'params': ['start_row', 'end_row', 'section_type']},
        }
        
        self.num_actions = len(self.actions)
        self.action_embedding_dim = 64
        
    def encode_action(self, action_name: str, params: Dict) -> np.ndarray:
        """Encode action and parameters into vector"""
        action_idx = list(self.actions.keys()).index(action_name)
        one_hot = np.zeros(self.num_actions)
        one_hot[action_idx] = 1
        
        # Encode parameters (simplified - would need proper encoding)
        param_vec = np.zeros(20)  # Fixed size param vector
        for i, (key, val) in enumerate(params.items()):
            if i < 20:
                param_vec[i] = hash(str(val)) % 1000 / 1000  # Normalize
                
        return np.concatenate([one_hot, param_vec])

class PPOAgent:
    """Proximal Policy Optimization agent for spreadsheet manipulation"""
    
    def __init__(self, state_dim=512, action_dim=100, lr=3e-4):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr
        
        # Hyperparameters
        self.gamma = 0.99
        self.lam = 0.95
        self.clip_ratio = 0.2
        self.entropy_coef = 0.01
        self.value_coef = 0.5
        
        # Build networks
        self.policy_network = self._build_policy_network()
        self.value_network = self._build_value_network()
        
        # Optimizers
        self.policy_optimizer = keras.optimizers.Adam(lr)
        self.value_optimizer = keras.optimizers.Adam(lr)
        
        # Experience buffer
        self.buffer = ExperienceBuffer(capacity=10000)
        
    def _build_policy_network(self):
        """Actor network - outputs action probabilities"""
        state_input = keras.Input(shape=(self.state_dim,))
        
        x = keras.layers.Dense(256, activation='relu')(state_input)
        x = keras.layers.LayerNormalization()(x)
        x = keras.layers.Dense(256, activation='relu')(x)
        x = keras.layers.Dropout(0.1)(x)
        
        # Multiple heads for different action types
        action_type = keras.layers.Dense(self.action_dim, activation='softmax', name='action_type')(x)
        cell_selection = keras.layers.Dense(1000, activation='softmax', name='cell_select')(x)  # 50x20 grid
        value_prediction = keras.layers.Dense(1, name='value_pred')(x)  # For continuous values
        
        return keras.Model(
            inputs=state_input,
            outputs=[action_type, cell_selection, value_prediction]
        )
    
    def _build_value_network(self):
        """Critic network - estimates state value"""
        state_input = keras.Input(shape=(self.state_dim,))
        
        x = keras.layers.Dense(256, activation='relu')(state_input)
        x = keras.layers.LayerNormalization()(x)
        x = keras.layers.Dense(128, activation='relu')(x)
        value = keras.layers.Dense(1)(x)
        
        return keras.Model(inputs=state_input, outputs=value)
    
    def select_action(self, state: np.ndarray, explore=True):
        """Select action using current policy"""
        action_probs, cell_probs, value_pred = self.policy_network(state[np.newaxis, ...])
        
        if explore:
            # Sample from distribution
            action_type = np.random.choice(self.action_dim, p=action_probs[0].numpy())
            cell_idx = np.random.choice(1000, p=cell_probs[0].numpy())
        else:
            # Greedy
            action_type = np.argmax(action_probs[0])
            cell_idx = np.argmax(cell_probs[0])
            
        # Convert to row/col
        row = cell_idx // 20
        col = cell_idx % 20
        
        return {
            'action_type': action_type,
            'row': row,
            'col': col,
            'value': value_pred[0, 0].numpy()
        }
    
    def compute_advantages(self, rewards, values, dones):
        """GAE (Generalized Advantage Estimation)"""
        advantages = np.zeros_like(rewards)
        last_advantage = 0
        
        for t in reversed(range(len(rewards))):
            if dones[t]:
                last_advantage = 0
            delta = rewards[t] + self.gamma * values[t + 1] * (1 - dones[t]) - values[t]
            last_advantage = delta + self.gamma * self.lam * (1 - dones[t]) * last_advantage
            advantages[t] = last_advantage
            
        return advantages
    
    @tf.function
    def train_step(self, states, actions, advantages, returns, old_log_probs):
        """Single PPO training step"""
        with tf.GradientTape() as tape:
            # Get current policy predictions
            action_probs, cell_probs, _ = self.policy_network(states)
            values = self.value_network(states)
            
            # Calculate log probabilities
            action_indices = tf.stack([tf.range(tf.shape(actions)[0]), actions], axis=1)
            log_probs = tf.nn.log_softmax(action_probs)
            selected_log_probs = tf.gather_nd(log_probs, action_indices)
            
            # PPO clipped objective
            ratio = tf.exp(selected_log_probs - old_log_probs)
            clipped_ratio = tf.clip_by_value(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio)
            policy_loss = -tf.minimum(ratio * advantages, clipped_ratio * advantages)
            
            # Value loss
            value_loss = tf.square(returns - values)
            
            # Entropy bonus for exploration
            entropy = -tf.reduce_sum(action_probs * log_probs, axis=1)
            
            # Total loss
            total_loss = tf.reduce_mean(
                policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
            )
        
        # Compute gradients and update
        gradients = tape.gradient(total_loss, 
                                  self.policy_network.trainable_variables + 
                                  self.value_network.trainable_variables)
        self.policy_optimizer.apply_gradients(
            zip(gradients[:len(self.policy_network.trainable_variables)],
                self.policy_network.trainable_variables)
        )
        self.value_optimizer.apply_gradients(
            zip(gradients[len(self.policy_network.trainable_variables):],
                self.value_network.trainable_variables)
        )
        
        return total_loss

class ExperienceBuffer:
    """Stores and samples experience for training"""
    
    def __init__(self, capacity=10000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
        
    def add(self, state, action, reward, next_state, done, info=None):
        """Add experience with priority"""
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done,
            'info': info or {}
        }
        
        # Priority based on TD error or reward magnitude
        priority = abs(reward) + 0.01
        self.buffer.append(experience)
        self.priorities.append(priority)
    
    def sample(self, batch_size=32, prioritized=True):
        """Sample batch with optional prioritization"""
        if prioritized:
            # Convert priorities to probabilities
            probs = np.array(self.priorities) / sum(self.priorities)
            indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        else:
            indices = np.random.choice(len(self.buffer), batch_size)
            
        batch = [self.buffer[i] for i in indices]
        return batch
    
    def get_stats(self):
        """Get buffer statistics"""
        if not self.buffer:
            return {}
        
        rewards = [exp['reward'] for exp in self.buffer]
        return {
            'size': len(self.buffer),
            'avg_reward': np.mean(rewards),
            'max_reward': np.max(rewards),
            'min_reward': np.min(rewards),
            'std_reward': np.std(rewards)
        }

class RewardShaper:
    """Multi-factor reward calculation"""
    
    def __init__(self):
        self.weights = {
            'correctness': 0.3,      # Formula correctness, reasonable values
            'efficiency': 0.2,       # Minimal steps to goal
            'consistency': 0.15,     # Following patterns
            'completeness': 0.15,    # Progress toward full model
            'formatting': 0.1,       # Proper formatting
            'complexity': 0.1        # Appropriate complexity
        }
    
    def calculate_reward(self, state_before, state_after, action, user_feedback=None):
        """Calculate multi-factor reward"""
        rewards = {}
        
        # Correctness - check formulas work and values are reasonable
        rewards['correctness'] = self._check_correctness(state_after)
        
        # Efficiency - penalize redundant actions
        rewards['efficiency'] = self._check_efficiency(state_before, state_after, action)
        
        # Consistency - reward following existing patterns
        rewards['consistency'] = self._check_consistency(state_after)
        
        # Completeness - progress toward complete model
        rewards['completeness'] = self._check_completeness(state_after)
        
        # Formatting - proper number formats, alignment
        rewards['formatting'] = self._check_formatting(state_after)
        
        # Complexity - appropriate for task
        rewards['complexity'] = self._check_complexity(state_after, action)
        
        # Calculate weighted sum
        total_reward = sum(self.weights[k] * rewards[k] for k in rewards)
        
        # Apply user feedback multiplier if provided
        if user_feedback:
            feedback_multiplier = {
                'perfect': 2.0,
                'good': 1.5,
                'okay': 1.0,
                'poor': 0.5,
                'wrong': -1.0
            }.get(user_feedback, 1.0)
            total_reward *= feedback_multiplier
        
        return total_reward, rewards
    
    def _check_correctness(self, state):
        """Check if formulas are valid and values reasonable"""
        # Check for #ERROR, #DIV/0, etc
        # Check if values are within reasonable ranges
        # Return score 0-1
        return 0.8  # Placeholder
    
    def _check_efficiency(self, state_before, state_after, action):
        """Penalize redundant or inefficient actions"""
        # Check if action made meaningful progress
        # Penalize overwriting recent work
        return 0.7  # Placeholder
    
    def _check_consistency(self, state):
        """Check if following existing patterns"""
        # Look for consistent formula patterns
        # Check naming conventions
        return 0.9  # Placeholder
    
    def _check_completeness(self, state):
        """Measure progress toward complete model"""
        # Count filled vs empty cells in expected areas
        # Check for key components (revenue, costs, etc)
        return 0.6  # Placeholder
    
    def _check_formatting(self, state):
        """Check proper formatting"""
        # Number formats, alignment, etc
        return 0.8  # Placeholder
    
    def _check_complexity(self, state, action):
        """Check if complexity is appropriate"""
        # Not too simple, not overly complex
        return 0.7  # Placeholder

def train_agent(episodes=1000):
    """Main training loop"""
    # Initialize components
    encoder = SpreadsheetStateEncoder()
    action_space = ActionSpace()
    agent = PPOAgent()
    reward_shaper = RewardShaper()
    
    for episode in range(episodes):
        # Reset environment (would need actual spreadsheet env)
        state = get_initial_state()  # Placeholder
        state_encoded = encoder.encode(state)
        
        episode_reward = 0
        done = False
        
        while not done:
            # Select action
            action = agent.select_action(state_encoded)
            
            # Execute action in environment
            next_state, done = execute_action(state, action)  # Placeholder
            next_state_encoded = encoder.encode(next_state)
            
            # Calculate reward
            reward, reward_components = reward_shaper.calculate_reward(
                state, next_state, action
            )
            
            # Store experience
            agent.buffer.add(state_encoded, action, reward, next_state_encoded, done)
            
            # Update state
            state = next_state
            state_encoded = next_state_encoded
            episode_reward += reward
            
            # Train if enough experience
            if len(agent.buffer.buffer) >= 1000:
                batch = agent.buffer.sample(32)
                # Convert batch to tensors and train
                # agent.train_step(...)  # Would need proper tensor conversion
        
        print(f"Episode {episode}: Reward = {episode_reward:.2f}")
        
        # Save checkpoint periodically
        if episode % 100 == 0:
            save_checkpoint(agent, episode)

def get_initial_state():
    """Create initial spreadsheet state"""
    return SpreadsheetState(
        grid_values=np.zeros((50, 20)),
        grid_formulas=np.zeros((50, 20)),
        cell_types=np.zeros((50, 20)),
        cell_formats=np.zeros((50, 20)),
        metadata={}
    )

def execute_action(state, action):
    """Execute action in spreadsheet environment"""
    # Would need actual implementation
    return state, False

def save_checkpoint(agent, episode):
    """Save model checkpoint"""
    agent.policy_network.save(f'checkpoints/policy_{episode}.h5')
    agent.value_network.save(f'checkpoints/value_{episode}.h5')

if __name__ == "__main__":
    print("Deep RL Agent for Financial Modeling")
    print("=====================================")
    print("Features:")
    print("- PPO algorithm for stable learning")
    print("- CNN + Attention for state encoding")
    print("- Multi-head policy for complex actions")
    print("- Prioritized experience replay")
    print("- Multi-factor reward shaping")
    print("\nReady to train!")