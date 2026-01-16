#!/bin/bash

# Test deck generation with a simple company query
echo "Testing deck generation via unified-brain..."

curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze @Mercury and @Ramp for investment",
    "output_format": "deck",
    "stream": false,
    "context": {}
  }' | python3 -m json.tool

echo ""
echo "========================================="
echo "Check the response for:"
echo "1. format: 'deck'"
echo "2. slides array with actual slides"
echo "3. No error messages about TAM"
echo "========================================="