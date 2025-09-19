#!/bin/bash

# Frontend Restart Script

echo "🔄 Restarting Frontend Server..."

# 1. Kill existing server
echo "Stopping current server..."
PID=$(lsof -i :3001 | grep node | awk '{print $2}' | head -1)
if [ ! -z "$PID" ]; then
    kill -9 $PID
    echo "✅ Killed process $PID"
else
    echo "No server running on port 3001"
fi

# 2. Clear cache (optional - uncomment if needed)
# echo "Clearing cache..."
# rm -rf .next
# rm -rf node_modules/.cache
# echo "✅ Cache cleared"

# 3. Start server
echo "Starting fresh server..."
npm run dev