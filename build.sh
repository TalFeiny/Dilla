#!/bin/bash

# Dilla AI Complete Build Script
# Builds and sets up the entire project infrastructure

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Dilla AI - Complete Build System    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if running from project root
if [ ! -f "$PROJECT_ROOT/package.json" ]; then
    print_error "Error: Must run from project root directory"
    exit 1
fi

# Step 1: Environment Setup
print_status "Step 1: Setting up environment files..."

# Create .env for root if it doesn't exist
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cat > "$PROJECT_ROOT/.env" << 'EOF'
# Root environment variables
NODE_ENV=development
ENVIRONMENT=development
EOF
    print_success "Created root .env file"
else
    print_success "Root .env file already exists"
fi

# Create backend .env if it doesn't exist
if [ ! -f "$PROJECT_ROOT/backend/.env" ]; then
    cat > "$PROJECT_ROOT/backend/.env" << 'EOF'
# Backend Configuration
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production-$(openssl rand -hex 32)

# Database
DATABASE_URL=postgresql://user:password@localhost/dilla_ai
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# API Keys
ANTHROPIC_API_KEY=your-anthropic-api-key
CLAUDE_API_KEY=your-claude-api-key
OPENAI_API_KEY=your-openai-api-key
TAVILY_API_KEY=your-tavily-api-key
FIRECRAWL_API_KEY=your-firecrawl-api-key

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Celery (optional)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
EOF
    print_success "Created backend/.env file (UPDATE WITH YOUR KEYS)"
else
    print_success "Backend .env file already exists"
fi

# Create frontend .env.local if it doesn't exist
if [ ! -f "$PROJECT_ROOT/frontend/.env.local" ]; then
    cat > "$PROJECT_ROOT/frontend/.env.local" << 'EOF'
# Frontend Configuration
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key

# API Keys (for server-side)
ANTHROPIC_API_KEY=your-anthropic-api-key
CLAUDE_API_KEY=your-claude-api-key
OPENAI_API_KEY=your-openai-api-key
TAVILY_API_KEY=your-tavily-api-key
FIRECRAWL_API_KEY=your-firecrawl-api-key

# Backend URL
FASTAPI_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Optional
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
NEXT_PUBLIC_GA_TRACKING_ID=
EOF
    print_success "Created frontend/.env.local file (UPDATE WITH YOUR KEYS)"
else
    print_success "Frontend .env.local file already exists"
fi

# Step 2: Install Dependencies
print_status "Step 2: Installing dependencies..."

# Check for Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check for Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_success "Node.js $NODE_VERSION found"
else
    print_error "Node.js not found. Please install Node.js 18+"
    exit 1
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
cd "$PROJECT_ROOT/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Created Python virtual environment"
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_success "Python dependencies installed"

# Install additional packages for advanced analytics
pip install numpy pandas scipy scikit-learn
print_success "Analytics packages installed"

# Step 3: Install Frontend Dependencies
print_status "Step 3: Installing frontend dependencies..."
cd "$PROJECT_ROOT/frontend"

# Install npm packages
npm install
print_success "Frontend dependencies installed"

# Step 4: Install Root Dependencies
print_status "Step 4: Installing root dependencies..."
cd "$PROJECT_ROOT"

if [ -f "package.json" ]; then
    npm install
    print_success "Root dependencies installed"
fi

# Step 5: Database Setup
print_status "Step 5: Setting up database..."

# Check if Supabase CLI is installed
if command -v supabase &> /dev/null; then
    print_success "Supabase CLI found"
    # You can add Supabase init commands here if needed
else
    print_status "Supabase CLI not found. Install from: https://supabase.com/docs/guides/cli"
fi

# Create SQL setup script
cat > "$PROJECT_ROOT/backend/setup_database.sql" << 'EOF'
-- Database setup for Dilla AI

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sector VARCHAR(100),
    revenue_usd BIGINT,
    total_funding_usd BIGINT,
    last_valuation_usd BIGINT,
    employee_count INTEGER,
    founded_year INTEGER,
    headquarters VARCHAR(255),
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    content TEXT,
    metadata JSONB,
    processed BOOLEAN DEFAULT FALSE,
    analysis_results JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Analytics results table
CREATE TABLE IF NOT EXISTS analytics_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255),
    analysis_type VARCHAR(50),
    result JSONB,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Portfolio table
CREATE TABLE IF NOT EXISTS portfolio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),
    investment_date DATE,
    investment_amount BIGINT,
    ownership_percentage FLOAT,
    current_valuation BIGINT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_documents_processed ON documents(processed);
CREATE INDEX IF NOT EXISTS idx_analytics_company ON analytics_results(company_name);
CREATE INDEX IF NOT EXISTS idx_portfolio_company ON portfolio(company_id);

-- Enable Row Level Security (for Supabase)
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio ENABLE ROW LEVEL SECURITY;
EOF
print_success "Database setup script created"

# Step 6: Build Frontend
print_status "Step 6: Building frontend..."
cd "$PROJECT_ROOT/frontend"

# Build Next.js app
npm run build
print_success "Frontend built successfully"

# Step 7: Verify Installation
print_status "Step 7: Verifying installation..."

# Check backend imports
cd "$PROJECT_ROOT/backend"
source venv/bin/activate

python3 -c "
import sys
try:
    from app.main import app
    from app.services.mcp_orchestrator import MCPOrchestrator
    from app.services.analytics_bridge import AnalyticsBridge
    print('✓ Backend modules verified')
except ImportError as e:
    print(f'✗ Backend import error: {e}')
    sys.exit(1)
"

# Check frontend build
if [ -d "$PROJECT_ROOT/frontend/.next" ]; then
    print_success "Frontend build verified"
else
    print_error "Frontend build not found"
fi

# Step 8: Create startup scripts
print_status "Step 8: Creating startup scripts..."

# Create backend start script
cat > "$PROJECT_ROOT/start_backend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/backend"
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
EOF
chmod +x "$PROJECT_ROOT/start_backend.sh"
print_success "Backend start script created"

# Create frontend start script
cat > "$PROJECT_ROOT/start_frontend.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/frontend"
npm run dev -- -p 3001
EOF
chmod +x "$PROJECT_ROOT/start_frontend.sh"
print_success "Frontend start script created"

# Create combined start script
cat > "$PROJECT_ROOT/start_all.sh" << 'EOF'
#!/bin/bash

# Start both services
echo "Starting Dilla AI Services..."

# Function to cleanup on exit
cleanup() {
    echo "Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
echo "Starting backend on port 8000..."
./start_backend.sh &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Start frontend
echo "Starting frontend on port 3001..."
./start_frontend.sh &
FRONTEND_PID=$!

echo "Services started!"
echo "Frontend: http://localhost:3001"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for processes
wait
EOF
chmod +x "$PROJECT_ROOT/start_all.sh"
print_success "Combined start script created"

# Step 9: Create Docker files
print_status "Step 9: Creating Docker configuration..."

# Create backend Dockerfile
cat > "$PROJECT_ROOT/backend/Dockerfile" << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
print_success "Backend Dockerfile created"

# Create frontend Dockerfile
cat > "$PROJECT_ROOT/frontend/Dockerfile" << 'EOF'
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3001

# Run the application
CMD ["npm", "start"]
EOF
print_success "Frontend Dockerfile created"

# Create docker-compose.yml
cat > "$PROJECT_ROOT/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
    env_file:
      - ./backend/.env
    volumes:
      - ./backend:/app
    depends_on:
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3001:3000"
    environment:
      - FASTAPI_URL=http://backend:8000
    env_file:
      - ./frontend/.env.local
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      - backend

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
EOF
print_success "Docker Compose configuration created"

# Step 10: Final Summary
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Build Complete! 🎉              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Project Structure:${NC}"
echo "  📁 backend/       - FastAPI backend (Port 8000)"
echo "  📁 frontend/      - Next.js frontend (Port 3001)"
echo "  📄 .env files     - Configuration (UPDATE WITH YOUR KEYS)"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Update .env files with your API keys"
echo "  2. Set up your Supabase database"
echo "  3. Run database migrations"
echo ""
echo -e "${BLUE}Start Services:${NC}"
echo "  ./start_all.sh     - Start both frontend and backend"
echo "  ./start_backend.sh - Start backend only"
echo "  ./start_frontend.sh - Start frontend only"
echo ""
echo -e "${BLUE}Docker:${NC}"
echo "  docker-compose up  - Run with Docker"
echo ""
echo -e "${BLUE}Access Points:${NC}"
echo "  Frontend:  http://localhost:3001"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}⚠️  Important:${NC}"
echo "  Remember to update all .env files with your actual API keys!"
echo ""