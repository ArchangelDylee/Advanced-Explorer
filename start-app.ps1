# 蹂꾨룄 李쎌뿉???ㅽ뻾
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'cd python-backend; .\venv\Scripts\Activate.ps1; python server.py'
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'npm run dev'
Start-Sleep -Seconds 3
npm run electron
