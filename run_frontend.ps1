# run_frontend.ps1
# 휴대용 Node.js를 이용해 Next.js 프론트엔드를 실행합니다.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$NodePath = Join-Path $ScriptDir "node_portable\node-v22.14.0-win-x64"

# 환경 변수에 휴대용 Node 경로 추가
$env:PATH = "$NodePath;" + $env:PATH

cd frontend
Write-Host "✅ Starting Next.js Frontend Server..." -ForegroundColor Green
npm run dev
