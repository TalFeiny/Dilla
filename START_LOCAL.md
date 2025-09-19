# 🚀 How to Start Dilla AI on Localhost

## Quick Start (Easiest Way)

### Step 1: Install Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install fastapi uvicorn supabase pandas numpy aiohttp python-multipart
```

### Step 2: Create .env file
```bash
cd backend
cp .env.example .env
# Edit .env with your actual credentials (or use test values)
```

### Step 3: Start the Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**That's it! Your backend is now running at http://localhost:8000**

## What You Can Access

Once running, you can access:
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **API Root**: http://localhost:8000

## Available Services (What's Actually Migrated)

### ✅ Core Services Working:
1. **Companies API** - CRUD operations for companies
2. **PWERM Analysis** - Valuation analysis 
3. **Self-Learning Agent** - AI agent with RL capabilities
4. **Portfolio Management** - Portfolio metrics and analysis
5. **Document Processing** - Upload and process documents
6. **Market Research** - Market intelligence gathering

### ⚠️ Not Yet Migrated (Still in Next.js):
- Many specialized agent endpoints (claude, crew, mcp, etc.)
- Data room management
- KYC processing
- LP (Limited Partner) management
- Funds management
- Audit endpoints
- Various dashboard endpoints
- Streaming endpoints

## Test the API

### Test if it's working:
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test API docs
open http://localhost:8000/docs
```

### Test PWERM endpoint:
```bash
curl -X POST "http://localhost:8000/api/pwerm/test"
```

### Test Agent:
```bash
curl -X POST "http://localhost:8000/api/agents/test"
```

## Common Issues & Solutions

### Issue: Import errors
```bash
# Solution: Install missing dependencies
pip install <missing-package>
```

### Issue: Supabase connection fails
```bash
# Solution: Backend works without Supabase - just shows warning
# Features will be limited but API will run
```

### Issue: Port 8000 already in use
```bash
# Solution: Use different port
uvicorn app.main:app --reload --port 8001
```

## Full Development Setup (Optional)

### With All Features:
```bash
# 1. Install all dependencies
./install_dependencies.sh

# 2. Start with Docker (if you have Docker)
docker-compose up

# 3. Or start everything manually
./start_local.sh
```

### With Frontend:
```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend (Next.js)
cd trees/main
npm install
npm run dev
# Frontend at http://localhost:3001
```

## What's Actually Working Now

The migration is **PARTIAL**. Here's the reality:

### ✅ Migrated (30-40%):
- Core business logic services
- Main API endpoints
- WebSocket support
- Authentication framework
- Background tasks setup

### ❌ Not Migrated (60-70%):
- All specialized agent endpoints
- Complex data pipelines
- Streaming endpoints
- Many utility endpoints
- Dashboard-specific APIs

## For Testing/Development

If you just want to test the new FastAPI backend:

```bash
cd backend
source venv/bin/activate
python -c "from app.main import app; print('✅ Backend loads!')"
uvicorn app.main:app --reload
```

Then visit http://localhost:8000/docs to explore available endpoints.

## Summary

**To start localhost:**
1. `cd backend`
2. `source venv/bin/activate`
3. `pip install fastapi uvicorn`
4. `uvicorn app.main:app --reload`
5. Visit http://localhost:8000/docs

The backend will start even without database credentials - it just won't have full functionality.