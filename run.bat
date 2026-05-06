@echo off
title Lumen Dev

echo [1/3] Checking Python deps...
pip install -r requirements.txt -q
echo  OK

echo [2/3] Checking Frontend deps...
if not exist "app\frontend\node_modules" (
    pushd app\frontend
    call npm install
    popd
)
echo  OK

echo [3/3] Starting servers...
echo.
echo   Backend  -> http://localhost:8000/docs
echo   Frontend -> http://localhost:5173
echo.

start "Lumen Backend" powershell -NoExit -Command "cd '%~dp0'; python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload"
start "Lumen Frontend" powershell -NoExit -Command "cd '%~dp0\app\frontend'; npm run dev"
