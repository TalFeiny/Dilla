#!/bin/bash

# Stop Services Script for Dilla AI
echo "🛑 Stopping Dilla AI Services..."

# Kill backend
if [ -f backend.pid ]; then
    kill $(cat backend.pid) 2>/dev/null
    rm backend.pid
    echo "✓ Backend stopped"
fi

# Kill frontend  
if [ -f frontend.pid ]; then
    kill $(cat frontend.pid) 2>/dev/null
    rm frontend.pid
    echo "✓ Frontend stopped"
fi

# Also kill any orphaned processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null

echo "✅ All services stopped"