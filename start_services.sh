#!/bin/bash

# Enhanced Start Services Script for Dilla AI with Logging
echo "🚀 Starting Dilla AI Services with Enhanced Logging..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=${BACKEND_PORT:-${PORT:-8000}}
FRONTEND_PORT=3001
LOG_DIR="./logs"

# Create logs directory
mkdir -p "$LOG_DIR"

# Backend log files
BACKEND_LOG="${LOG_DIR}/backend.log"
BACKEND_ERROR_LOG="${LOG_DIR}/backend_errors.log"

# Frontend log file
FRONTEND_LOG="${LOG_DIR}/frontend.log"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Starting Dilla AI Services${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Start Backend
echo -e "${BLUE}Starting Backend on port ${BACKEND_PORT}...${NC}"
cd backend

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "venv312" ]; then
    source venv312/bin/activate
fi

# Start backend with logging
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${BACKEND_PORT}" \
    >> "../${BACKEND_LOG}" 2>> "../${BACKEND_ERROR_LOG}" &
BACKEND_PID=$!

echo -e "${GREEN}✓ Backend started with PID: $BACKEND_PID${NC}"
echo -e "${GREEN}✓ Backend logs: ${BACKEND_LOG}${NC}"
echo -e "${GREEN}✓ Backend errors: ${BACKEND_ERROR_LOG}${NC}"
cd ..

# Wait for backend to be ready
echo -e "${BLUE}Waiting for backend to be ready...${NC}"
sleep 5

# Check if backend is running
for i in {1..10}; do
    if curl -s http://localhost:${BACKEND_PORT}/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is healthy${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${YELLOW}⚠ Backend may still be starting (check logs)${NC}"
    else
        sleep 1
    fi
done

# Start Frontend
echo -e "${BLUE}Starting Frontend on port ${FRONTEND_PORT}...${NC}"
cd frontend

# Start frontend with logging
npm run dev -- -p ${FRONTEND_PORT} >> "../${FRONTEND_LOG}" 2>&1 &
FRONTEND_PID=$!

echo -e "${GREEN}✓ Frontend started with PID: $FRONTEND_PID${NC}"
echo -e "${GREEN}✓ Frontend logs: ${FRONTEND_LOG}${NC}"
cd ..

# Wait for frontend to be ready
echo -e "${BLUE}Waiting for frontend to be ready...${NC}"
sleep 10

# Save PIDs for later shutdown
echo $BACKEND_PID > backend.pid
echo $FRONTEND_PID > frontend.pid

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "📍 Access points:"
echo "   Backend API: http://localhost:${BACKEND_PORT}"
echo "   Frontend:    http://localhost:${FRONTEND_PORT}"
echo ""
echo "📊 Log Files:"
echo "   Backend:     ${BACKEND_LOG}"
echo "   Backend Errors: ${BACKEND_ERROR_LOG}"
echo "   Frontend:    ${FRONTEND_LOG}"
echo ""
echo "📊 Test pages:"
echo "   Matrix:      http://localhost:${FRONTEND_PORT}/matrix"
echo "   Docs:        http://localhost:${FRONTEND_PORT}/docs-agent"
echo "   Deck:        http://localhost:${FRONTEND_PORT}/deck-agent"
echo "   Fund Admin:  http://localhost:${FRONTEND_PORT}/fund_admin"
echo "   Management:  http://localhost:${FRONTEND_PORT}/management-accounts"
echo ""
echo "📈 Monitoring:"
echo "   View logs:   ./monitor_logs.sh"
echo "   Errors only: ./monitor_logs.sh errors"
echo "   Stats:       ./monitor_logs.sh stats"
echo ""
echo "To stop services, run: ./stop_services.sh"
