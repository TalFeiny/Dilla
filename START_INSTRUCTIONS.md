# Starting Frontend and Backend Separately

## Quick Start

### Start Backend (Terminal 1)
```bash
./start_backend.sh
```

The backend will start on port **8000** and be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Start Frontend (Terminal 2)
```bash
./start_frontend.sh
```

The frontend will start on port **3001** and be available at:
- Frontend: http://localhost:3001

## Alternative: Using npm scripts

### Start Backend
```bash
npm run dev:backend
```

### Start Frontend
```bash
npm run dev:frontend
```

## Troubleshooting

### Backend Issues
- Make sure you have a virtual environment activated (`venv` or `venv312`)
- Check that port 8000 is not already in use
- Verify Python dependencies are installed: `cd backend && pip install -r requirements.txt`

### Frontend Issues
- Make sure Node.js dependencies are installed: `cd frontend && npm install`
- Check that port 3001 is not already in use
- Clear Next.js cache if needed: `cd frontend && rm -rf .next`

## Viewing Logs

Backend logs will appear in the terminal where you started it.

Frontend logs will appear in the terminal where you started it, and also in the browser console.

## Stopping Services

Press `Ctrl+C` in each terminal to stop the respective service.

