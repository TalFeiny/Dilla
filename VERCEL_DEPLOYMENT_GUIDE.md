# Vercel Deployment Guide for Monorepo (Next.js + FastAPI)

## The Problem
You have a monorepo with:
- **Frontend**: Next.js in `frontend/` directory
- **Backend**: FastAPI in `backend/` directory

Vercel needs to know which one to deploy and how to route requests.

## Solution Options

### Option 1: Deploy Backend Only (Current Setup) ✅
If you're deploying **just the FastAPI backend** to Vercel:

1. **Root-level entrypoint**: `/api/index.py` (already created)
2. **Root-level vercel.json**: Routes `/api/*` to FastAPI
3. **Root-level pyproject.toml**: Alternative entrypoint method

**Configuration**: The current `vercel.json` is set up for this.

**To deploy**:
```bash
# From root directory
vercel --prod
```

**Note**: Vercel will detect Python files and deploy as a Python project. The frontend directory will be ignored.

---

### Option 2: Deploy Frontend Only
If you're deploying **just the Next.js frontend**:

1. In Vercel dashboard, set **Root Directory** to `frontend`
2. Or create `frontend/vercel.json` with Next.js config
3. Backend should be deployed separately (different Vercel project or different platform)

---

### Option 3: Deploy Both (Recommended for Production)
**Best approach**: Two separate Vercel projects

#### Project 1: Frontend (Next.js)
- **Root Directory**: `frontend`
- **Build Command**: `npm install && npm run build`
- **Output Directory**: `.next`

#### Project 2: Backend (FastAPI)
- **Root Directory**: (root of repo)
- **Build Command**: `cd backend && pip install -r requirements.txt`
- **API Routes**: `/api/*` → FastAPI

Then configure frontend to call backend:
```env
NEXT_PUBLIC_BACKEND_URL=https://your-backend-project.vercel.app
```

---

## Current Setup (Backend Only)

The files configured:
- ✅ `/index.py` - Root-level FastAPI entrypoint (Vercel auto-detects this)
- ✅ `/vercel.json` - Modern configuration with Python 3.12 runtime
- ✅ `/requirements.txt` - Root-level dependencies (copied from backend/)
- ✅ `/pyproject.toml` - Entry point reference to `index:app`

**Configuration Details:**
- Uses Python 3.12 runtime (Vercel's current default)
- Routes all requests to `index.py` at root
- Excludes test files and frontend directory from bundle
- Memory: 1024MB, Max Duration: 60 seconds
- **Playwright excluded**: Root `requirements.txt` has Playwright commented out (browser binaries exceed 250MB limit)
  - PDF export will use fallback Chart.js rendering (code has graceful fallbacks)
  - For local dev with Playwright: use `backend/requirements.txt`

**This setup will work for deploying the backend only.**

The Next.js frontend in `frontend/` will be ignored by Vercel when deploying from root with Python files detected.
