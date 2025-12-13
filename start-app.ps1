# Advanced Explorer 실행 스크립트
# Python 백엔드와 Vite를 별도 창에서 실행

# UTF-8 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Advanced Explorer 시작 ===" -ForegroundColor Cyan

# 1. Python 백엔드 실행 (별도 PowerShell 창)
Write-Host "1. Python 백엔드 시작..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$OutputEncoding = [System.Text.Encoding]::UTF8; cd 'c:\Users\dylee\Desktop\Advanced Explorer\python-backend'; Write-Host 'Python 백엔드 시작 중...' -ForegroundColor Green; .\venv\Scripts\python.exe server.py"
)
Start-Sleep -Seconds 5

# 2. Vite 개발 서버 실행 (별도 PowerShell 창)
Write-Host "2. Vite 개발 서버 시작..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; `$OutputEncoding = [System.Text.Encoding]::UTF8; cd 'c:\Users\dylee\Desktop\Advanced Explorer'; Write-Host 'Vite 개발 서버 시작 중...' -ForegroundColor Cyan; npm run dev"
)
Start-Sleep -Seconds 8

# 3. Electron 실행 (현재 창)
Write-Host "3. Electron 애플리케이션 시작..." -ForegroundColor Green
npm run electron
