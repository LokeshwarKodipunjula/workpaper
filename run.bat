@echo off
REM One-shot setup and run on Windows (needs Python 3.11+ and Node 20+ installed).
cd /d "%~dp0"
echo [1/3] Installing backend dependencies...
pip install -r backend\requirements.txt || goto :err
echo [2/3] Building the UI...
cd frontend
call npm install || goto :err
call npm run build || goto :err
cd ..
echo [3/3] Starting the server at http://localhost:8000  (Ctrl+C to stop)
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
goto :eof
:err
echo Setup failed. Check that Python and Node are installed and on PATH.
pause
