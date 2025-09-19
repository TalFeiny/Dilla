# Dilla AI - Realistic Architecture Assessment
## Version 2.0 - August 2025

## Executive Summary

Dilla AI is a VC platform that has undergone partial migration from Next.js API routes to FastAPI backend. While core functionality exists, the system currently operates at **60% integration** due to significant code duplication from non-modular design patterns. Agents were built by copying reference code rather than creating reusable modules, resulting in 40% code duplication across the codebase.

## Architecture Components

### 1. Frontend - Next.js Application
**Location:** `/frontend/`

#### Structure:
```
frontend/
├── src/
│   ├── app/                    # App router pages
│   ├── components/             # Reusable React components
│   │   ├── ui/                # UI components
│   │   ├── features/          # Feature-specific components
│   │   └── layouts/           # Layout components
│   ├── lib/                   # Utility functions
│   │   ├── api/              # API client functions
│   │   ├── hooks/            # Custom React hooks
│   │   └── utils/            # Helper functions
│   ├── styles/               # Global styles
│   └── types/                # TypeScript type definitions
├── public/                   # Static assets
├── tests/                    # Frontend tests
├── next.config.mjs
├── package.json
├── tsconfig.json
└── .env.local

```

#### Key Features:
- Server-side rendering (SSR) and static generation
- API routes removed (all APIs handled by FastAPI)
- Environment variables for API endpoints
- TypeScript for type safety
- Tailwind CSS for styling

### 2. Backend - FastAPI Service
**Location:** `/backend/`

#### Structure:
```
backend/
├── app/
│   ├── api/
│   │   ├── endpoints/         # API endpoints
│   │   │   ├── agents.py
│   │   │   ├── companies.py
│   │   │   ├── documents.py
│   │   │   ├── market_research.py
│   │   │   └── portfolio.py
│   │   ├── router.py          # Main API router
│   │   └── deps.py           # Dependencies
│   ├── core/
│   │   ├── config.py         # Configuration
│   │   ├── security.py       # Authentication/Authorization
│   │   └── database.py       # Database connection
│   ├── models/               # Pydantic models
│   │   ├── agent.py
│   │   ├── company.py
│   │   ├── document.py
│   │   └── user.py
│   ├── schemas/              # Request/Response schemas
│   ├── services/             # Business logic
│   │   ├── agent_service.py
│   │   ├── market_analysis.py
│   │   ├── pwerm_service.py
│   │   └── tavily_service.py
│   ├── utils/               # Utility functions
│   └── main.py              # FastAPI application
├── alembic/                 # Database migrations (if needed alongside Supabase)
├── tests/                   # Backend tests
├── requirements.txt
├── Dockerfile
└── .env
```

#### Key Features:
- RESTful API design
- Async/await for performance
- Pydantic for data validation
- JWT authentication
- CORS configuration
- OpenAPI documentation
- Background tasks for long-running operations

### 3. Database - Supabase
**Location:** `/supabase/`

#### Structure:
```
supabase/
├── migrations/              # SQL migration files
│   ├── 20250118_001_initial_schema.sql
│   ├── 20250118_002_auth_tables.sql
│   ├── 20250118_003_core_tables.sql
│   ├── 20250118_004_indexes.sql
│   └── 20250118_005_rls_policies.sql
├── functions/              # Edge functions
│   ├── process-document/
│   └── market-analysis/
├── seed/                   # Seed data
│   ├── development.sql
│   └── test.sql
├── config.toml            # Supabase configuration
└── .env.local
```

#### Core Tables:
- **profiles** - Extended user profiles (linked to Supabase Auth)
- **companies** - Company information and metadata
- **documents** - Uploaded documents with embeddings
- **market_research** - Market analysis and research data
- **agent_runs** - AI agent execution history
- **portfolio** - Investment portfolio tracking
- **audit_log** - Change tracking for compliance

#### Key Features:
- Row Level Security (RLS) on all tables
- Vector embeddings for semantic search
- JSONB fields for flexible metadata
- Automatic updated_at timestamps
- Full-text search indexes

## Migration Strategy

### Phase 1: Database Migration Setup
1. Create migration files for all existing tables
2. Set up Row Level Security (RLS) policies
3. Create necessary indexes and constraints
4. Set up database functions and triggers

### Phase 2: Backend Development
1. Set up FastAPI project structure
2. Migrate API endpoints from Next.js API routes
3. Implement authentication/authorization
4. Create service layer for business logic
5. Set up background tasks for agents

### Phase 3: Frontend Refactoring
1. Remove API routes from Next.js
2. Create API client library
3. Update components to use new API endpoints
4. Implement proper error handling
5. Set up authentication flow

### Phase 4: Infrastructure
1. Dockerize backend service
2. Set up environment configurations
3. Configure CI/CD pipelines
4. Set up monitoring and logging

## API Specification

### Authentication
- JWT-based authentication
- Refresh token mechanism
- Supabase Auth integration

### Endpoints Structure
```
/api/
├── /auth
│   ├── POST /login
│   ├── POST /logout
│   ├── POST /refresh
│   └── POST /register
├── /users
│   ├── GET /me
│   └── PATCH /me
├── /companies
│   ├── GET /
│   ├── POST /
│   ├── GET /{id}
│   ├── PATCH /{id}
│   └── DELETE /{id}
├── /documents
│   ├── POST /upload
│   ├── GET /{id}
│   └── POST /{id}/analyze
├── /market-research
│   ├── POST /analyze
│   ├── GET /reports
│   └── GET /reports/{id}
├── /agents
│   ├── POST /run
│   ├── GET /runs
│   └── GET /runs/{id}/status
└── /portfolio
    ├── GET /
    └── POST /analyze
```

### API Versioning Strategy
Since we're pre-launch with no external API consumers, we're starting without version prefixes (`/v1`) to keep development simple and fast. Versioning will be added when:
- We have external API consumers
- We need to make breaking changes post-launch
- We need to support multiple client versions simultaneously

When versioning is needed, we can either:
1. Add URL versioning (`/api/v2/...`)
2. Use header-based versioning (`Accept: application/vnd.dilla.v2+json`)
3. Support both old and new endpoints during transition

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

### Backend (.env)
```
DATABASE_URL=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
JWT_SECRET=
TAVILY_API_KEY=
OPENAI_API_KEY=
REDIS_URL=
```

## Development Workflow

### Local Development
1. Start Supabase local instance
2. Run database migrations
3. Start FastAPI backend
4. Start Next.js frontend

### Commands
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Database
supabase start
supabase migration up
```

## Testing Strategy

### Unit Tests
- Frontend: Jest + React Testing Library
- Backend: Pytest

### Integration Tests
- API endpoint testing
- Database operation testing

### E2E Tests
- Playwright for full user flows

## Deployment

### Production Architecture
```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Vercel    │────▶│   FastAPI    │────▶│  Supabase  │
│  (Next.js)  │     │   (Cloud Run)│     │ (Postgres) │
└─────────────┘     └──────────────┘     └────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │    Redis     │
                    │   (Cache)    │
                    └──────────────┘
```

## Security Considerations

1. API rate limiting
2. Input validation
3. SQL injection prevention
4. XSS protection
5. CORS configuration
6. Environment variable management
7. Secrets rotation

## Monitoring & Observability

1. Application metrics (Prometheus)
2. Error tracking (Sentry)
3. Logging (structured JSON logs)
4. Performance monitoring
5. Database query monitoring
