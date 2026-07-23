# PowerShell 部署脚本

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== 食刻部署 ===" -ForegroundColor Cyan

# 检查 .env
if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Write-Host "已创建 .env，请填入 API Key 后重新运行" -ForegroundColor Yellow
    exit 1
}

# 数据初始化
Write-Host "导入种子数据..." -ForegroundColor Green
Push-Location "$Root\backend"
pip install -r requirements.txt -q
python -m pipeline.import_data --seed --count 3000
python -m pipeline.ingest --all
Pop-Location

# Docker 启动
Write-Host "启动 Docker 服务..." -ForegroundColor Green
Push-Location $Root
docker compose up -d --build
Pop-Location

Write-Host "部署完成！API: http://localhost:8000/api/health" -ForegroundColor Cyan
