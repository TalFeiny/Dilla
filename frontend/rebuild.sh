#!/bin/bash

# Frontend Full Rebuild Script

echo "🔨 Full Frontend Rebuild..."

# 1. Kill existing server
echo "Stopping current server..."
PID=$(lsof -i :3001 | grep node | awk '{print $2}' | head -1)
if [ ! -z "$PID" ]; then
    kill -9 $PID
    echo "✅ Killed process $PID"
    sleep 1
fi

# 2. Clear everything
echo "Cleaning build files..."
rm -rf .next
rm -rf node_modules/.cache
echo "✅ Build files cleared"

# 3. Optional: Full reinstall (uncomment if needed)
# echo "Reinstalling dependencies..."
# rm -rf node_modules package-lock.json
# npm install
# echo "✅ Dependencies reinstalled"

# 4. Start server
echo "Starting server..."
npm run dev