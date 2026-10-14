@echo off
echo ========================================================
echo Starting FinReq AI Requirement Engineer on Localhost
echo ========================================================

echo 1. Starting Backend on http://127.0.0.1:8000 ...
start "FinReq Backend" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo 2. Starting Frontend on http://localhost:5173 ...
start "FinReq Frontend" cmd /k "cd frontend && npm run dev"

echo ========================================================
echo Services launched!
echo Frontend UI:     http://localhost:5173
echo Backend Swagger: http://127.0.0.1:8000/docs
echo Ollama LLM:      http://127.0.0.1:11434
echo ========================================================
pause
