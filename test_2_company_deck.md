# Test Query: 2 Company Deck Generation

## Query
Create comprehensive investment deck for @Vega and @73Strings. These are AI companies - Vega does AI security analytics, 73Strings does AI for alternative asset data extraction. Fund context: $234M fund with $109M remaining.

## Expected Results
1. Both companies extracted with complete data
2. Investors extracted from funding rounds and added to top-level company data
3. Investors displayed in deck slides
4. Charts generated and attached to slides
5. No data mixing between companies

## API Request
```bash
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create comprehensive investment deck for @Vega and @73Strings. These are AI companies - Vega does AI security analytics, 73Strings does AI for alternative asset data extraction. Fund context: $234M fund with $109M remaining.",
    "output_format": "deck",
    "context": {
      "fund_size": 234000000,
      "remaining_capital": 109000000,
      "target_ownership": 0.15
    },
    "stream": false
  }' \
  --max-time 300
```
