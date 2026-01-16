#!/bin/bash

# TAM Search Test via Curl
# Tests the production TAM extraction pipeline through the unified brain endpoint

echo "============================================================"
echo "TAM EXTRACTION TEST - PRODUCTION PIPELINE"
echo "============================================================"

# Check if backend is running
echo "Step 1: Checking backend status..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Backend is running"
else
    echo "❌ Backend not running. Starting backend..."
    echo "Run this command in another terminal:"
    echo "cd /Users/admin/code/dilla-ai/backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Test TAM extraction for NoxMetals (let system figure out what it does)
echo ""
echo "Step 2: Testing TAM extraction for NoxMetals..."
echo "Sending request to unified brain endpoint..."

curl -X POST "http://localhost:8000/api/agent/unified-brain" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze NoxMetals as an investment opportunity and provide comprehensive market sizing analysis including TAM, SAM, and SOM",
    "output_format": "analysis",
    "context": {
      "company_name": "NoxMetals"
    }
  }' \
  --max-time 120 \
  -w "\n\nHTTP Status: %{http_code}\nTotal Time: %{time_total}s\n" \
  -o noxmetals_tam_response.json

echo ""
echo "Step 3: Analyzing response..."

if [ -f tam_response.json ]; then
    echo "✓ Response received and saved to tam_response.json"
    
    # Check if response contains TAM data
    if grep -q "tam_market_definition\|market_analysis\|TAM" tam_response.json; then
        echo "✓ TAM data found in response"
        
        # Extract key TAM information
        echo ""
        echo "TAM EXTRACTION RESULTS:"
        echo "-----------------------"
        
        # Try to extract market definition
        if grep -q "tam_market_definition" tam_response.json; then
            echo "Market Definition:"
            grep -o '"tam_market_definition":"[^"]*"' tam_response.json | head -1
        fi
        
        # Try to extract TAM estimates
        if grep -q "tam_estimates" tam_response.json; then
            echo ""
            echo "TAM Estimates found (check tam_response.json for details)"
        fi
        
        # Try to extract market analysis
        if grep -q "market_analysis" tam_response.json; then
            echo ""
            echo "Market Analysis section found"
        fi
        
        echo ""
        echo "✓ SUCCESS: TAM extraction pipeline is working"
        echo "Full response saved to: tam_response.json"
        
    else
        echo "❌ No TAM data found in response"
        echo "Response preview:"
        head -20 tam_response.json
        echo ""
        echo "This may indicate:"
        echo "- TAM extraction failed"
        echo "- Response format changed"
        echo "- Backend error"
    fi
    
else
    echo "❌ No response file created"
    echo "This indicates the curl request failed"
fi

echo ""
echo "============================================================"
echo "TEST COMPLETE"
echo "============================================================"
echo ""
echo "To view the full response:"
echo "cat tam_response.json | jq ."
echo ""
echo "To search for TAM data:"
echo "grep -i 'tam\|market' tam_response.json"
