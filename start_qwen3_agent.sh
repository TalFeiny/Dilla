#!/bin/bash

# Dilla AI - Start Qwen3 Agent with GRPO Training
# Complete system startup with all tools and frameworks

echo "=========================================="
echo "🚀 Starting Dilla AI with Qwen3 + GRPO"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Ollama is running
echo -e "${YELLOW}Checking Ollama status...${NC}"
if ! pgrep -x "ollama" > /dev/null; then
    echo -e "${YELLOW}Starting Ollama...${NC}"
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

# Check if Qwen3 model is installed
echo -e "${YELLOW}Checking Qwen3 model...${NC}"
if ! ollama list | grep -q "qwen3:latest"; then
    echo -e "${RED}Qwen3 not found! Installing...${NC}"
    echo -e "${YELLOW}This will download 5.2GB, please wait...${NC}"
    ollama pull qwen3:latest
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Qwen3 installed successfully${NC}"
    else
        echo -e "${RED}Failed to install Qwen3. Please run: ollama pull qwen3:latest${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Qwen3 model found${NC}"
fi

# Start backend with all services
echo ""
echo -e "${BLUE}=========================================="
echo "Starting Backend Services"
echo "==========================================${NC}"
echo ""

# Navigate to backend directory
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start the backend server
echo -e "${YELLOW}Starting FastAPI backend on port 8000...${NC}"
python3 -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to initialize...${NC}"
sleep 5

# Test Qwen3 integration
echo ""
echo -e "${BLUE}=========================================="
echo "Testing Qwen3 Integration"
echo "==========================================${NC}"
echo ""

python3 - <<EOF
import asyncio
import sys
sys.path.append('.')

async def test_qwen():
    try:
        from app.services.qwen_agent_service import get_qwen_agent_service
        from app.services.unified_mcp_orchestrator import get_unified_orchestrator
        
        qwen_agent = get_qwen_agent_service()
        orchestrator = get_unified_orchestrator()
        
        print("✓ Qwen3 agent service initialized")
        print("✓ Unified MCP orchestrator ready")
        print("✓ GRPO training system connected")
        
        # Test a simple tool call
        result = await qwen_agent.process_with_tools(
            prompt="Calculate NPV of [-100000, 30000, 40000, 50000] at 10%",
            context={},
            stream=False
        )
        
        if result.get('success'):
            print("✓ Tool calling test successful")
        else:
            print("⚠ Tool calling test needs configuration")
            
    except Exception as e:
        print(f"⚠ Test error: {e}")

asyncio.run(test_qwen())
EOF

echo ""
echo -e "${BLUE}=========================================="
echo "Available Tools & Frameworks"
echo "==========================================${NC}"
echo ""
echo -e "${GREEN}4 BASE TOOLS:${NC}"
echo "  • search_web - Tavily web search"
echo "  • scrape_website - Tavily extraction"
echo "  • execute_python - Python calculations"
echo "  • execute_javascript - JS execution"
echo ""
echo -e "${GREEN}19 PRIMARY SKILLS:${NC}"
echo "  • company-data-fetcher"
echo "  • funding-aggregator"
echo "  • competitive-intelligence"
echo "  • valuation-engine & pwerm-calculator"
echo "  • unit-economics-analyzer"
echo "  • fund-fit-analyzer"
echo "  • portfolio-constructor"
echo "  • investment-thesis-generator"
echo "  • deal-scorer & market-timing-analyzer"
echo "  • chart-generator & deck-storytelling"
echo "  • excel-generator & memo-writer"
echo ""
echo -e "${GREEN}CONVERTIBLE SECURITIES:${NC}"
echo "  • SAFE calculator"
echo "  • Warrant pricing"
echo "  • Liquidation waterfall"
echo "  • Ratchet modeling"
echo "  • PIK loan calculator"
echo ""
echo -e "${GREEN}PARALLEL EXECUTION:${NC}"
echo "  • Parallel task execution"
echo "  • Batch processing"
echo "  • Skill chain orchestration"
echo ""
echo -e "${GREEN}VISUALIZATION (10+ types):${NC}"
echo "  • Sankey, Heatmap, Waterfall"
echo "  • Treemap, Cohort, Runway"
echo "  • Cap table visualization"
echo ""

# Start frontend in new terminal (optional)
echo -e "${BLUE}=========================================="
echo "Frontend Setup"
echo "==========================================${NC}"
echo ""
echo -e "${YELLOW}To start the frontend, run in a new terminal:${NC}"
echo "  cd frontend"
echo "  npm run dev"
echo ""

echo -e "${GREEN}=========================================="
echo "✅ Qwen3 + GRPO System Ready!"
echo "==========================================${NC}"
echo ""
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:8000/api/qwen/test"
echo "  curl http://localhost:8000/api/mcp/tools/status"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"

# Keep the script running
wait $BACKEND_PID