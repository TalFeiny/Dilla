#!/bin/bash

# Test deck generation with string companies (@ symbols)
echo "Testing deck generation with string companies..."
echo "================================================"

curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "deck-storytelling",
    "companies": ["@Mercury", "@Brex"],
    "inputs": {
      "fund_context": {
        "fund_size": 234000000,
        "remaining_capital": 109000000,
        "deployed_capital": 125000000,
        "portfolio_count": 12,
        "dpi": 0.4,
        "tvpi": 1.8,
        "fund_year": 3
      }
    }
  }' | python3 -m json.tool

echo ""
echo "Test complete!"