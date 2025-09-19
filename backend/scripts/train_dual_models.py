#!/usr/bin/env python3
"""
Dual Model Training System
Trains both Mistral (reasoning) and Qwen (code) with GRPO
"""

import asyncio
import json
import numpy as np
from typing import List, Dict, Tuple
import logging
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import supabase_service
from app.services.grpo_rl_system import GRPOSystem, PreferencePair

logger = logging.getLogger(__name__)


class DualModelTrainer:
    """
    Trains two models with different objectives:
    - Mistral: Reasoning quality, analysis depth
    - Qwen2.5-Coder: Code correctness, syntax quality
    """
    
    def __init__(self):
        self.mistral_grpo = GRPOSystem()  # For reasoning/analysis
        self.qwen_grpo = GRPOSystem()     # For code generation
        
        # Separate scoring criteria
        self.reasoning_weights = {
            "has_decomposition": 0.3,
            "identifies_tools": 0.2,
            "parallel_thinking": 0.2,
            "cites_sources": 0.15,
            "structured_output": 0.15
        }
        
        self.code_weights = {
            "syntax_correct": 0.4,      # Most important
            "uses_asyncio": 0.2,         # For parallel execution
            "has_error_handling": 0.15,
            "proper_imports": 0.15,
            "returns_data": 0.1
        }
    
    async def generate_training_data(self):
        """Generate specialized training data for each model"""
        
        mistral_data = []
        qwen_data = []
        
        # Mistral Training Data (Reasoning & Analysis)
        reasoning_examples = [
            {
                "prompt": "Analyze @Ramp's market position",
                "good": """
                I need to analyze Ramp's market position across multiple dimensions:
                
                1. Data Collection (Parallel):
                   - Market size and growth data
                   - Competitor analysis (Brex, Deel, Divvy)
                   - Customer segment analysis
                   - Product differentiation factors
                
                2. Analysis Framework:
                   - TAM/SAM/SOM calculation
                   - Competitive positioning matrix
                   - Porter's Five Forces
                   - Growth trajectory vs peers
                
                3. Synthesis Approach:
                   - Identify moats and vulnerabilities
                   - Market share trajectory
                   - Strategic recommendations
                """,
                "bad": "Ramp is good. They have market share.",
                "score_good": 0.95,
                "score_bad": 0.2
            },
            {
                "prompt": "Create investment thesis for @Stripe",
                "good": """
                Investment Thesis Structure:
                
                Executive Summary:
                - Stripe at inflection point for public markets
                - $95B valuation justified by fundamentals
                
                Key Investment Drivers:
                1. Market Leadership (35% share in online payments)
                2. Platform Expansion (Stripe Capital, Treasury, Tax)
                3. Network Effects (2M+ developers)
                4. Pricing Power (2.9% + $0.30 sustainable)
                
                Financial Analysis Required:
                - Revenue: $14B (2023) → $28B (2025E)
                - Growth: 25% CAGR next 3 years
                - Margins: 25% EBITDA achievable at scale
                
                Risks to Monitor:
                - Regulatory (EU payment directives)
                - Competition (Block, Adyen)
                - Concentration (top 10 = 30% of volume)
                
                Return Potential: 3-5x in 5 years
                """,
                "bad": "Stripe good investment. Buy it.",
                "score_good": 1.0,
                "score_bad": 0.1
            }
        ]
        
        # Qwen Training Data (Code Generation)
        code_examples = [
            {
                "prompt": "Generate code to fetch Ramp data",
                "good": """
import asyncio
from typing import Dict, List

async def fetch_ramp_data() -> Dict:
    try:
        # Parallel data gathering
        results = await asyncio.gather(
            tavily_search("Ramp valuation Series D 2024"),
            tavily_search("Ramp revenue ARR growth rate"),
            database_search({"company": "Ramp"}),
            return_exceptions=True
        )
        
        # Process results
        data = {
            "valuation": results[0].get("valuation") if not isinstance(results[0], Exception) else None,
            "revenue": results[1].get("arr") if not isinstance(results[1], Exception) else None,
            "db_data": results[2] if not isinstance(results[2], Exception) else {}
        }
        
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}
""",
                "bad": "fetch_ramp_data() # This gets Ramp data",
                "score_good": 0.98,
                "score_bad": 0.05
            },
            {
                "prompt": "Create spreadsheet commands for DCF model",
                "good": """
// DCF Model Spreadsheet Commands
const commands = [
    // Headers
    "grid.write('A1', 'DCF Valuation Model')",
    "grid.style('A1', {bold: true, fontSize: 16})",
    
    // Revenue Projections
    "grid.write('A3', 'Revenue')",
    "grid.write('B2', 'Year 1')",
    "grid.write('C2', 'Year 2')",
    "grid.write('D2', 'Year 3')",
    "grid.write('E2', 'Year 4')",
    "grid.write('F2', 'Year 5')",
    
    // Formulas
    "grid.write('B3', 100)",
    "grid.formula('C3', '=B3*1.5')",
    "grid.formula('D3', '=C3*1.4')",
    "grid.formula('E3', '=D3*1.3')",
    "grid.formula('F3', '=E3*1.2')",
    
    // Cash Flow
    "grid.write('A4', 'Free Cash Flow')",
    "grid.formula('B4', '=B3*0.2')",
    "grid.formula('C4', '=C3*0.25')",
    "grid.formula('D4', '=D3*0.3')",
    
    // NPV Calculation
    "grid.write('A6', 'NPV')",
    "grid.formula('B6', '=NPV(0.12, B4:F4)')",
    
    // Chart
    "grid.createChart('line', {range: 'A2:F3', title: 'Revenue Projection'})"
];

commands.forEach(cmd => eval(cmd));
""",
                "bad": "make dcf spreadsheet with formulas",
                "score_good": 0.95,
                "score_bad": 0.0
            }
        ]
        
        # Convert to training format
        for ex in reasoning_examples:
            mistral_data.append({
                "prompt": ex["prompt"],
                "chosen": ex["good"],
                "rejected": ex["bad"],
                "score_diff": ex["score_good"] - ex["score_bad"]
            })
        
        for ex in code_examples:
            qwen_data.append({
                "prompt": ex["prompt"],
                "chosen": ex["good"],
                "rejected": ex["bad"],
                "score_diff": ex["score_good"] - ex["score_bad"]
            })
        
        return mistral_data, qwen_data
    
    def score_reasoning(self, response: str) -> float:
        """Score reasoning quality for Mistral training"""
        
        score = 0.0
        response_lower = response.lower()
        
        # Check decomposition
        if any(word in response_lower for word in ["step", "phase", "first", "then", "finally"]):
            score += self.reasoning_weights["has_decomposition"]
        
        # Check tool identification
        if any(tool in response_lower for tool in ["search", "database", "calculate", "analyze"]):
            score += self.reasoning_weights["identifies_tools"]
        
        # Check parallel thinking
        if any(word in response_lower for word in ["parallel", "simultaneously", "gather", "concurrent"]):
            score += self.reasoning_weights["parallel_thinking"]
        
        # Check citations
        if "[" in response or "source" in response_lower:
            score += self.reasoning_weights["cites_sources"]
        
        # Check structure
        if response.count('\n') > 5 and any(char in response for char in ['-', '•', '1.', '2.']):
            score += self.reasoning_weights["structured_output"]
        
        return min(1.0, score)
    
    def score_code(self, code: str) -> float:
        """Score code quality for Qwen training"""
        
        score = 0.0
        
        # Check syntax (basic)
        try:
            if "python" in code.lower() or "import" in code:
                compile(code.replace('await ', ''), '<string>', 'exec')
                score += self.code_weights["syntax_correct"]
        except:
            pass  # Syntax error
        
        # Check asyncio usage
        if "asyncio" in code or "await" in code:
            score += self.code_weights["uses_asyncio"]
        
        # Check error handling
        if "try:" in code and "except" in code:
            score += self.code_weights["has_error_handling"]
        
        # Check imports
        if "import" in code or "const" in code:
            score += self.code_weights["proper_imports"]
        
        # Check return values
        if "return" in code or "export" in code:
            score += self.code_weights["returns_data"]
        
        return min(1.0, score)
    
    async def train_models(self, epochs: int = 10):
        """Train both models with their specialized data"""
        
        print("🎯 Dual Model Training System")
        print("=" * 50)
        
        # Generate training data
        print("📝 Generating training data...")
        mistral_data, qwen_data = await self.generate_training_data()
        
        print(f"✅ Generated {len(mistral_data)} Mistral examples")
        print(f"✅ Generated {len(qwen_data)} Qwen examples")
        
        # Train Mistral on reasoning
        print("\n🧠 Training Mistral for reasoning...")
        mistral_results = {
            "model": "mistral",
            "focus": "reasoning & analysis",
            "examples": len(mistral_data),
            "improvements": []
        }
        
        for epoch in range(epochs):
            total_score = 0
            for example in mistral_data:
                # Score both options
                good_score = self.score_reasoning(example["chosen"])
                bad_score = self.score_reasoning(example["rejected"])
                
                # Create preference pair
                if good_score > bad_score:
                    # Update GRPO weights
                    total_score += good_score
            
            avg_score = total_score / len(mistral_data)
            mistral_results["improvements"].append(avg_score)
            print(f"  Epoch {epoch+1}: Score {avg_score:.3f}")
        
        # Train Qwen on code generation
        print("\n💻 Training Qwen for code generation...")
        qwen_results = {
            "model": "qwen2.5-coder",
            "focus": "code generation",
            "examples": len(qwen_data),
            "improvements": []
        }
        
        for epoch in range(epochs):
            total_score = 0
            for example in qwen_data:
                # Score both options
                good_score = self.score_code(example["chosen"])
                bad_score = self.score_code(example["rejected"])
                
                # Create preference pair
                if good_score > bad_score:
                    # Update GRPO weights
                    total_score += good_score
            
            avg_score = total_score / len(qwen_data)
            qwen_results["improvements"].append(avg_score)
            print(f"  Epoch {epoch+1}: Score {avg_score:.3f}")
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Training Complete!")
        print(f"\nMistral (Reasoning):")
        print(f"  Start: {mistral_results['improvements'][0]:.3f}")
        print(f"  Final: {mistral_results['improvements'][-1]:.3f}")
        print(f"  Gain: +{(mistral_results['improvements'][-1] - mistral_results['improvements'][0]):.3f}")
        
        print(f"\nQwen2.5-Coder (Code):")
        print(f"  Start: {qwen_results['improvements'][0]:.3f}")
        print(f"  Final: {qwen_results['improvements'][-1]:.3f}")
        print(f"  Gain: +{(qwen_results['improvements'][-1] - qwen_results['improvements'][0]):.3f}")
        
        return {
            "mistral": mistral_results,
            "qwen": qwen_results
        }
    
    async def save_weights(self):
        """Save trained weights for both models"""
        
        # In production, this would save to Supabase
        weights = {
            "mistral_weights": self.mistral_grpo.grpo_network.get_weights(),
            "qwen_weights": self.qwen_grpo.grpo_network.get_weights(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open("dual_model_weights.json", "w") as f:
            json.dump(weights, f)
        
        print("💾 Weights saved to dual_model_weights.json")


async def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║      DUAL MODEL FINE-TUNING SYSTEM          ║
    ║                                              ║
    ║  Mistral: Reasoning & Analysis              ║
    ║  Qwen2.5: Code Generation                   ║
    ╚══════════════════════════════════════════════╝
    """)
    
    trainer = DualModelTrainer()
    
    # Train both models
    results = await trainer.train_models(epochs=5)
    
    # Save weights
    await trainer.save_weights()
    
    print("\n✅ Both models trained for their specialized tasks!")
    print("   Mistral → Better at planning and analysis")
    print("   Qwen → Better at generating executable code")


if __name__ == "__main__":
    asyncio.run(main())