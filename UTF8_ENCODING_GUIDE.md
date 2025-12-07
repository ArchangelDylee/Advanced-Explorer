# UTF-8 인코딩 통합 가이드

Advanced Explorer의 모든 영역에서 UTF-8 인코딩이 올바르게 작동하도록 설정된 내용입니다.

---

## 📋 목차
1. [HTML/Frontend](#1-htmlfrontend)
2. [Electron Main Process](#2-electron-main-process)
3. [Python Backend](#3-python-backend)
4. [파일 시스템 작업](#4-파일-시스템-작업)
5. [데이터베이스](#5-데이터베이스)
6. [로그 파일](#6-로그-파일)
7. [API 통신](#7-api-통신)
8. [터미널 출력](#8-터미널-출력)

---

## 1. HTML/Frontend

### ✅ index.html
```html
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Advanced Explorer</title>
</head>
```

### ✅ TypeScript/React
- 모든 `.tsx`, `.ts` 파일은 UTF-8로 저장
- VSCode/Cursor 설정: `"files.encoding": "utf8"`

---

## 2. Electron Main Process

### ✅ Python 프로세스 spawn 시 환경 변수 설정
**파일**: `electron/main.cjs`

```javascript
pythonProcess = spawn(pythonCmd, [serverScript], {
  cwd: pythonBackendPath,
  env: {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',    // Python 입출력 UTF-8 강제
    PYTHONUTF8: '1',              // Python 3.7+ UTF-8 모드
    LANG: 'ko_KR.UTF-8',          // 로케일 설정
    LC_ALL: 'ko_KR.UTF-8'         // 전체 로케일
  }
});
```

### ✅ stdout/stderr 인코딩
```javascript
pythonProcess.stdout.on('data', (data) => {
  console.log(`[Python] ${data.toString('utf8').trim()}`);
});

pythonProcess.stderr.on('data', (data) => {
  console.error(`[Python Error] ${data.toString('utf8').trim()}`);
});
```

### ✅ 파일 읽기 (텍스트)
```javascript
// 텍스트 파일은 UTF-8로 읽기
const content = await fs.readFile(filePath, 'utf8');

// 바이너리 파일은 그대로
const imageData = await fs.readFile(imagePath); // Buffer
```

---

## 3. Python Backend

### ✅ 전역 UTF-8 설정 (모든 .py 파일 상단)
**파일**: `server.py`, `indexer.py`, `database.py`, `search.py`

```python
# -*- coding: utf-8 -*-

import sys
import io
import ctypes

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)        # 입력 UTF-8
        kernel32.SetConsoleOutputCP(65001)  # 출력 UTF-8
    except Exception:
        pass

# stdout/stderr UTF-8 재설정
try:
    if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding='utf-8', 
            errors='replace', 
            line_buffering=True
        )
except Exception:
    pass

try:
    if hasattr(sys.stderr, 'buffer') and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, 
            encoding='utf-8', 
            errors='replace', 
            line_buffering=True
        )
except Exception:
    pass
```

### ✅ 로케일 설정
```python
import locale
try:
    locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass
```

### ✅ Flask JSON 응답 UTF-8
```python
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 한글 등 유니코드 정상 표시
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
```

---

## 4. 파일 시스템 작업

### ✅ Python 파일 읽기
```python
# 텍스트 파일 읽기 (인코딩 자동 감지)
import chardet

def read_text_file(file_path: str) -> str:
    # 1차: UTF-8 시도
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        pass
    
    # 2차: 인코딩 자동 감지
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            return raw_data.decode(encoding, errors='replace')
    except Exception:
        return None
```

### ✅ 파일 쓰기
```python
# 항상 UTF-8로 저장
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
```

---

## 5. 데이터베이스

### ✅ SQLite 연결 시 UTF-8
```python
import sqlite3

conn = sqlite3.connect('file_index.db')
conn.execute("PRAGMA encoding = 'UTF-8'")
conn.row_factory = sqlite3.Row

# 데이터 삽입
cursor.execute("INSERT INTO files_fts (path, content) VALUES (?, ?)", 
               (path, content))  # Python 문자열은 자동으로 UTF-8
```

### ✅ FTS5 트라이그램 토크나이저
```python
# 다국어 지원 토크나이저 (한글, 영어, 중국어 등)
CREATE VIRTUAL TABLE files_fts USING fts5(
    path UNINDEXED, 
    content, 
    mtime UNINDEXED, 
    tokenize='trigram'  # 문자 단위 검색으로 다국어 지원
)
```

---

## 6. 로그 파일

### ✅ 로깅 UTF-8 설정
```python
import logging

log_file = 'logs/server.log'
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8', mode='a')  # UTF-8 명시
    ]
)

# 핸들러 UTF-8 재확인
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler):
        if hasattr(handler.stream, 'reconfigure'):
            try:
                handler.stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
```

### ✅ 직접 파일 쓰기
```python
# 인덱싱 로그 등
with open(self.indexing_log_file, 'a', encoding='utf-8') as f:
    f.write(f'{timestamp} | {status} | {filename}\n')
```

---

## 7. API 통신

### ✅ Flask → Frontend
```python
from flask import jsonify

@app.route('/api/search', methods=['POST'])
def search():
    # JSON 응답은 자동으로 UTF-8 (app.config['JSON_AS_ASCII'] = False)
    return jsonify({
        'results': [
            {'path': 'C:\\문서\\한글파일.txt', 'content': '안녕하세요'}
        ]
    })
```

### ✅ Frontend → Flask
```typescript
// fetch는 기본적으로 UTF-8
const response = await fetch('http://127.0.0.1:5000/api/search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json; charset=utf-8'
  },
  body: JSON.stringify({ query: '한글검색' })
});

const data = await response.json(); // 자동 UTF-8 디코딩
```

---

## 8. 터미널 출력

### ✅ Windows PowerShell
```powershell
# UTF-8 코드페이지 설정
chcp 65001

# 또는 자동 설정 (Python 환경 변수)
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

### ✅ VSCode/Cursor 터미널 설정
```json
// settings.json
{
  "terminal.integrated.env.windows": {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "files.encoding": "utf8",
  "files.autoGuessEncoding": false
}
```

---

## 📊 인코딩 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│                    사용자 입력 (한글)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │ UTF-8
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              React UI (UTF-8 meta charset)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ fetch (UTF-8 JSON)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         Flask API (JSON_AS_ASCII=False, UTF-8)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ SQLite   │  │ 파일시스템│  │ 로그파일  │
│ (UTF-8)  │  │ (chardet)│  │ (UTF-8)  │
└──────────┘  └──────────┘  └──────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │ UTF-8
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            Electron stdout (toString('utf8'))               │
└─────────────────────┬───────────────────────────────────────┘
                      │ UTF-8
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  터미널 출력 (한글)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ 체크리스트

- [x] HTML meta charset UTF-8
- [x] Python 파일 `# -*- coding: utf-8 -*-` 헤더
- [x] Python sys.stdout/stderr UTF-8 재설정
- [x] Windows 콘솔 SetConsoleCP/OutputCP(65001)
- [x] Flask JSON_AS_ASCII = False
- [x] SQLite UTF-8 인코딩
- [x] 로그 파일 encoding='utf-8'
- [x] Electron spawn env PYTHONIOENCODING
- [x] Electron stdout/stderr toString('utf8')
- [x] chardet로 파일 인코딩 자동 감지
- [x] FTS5 trigram 토크나이저 (다국어 지원)

---

## 🔧 문제 해결

### 터미널에서 한글 깨짐
```powershell
# PowerShell에서 실행
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

### Python 파일 읽기 실패
```python
# chardet 설치
pip install chardet

# 인코딩 자동 감지 사용
import chardet
with open(file_path, 'rb') as f:
    raw = f.read()
    encoding = chardet.detect(raw)['encoding']
    content = raw.decode(encoding, errors='replace')
```

### DB에서 한글 조회 실패
```python
# SQLite 연결 시 UTF-8 명시
conn = sqlite3.connect('file.db')
conn.execute("PRAGMA encoding = 'UTF-8'")
```

---

## 📚 참고 자료

- [Python Unicode HOWTO](https://docs.python.org/3/howto/unicode.html)
- [Flask JSON 인코딩](https://flask.palletsprojects.com/en/2.3.x/config/#JSON_AS_ASCII)
- [SQLite 인코딩](https://www.sqlite.org/pragma.html#pragma_encoding)
- [Node.js Buffer toString](https://nodejs.org/api/buffer.html#buftostringencoding-start-end)

---

**모든 영역에서 UTF-8 기반으로 통일되어 한글 및 다국어가 정상적으로 표시됩니다.** ✅

