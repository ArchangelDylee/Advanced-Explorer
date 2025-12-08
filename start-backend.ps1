# UTF-8 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

# 가상환경 활성화 및 서버 시작
cd python-backend
& .\venv\Scripts\Activate.ps1
python server.py

