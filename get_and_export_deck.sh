#!/bin/bash

# Step 1: Get the deck data
echo "📥 Getting deck data..."
curl -s -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "monitor compare @Cuspai with @Exactlyai for my 145m fund with 86m to deploy",
    "output_format": "deck"
  }' > /tmp/deck_response.json

# Step 2: Extract just the deck data (the "result" field)
echo "📦 Extracting deck data..."
cat > /tmp/extract_deck.py << 'EOF'
import json
import sys

with open('/tmp/deck_response.json', 'r') as f:
    data = json.load(f)

# Get the deck data from result.result
deck = data.get('result', {})
print(json.dumps(deck))
EOF

python3 /tmp/extract_deck.py > /tmp/deck_data.json

# Step 3: Export to PDF
echo "📄 Exporting to PDF..."
curl -X POST http://localhost:8000/api/export/deck \
  -H "Content-Type: application/json" \
  -d @- < <(jq -n --argjson deck "$(cat /tmp/deck_data.json)" '{deck_data: $deck, format: "pdf"}') \
  --output deck.pdf

echo "✅ Done! PDF saved as deck.pdf"

