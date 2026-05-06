@echo off
title Lumen

if not exist app\frontend\dist\index.html (
    echo Building frontend...
    pushd app\frontend
    call npm run build
    popd
)

echo Starting Lumen...
python desktop.py
pause
