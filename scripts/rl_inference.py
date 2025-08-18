#!/usr/bin/env python3
"""
RL Agent Inference Server
Handles predictions and online learning
"""

import sys
import json
from pathlib import Path

# Import our NumPy-based RL agent (no TensorFlow/PyTorch needed)
sys.path.append(str(Path(__file__).parent))
from numpy_rl_agent import RLInferenceServer

def main():
    """CLI interface"""
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
            
        elif command == 'reset':
            # Reset for new episode
            print(json.dumps({'success': True}))
            
        else:
            print(json.dumps({'error': f'Unknown command: {command}'}))
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()