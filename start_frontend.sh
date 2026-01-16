#!/bin/bash

# Start Frontend Server
echo "🚀 Starting Dilla AI Frontend Server..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
FRONTEND_PORT=3001

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Starting Dilla AI Frontend${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Navigate to frontend directory
cd frontend || exit 1

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠ node_modules not found. Installing dependencies...${NC}"
    npm install
fi

# Start frontend
echo -e "${BLUE}Starting frontend on port ${FRONTEND_PORT}...${NC}"
echo -e "${GREEN}Frontend will be available at: http://localhost:${FRONTEND_PORT}${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the frontend server${NC}"
echo ""

npm run dev -- -p ${FRONTEND_PORT}

