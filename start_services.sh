#!/bin/bash

# Start Services Script for Dilla AI
echo "🚀 Starting Dilla AI Services..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Start Backend
echo -e "${BLUE}Starting Backend on port 8000...${NC}"
cd backend
python3 -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend started with PID: $BACKEND_PID${NC}"
cd ..

# Wait for backend to be ready
echo -e "${BLUE}Waiting for backend to be ready...${NC}"
sleep 5

# Check if backend is running
if curl -s http://localhost:8000/api/health > /dev/null; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${RED}✗ Backend failed to start${NC}"
    exit 1
fi

# Start Frontend
echo -e "${BLUE}Starting Frontend on port 3001...${NC}"
cd frontend
npm run dev -- -p 3001 &
FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend started with PID: $FRONTEND_PID${NC}"
cd ..

# Wait for frontend to be ready
echo -e "${BLUE}Waiting for frontend to be ready...${NC}"
sleep 10

# Save PIDs for later shutdown
echo $BACKEND_PID > backend.pid
echo $FRONTEND_PID > frontend.pid

echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "📍 Access points:"
echo "   Backend API: http://localhost:8000"
echo "   Frontend:    http://localhost:3001"
echo ""
echo "📊 Test pages:"
echo "   Matrix:      http://localhost:3001/matrix"
echo "   Docs:        http://localhost:3001/docs-agent"
echo "   Deck:        http://localhost:3001/deck-agent"
echo "   Fund Admin:  http://localhost:3001/fund_admin"
echo "   Management:  http://localhost:3001/management-accounts"
echo ""
echo "To stop services, run: ./stop_services.sh"