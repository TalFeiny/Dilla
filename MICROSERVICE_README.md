# VC Platform New Microservice

This directory contains the microservice architecture for the VC Platform, running on port 3001 as requested.

## Architecture Overview

The microservice provides the following components:
- **PWERM7 Analysis**: Probability-Weighted Expected Return Model with 499 scenarios
- **Full Flow Processing**: Complete document processing pipeline
- **KYC Processing**: Know Your Customer document verification
- **Companies Data**: Loading and management of portfolio companies
- **LPs Data**: Loading and management of Limited Partners

## Quick Start

### 1. Start the Microservice

```bash
# From the vc-platform-new directory
./start_microservice.sh
```

Or manually:
```bash
# Activate virtual environment
source ../venv/bin/activate

# Start the service
python ../document_service.py
```

### 2. Test the Service

```bash
# Run comprehensive tests
python test_microservice.py
```

### 3. Health Check

```bash
curl http://localhost:3001/health
```

## Available Endpoints

### Core Processing
- `GET /health` - Service health check
- `POST /process` - Process a single document
- `POST /batch-process` - Process multiple documents

### Data Loading
- `POST /api/companies/load` - Load companies data
- `POST /api/lps/load` - Load Limited Partners data

### Analysis
- `POST /api/pwerm/analyze` - Run PWERM analysis
- `POST /api/kyc/process` - Process KYC documents

## API Examples

### PWERM Analysis
```bash
curl -X POST http://localhost:3001/api/pwerm/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "TechCorp Inc",
    "growth_rate": 75,
    "annual_revenue": 25,
    "scenario_id": "analysis_001"
  }'
```

### Document Processing
```bash
curl -X POST http://localhost:3001/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Document content here...",
    "document_type": "investor_update",
    "filename": "document.pdf"
  }'
```

### Load Companies
```bash
curl -X POST http://localhost:3001/api/companies/load \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Load LPs
```bash
curl -X POST http://localhost:3001/api/lps/load \
  -H "Content-Type: application/json" \
  -d '{}'
```

### KYC Processing
```bash
curl -X POST http://localhost:3001/api/kyc/process \
  -H "Content-Type: application/json" \
  -d '{
    "document_path": "/path/to/kyc/document.pdf"
  }'
```

## File Structure

```
vc-platform-new/
├── services/
│   └── document_service.py          # Main microservice (updated)
├── scripts/
│   ├── pwerm_analysis.py           # PWERM analysis engine
│   ├── pwerm_bridge                # PWERM bridge for Node.js
│   ├── full_flow_no_comp.py        # Full document processing
│   └── kyc_processor.py            # KYC document processing
├── start_microservice.sh           # Startup script
├── test_microservice.py            # Test suite
└── MICROSERVICE_README.md          # This file
```

## Components

### PWERM7 Analysis
- **File**: `scripts/pwerm_analysis.py`
- **Bridge**: `scripts/pwerm_bridge`
- **Features**: 499 discrete scenarios, market research integration, liquidation preference analysis

### Full Flow Processing
- **File**: `scripts/full_flow_no_comp.py`
- **Features**: Complete document analysis pipeline, AI-powered extraction, financial metrics

### KYC Processing
- **File**: `scripts/kyc_processor.py`
- **Features**: Document type detection, entity extraction, risk assessment, compliance scoring

### Companies Data
- **Endpoint**: `/api/companies/load`
- **Features**: Portfolio company management, sector classification, funding stages

### LPs Data
- **Endpoint**: `/api/lps/load`
- **Features**: Limited Partner management, commitment tracking, investment status

## Environment Variables

The service uses the following environment variables:
- `PORT`: Service port (default: 3001)
- `TAVILY_API_KEY`: For market research
- `OPENAI_API_KEY`: For AI analysis
- `NEXT_PUBLIC_SUPABASE_URL`: Supabase connection
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service key

## Troubleshooting

### Port Already in Use
If port 3001 is already in use:
```bash
# Find process using port 3001
lsof -i :3001

# Kill the process
kill -9 <PID>
```

### Service Won't Start
1. Check virtual environment is activated
2. Verify all dependencies are installed
3. Check environment variables are set
4. Review logs for specific errors

### Scripts Not Found
Ensure all scripts are copied to the `scripts/` directory:
```bash
cp -r ../scripts/* scripts/
```

## Integration with Frontend

The microservice is designed to work with the Next.js frontend in `vc-platform-new/src/`. The frontend can make API calls to the microservice endpoints for:

- Document processing and analysis
- PWERM calculations
- KYC verification
- Data loading and management

## Performance Notes

- The service runs on port 3001 as requested
- All Python scripts are executed as subprocesses
- CORS is enabled for frontend integration
- Health checks are available for monitoring
- Comprehensive error handling and logging

## Next Steps

1. **Database Integration**: Connect to Supabase for persistent data
2. **Authentication**: Add API key or JWT authentication
3. **Rate Limiting**: Implement request throttling
4. **Monitoring**: Add metrics and alerting
5. **Scaling**: Consider containerization with Docker 