#!/bin/bash

# Start Backend Server
echo "🚀 Starting Dilla AI Backend Server..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=${BACKEND_PORT:-8000}

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Starting Dilla AI Backend${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Navigate to backend directory
cd backend || exit 1

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${BLUE}Activating virtual environment (venv)...${NC}"
    source venv/bin/activate
elif [ -d "venv312" ]; then
    echo -e "${BLUE}Activating virtual environment (venv312)...${NC}"
    source venv312/bin/activate
else
    echo -e "${YELLOW}⚠ Warning: No virtual environment found${NC}"
fi

# Start backend
echo -e "${BLUE}Starting backend on port ${BACKEND_PORT}...${NC}"
echo -e "${GREEN}Backend will be available at: http://localhost:${BACKEND_PORT}${NC}"
echo -e "${GREEN}API docs will be available at: http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the backend server${NC}"
echo ""

python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${BACKEND_PORT}"

