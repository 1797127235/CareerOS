# Lumen 启动脚本 (PowerShell)
# 用法: .\start.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ✦ Lumen 桌面应用 ✦" -ForegroundColor Cyan
Write-Host "  ─────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── 检查依赖 ──
$missing = @()

if (-not (Get-Command "cargo" -ErrorAction SilentlyContinue)) { $missing += "Rust (cargo)" }
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) { $missing += "Python" }
if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) { $missing += "Node.js" }

if ($missing.Count -gt 0) {
    Write-Host "  [ERROR] 缺少依赖: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "  Rust:    $(cargo --version)" -ForegroundColor DarkGray
Write-Host "  Python:  $(python --version)" -ForegroundColor DarkGray
Write-Host "  Node:    $(node --version)" -ForegroundColor DarkGray
Write-Host ""

# ── 安装前端依赖（按需）──
if (-not (Test-Path "node_modules")) {
    Write-Host "  [1/2] 安装前端依赖..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "  [1/2] 完成" -ForegroundColor Green
} else {
    Write-Host "  [1/2] 跳过（已安装）" -ForegroundColor DarkGray
}

# ── 启动 ──
Write-Host "  [2/2] 启动 Tauri 桌面应用..." -ForegroundColor Yellow
Write-Host ""
cargo tauri dev
