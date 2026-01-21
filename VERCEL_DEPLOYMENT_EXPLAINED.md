# Why This Configuration Works (And What Might Be Missing)

## Why The Changes Will Actually Work

### 1. **Root-Level `requirements.txt` is Critical**
**Problem**: Vercel looks for `requirements.txt` at the **project root** (where `vercel.json` is), not in subdirectories.

**Old Setup**:
- `requirements.txt` was in `backend/`
- Vercel couldn't find it → dependencies never installed → deployment fails

**New Setup**:
- `requirements.txt` is at root
- Vercel auto-detects and installs dependencies → deployment works

### 2. **Entry Point Location Matters**
**Old Setup**:
```json
"functions": {
  "api/index.py": { ... }  // Points to /api/index.py
}
```
- This worked, but Vercel's auto-detection prefers root-level files
- The path `api/index.py` requires explicit routing

**New Setup**:
```json
"functions": {
  "index.py": { ... }  // Points to root /index.py
}
```
- Vercel auto-detects `index.py`, `app.py`, or `server.py` at root
- Simpler, more reliable

### 3. **Python Runtime Version**
**Old**: `python3.9` (deprecated, no longer supported)
**New**: `python3.12` (current Vercel default)

If you specify an unsupported runtime, Vercel will fail or fall back unpredictably.

### 4. **File Inclusion/Exclusion**
**Old**: `"includeFiles": "backend/**"` - This pattern might not work correctly
**New**: `"excludeFiles": "{tests/**,frontend/**}"` - Excludes what we don't need

Vercel includes everything by default, so excluding unnecessary files keeps bundle size down (250MB limit).

---

## What About Build Commands?

### **For Most FastAPI Apps: NO Build Command Needed**

Vercel automatically:
1. Detects `requirements.txt` at root
2. Runs `pip install -r requirements.txt` 
3. Deploys your app

**You only need a build command if:**
- You need to compile C extensions (numpy, scipy, pandas do this automatically)
- You need to install system packages
- You need to run setup scripts
- You have custom build steps

### **Potential Issue: Heavy Dependencies**

Your `requirements.txt` includes:
- `numpy>=1.26.4` - Compiles C extensions (Vercel handles this)
- `pandas>=2.2.0` - Compiles C extensions (Vercel handles this)
- `scipy>=1.13.0` - Compiles C extensions (Vercel handles this)
- `playwright==1.40.0` - **⚠️ PROBLEM**: Needs browser binaries (~300MB)

### **Playwright Issue** ⚠️

Playwright is used for **PDF export** (rendering Next.js pages to PDF). The code has **graceful fallbacks**, but:

**The Problem**:
- Playwright browser binaries are ~300MB
- Vercel has a **250MB uncompressed limit** for Python functions
- This will cause deployment to fail or exceed limits

**Your Options**:

**Option 1: Remove Playwright** (PDF export will use fallback method)
```bash
# Comment out in requirements.txt
# playwright==1.40.0
```
The code will fall back to `export_to_pdf_sync()` which uses Chart.js instead of browser rendering.

**Option 2: Add Build Command** (try to install, but may still fail)
Add to `vercel.json`:
```json
{
  "buildCommand": "pip install playwright && playwright install chromium"
}
```
⚠️ This will likely exceed the 250MB limit and fail.

**Option 3: Use External Service** (recommended for production)
- Deploy PDF export to a separate service (AWS Lambda, Railway, etc.)
- Or use a headless browser service (Browserless.io, Puppeteer-as-a-Service)
- Keep main API on Vercel without Playwright

**Recommendation**: Start with Option 1 (remove Playwright) to get deployment working, then add PDF export as a separate service if needed.

**✅ Current Setup**: 
- Playwright is commented out in root `requirements.txt` (for Vercel)
- Playwright code remains intact in `backend/app/services/deck_export_service.py`
- Code has graceful fallbacks: if Playwright unavailable, uses `export_to_pdf_sync()` with Chart.js
- For local development: use `backend/requirements.txt` which includes Playwright

---

## What You Might Still Need

### 1. **Build Command (Only if needed)**

**For most FastAPI apps: NO build command needed.** Vercel auto-installs from `requirements.txt`.

**Only add if:**
- You need to install system packages
- You need to run setup scripts
- You're trying to install Playwright (but this will likely fail due to size)

**How to add** (if needed):
- **Option A**: In Vercel dashboard → Project Settings → Build & Development Settings → Build Command
- **Option B**: In `vercel.json` (at root level, not in `functions`):
```json
{
  "buildCommand": "pip install -r requirements.txt && playwright install chromium"
}
```

**But remember**: Vercel already runs `pip install -r requirements.txt` automatically, so you only need the build command for extra steps.

### 2. **Environment Variables**
Make sure all required env vars are set in Vercel dashboard:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ANTHROPIC_API_KEY`
- etc.

### 3. **Bundle Size Check**
Your dependencies are heavy. Check if total size < 250MB:
```bash
# Test locally
pip install -r requirements.txt
du -sh $(python -m site --user-site)
```

---

## Summary: Why It Works Now

| Issue | Old Config | New Config | Why It Matters |
|-------|-----------|------------|----------------|
| `requirements.txt` location | `backend/` | Root | Vercel can't find it in subdirs |
| Entry point | `api/index.py` | `index.py` | Auto-detection prefers root |
| Python version | `3.9` (deprecated) | `3.12` (current) | Old version not supported |
| File patterns | `includeFiles` | `excludeFiles` | More reliable pattern |

**The main fix**: Moving `requirements.txt` to root is the critical change. Everything else is optimization.

---

## Testing

After deployment, check:
1. `https://your-app.vercel.app/health` - Should return JSON
2. `https://your-app.vercel.app/docs` - Should show Swagger UI
3. Check Vercel build logs for any dependency installation errors

If you see errors about missing dependencies or import failures, the build command might be needed, but start without it first.
