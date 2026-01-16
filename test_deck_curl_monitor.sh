#!/bin/bash
# Test deck generation with monitoring

PROMPT='Compare @ExactlyAI and @CuspAI for my 345m fund with 234m to deploy'

echo "==================================="
echo "TEST: Deck Generation with Monitor"
echo "Prompt: $PROMPT"
echo "==================================="
echo ""

# Start monitoring in background
echo "Starting log monitoring..."
tail -f backend.log | grep -E "(DECK_GEN|EXTRACTION|COMPANY|ORCHESTRATOR|deck-storytelling)" --line-buffered &
MONITOR_PID=$!

# Give monitor a moment to start
sleep 2

# Make the request
echo "Sending request..."
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"$PROMPT\",
    \"format\": \"deck\",
    \"context\": {
      \"fund_size\": 345000000,
      \"remaining_capital\": 234000000
    }
  }" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -o response.json

echo ""
echo "Request completed"

# Wait a moment for logs
sleep 3

# Kill monitor
kill $MONITOR_PID 2>/dev/null

echo ""
echo "==================================="
echo "Response saved to response.json"
echo "Check backend.log for detailed logs"
echo "==================================="

