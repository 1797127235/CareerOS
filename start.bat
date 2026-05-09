@echo off
title Lumen
echo.
echo   Lumen Desktop
echo   -------------
echo.

where cargo >nul 2>nul || (echo [ERROR] Rust (cargo) not found & exit /b 1)
where python >nul 2>nul || (echo [ERROR] Python not found & exit /b 1)
where node >nul 2>nul || (echo [ERROR] Node.js not found & exit /b 1)

if not exist "node_modules\" (
    echo [1/2] Installing npm dependencies...
    call npm install
    if %errorlevel% neq 0 exit /b %errorlevel%
    echo [1/2] Done
) else (
    echo [1/2] Skipped (already installed)
)

echo [2/2] Starting Tauri...
echo.
cargo tauri dev
