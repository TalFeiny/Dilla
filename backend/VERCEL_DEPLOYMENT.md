# Vercel Deployment Guide for FastAPI Backend

## Step 1: Set Environment Variables in Vercel Dashboard

Go to your Vercel project → **Settings** → **Environment Variables** and add these:

### Required Variables (Production):
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_service_key
SUPABASE_ANON_KEY=your_anon_key
SECRET_KEY=your_secret_key
ENVIRONMENT=production
DEBUG=False
```

### API Keys (at least one LLM key):
```
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
TAVILY_API_KEY=your_key
FIRECRAWL_API_KEY=your_key
```

### Optional:
```
REDIS_URL=your_redis_url
PRIMARY_EXTRACTION_MODEL=claude-sonnet-4-5
FALLBACK_MODEL_1=gpt-5
FALLBACK_MODEL_2=gpt-5
FALLBACK_MODEL_3=claude-sonnet-4-5
ENABLE_STREAMING=True
ENABLE_WEBSOCKET=True
ENABLE_MULTI_AGENT=True
ENABLE_RL_AGENT=True
```

**Important:** Select **Production** (and optionally **Preview**) when adding each variable.

## Step 2: Deploy to Vercel

1. Make sure you're in the `backend` directory
2. Run: `vercel --prod`
3. Or connect your GitHub repo to Vercel and it will auto-deploy

## Step 3: Verify Deployment

After deployment, check:
- `https://your-project.vercel.app/health` - Should return health status
- `https://your-project.vercel.app/docs` - Should show Swagger docs

## Troubleshooting

If deployment fails:
1. Check Vercel build logs
2. Ensure all environment variables are set
3. Make sure `ENVIRONMENT=production` and `DEBUG=False` are set
4. Check that `mangum` is in `requirements.txt`
