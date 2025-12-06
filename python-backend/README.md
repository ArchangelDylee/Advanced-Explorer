# Python 백엔드 인덱싱 엔진

로컬 파일 인덱싱 & 전문 검색 엔진 (SQLite FTS5 기반)

## 🚀 기능

- **고속 전문 검색**: SQLite FTS5 + trigram 토크나이저로 한국어 검색 최적화
- **비동기 인덱싱**: Worker 쓰레드를 사용한 UI 블로킹 없는 처리
- **증분 인덱싱**: 수정된 파일만 재인덱싱하여 성능 최적화
- **다양한 파일 형식 지원**: TXT, DOCX, PPTX, PDF 등
- **REST API**: Electron 앱과 Flask API로 통신

## 📋 시스템 요구사항

- Python 3.8 이상
- Windows 10/11
- SQLite 3.35 이상 (FTS5 지원)

## 🔧 설치

### 1. 가상 환경 생성 (권장)

```bash
cd python-backend
python -m venv venv
```

### 2. 가상 환경 활성화

**Windows (PowerShell):**
```bash
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```bash
.\venv\Scripts\activate.bat
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

## 🏃 실행

### 개발 모드

```bash
python server.py
```

서버가 `http://127.0.0.1:5000`에서 실행됩니다.

### 프로덕션 모드

```bash
# Gunicorn 사용 (Linux/Mac)
gunicorn -w 4 -b 127.0.0.1:5000 server:app

# Waitress 사용 (Windows)
pip install waitress
waitress-serve --host=127.0.0.1 --port=5000 server:app
```

## 📡 API 엔드포인트

### 1. 서버 상태 확인

```http
GET /api/health
```

**응답:**
```json
{
  "status": "ok",
  "message": "Python backend is running"
}
```

### 2. 인덱싱 시작

```http
POST /api/indexing/start
Content-Type: application/json

{
  "paths": ["C:\\Users\\dylee\\Documents", "C:\\Users\\dylee\\Desktop"]
}
```

**응답:**
```json
{
  "status": "started",
  "message": "인덱싱이 시작되었습니다."
}
```

### 3. 인덱싱 상태 조회

```http
GET /api/indexing/status
```

**응답:**
```json
{
  "is_running": true,
  "stats": {
    "total_files": 1000,
    "indexed_files": 500,
    "skipped_files": 300,
    "error_files": 200,
    "start_time": 1234567890.0,
    "end_time": null
  }
}
```

### 4. 인덱싱 중지

```http
POST /api/indexing/stop
```

### 5. 파일 검색

```http
POST /api/search
Content-Type: application/json

{
  "query": "Python 프로그래밍",
  "max_results": 100,
  "include_content": true
}
```

**응답:**
```json
{
  "query": "Python 프로그래밍",
  "count": 15,
  "results": [
    {
      "path": "C:\\Users\\dylee\\Documents\\tutorial.txt",
      "name": "tutorial.txt",
      "directory": "C:\\Users\\dylee\\Documents",
      "extension": ".txt",
      "size": 12345,
      "mtime": "1234567890.0",
      "rank": -0.5,
      "preview": "...Python 프로그래밍 기초...",
      "highlight": [
        {"start": 10, "end": 25, "text": "Python 프로그래밍"}
      ]
    }
  ]
}
```

### 6. 통계 조회

```http
GET /api/statistics
```

**응답:**
```json
{
  "total_indexed_files": 1000,
  "database_size": 52428800
}
```

### 7. 데이터베이스 초기화

```http
POST /api/database/clear
```

### 8. 데이터베이스 최적화

```http
POST /api/database/optimize
```

### 9. 검색 히스토리 조회

```http
GET /api/search-history?limit=10
```

**응답:**
```json
{
  "count": 3,
  "history": [
    {
      "keyword": "Python 프로그래밍",
      "last_used": 1234567890.0
    },
    {
      "keyword": "인덱싱",
      "last_used": 1234567880.0
    }
  ]
}
```

### 10. 특정 검색어 삭제

```http
DELETE /api/search-history
Content-Type: application/json

{
  "keyword": "Python 프로그래밍"
}
```

### 11. 모든 검색 히스토리 삭제

```http
POST /api/search-history/clear
```

### 12. 데이터베이스 VACUUM

```http
POST /api/database/vacuum
```

**응답:**
```json
{
  "status": "vacuumed",
  "message": "데이터베이스 단편화가 제거되었습니다."
}
```

**설명:** DELETE/INSERT로 인한 DB 단편화를 제거하고 용량을 최적화합니다.

### 13. 사용자 정의 제외 패턴 조회

```http
GET /api/exclusion-patterns
```

**응답:**
```json
{
  "count": 2,
  "patterns": [
    "C:\\SecureFolder\\*",
    "*/private/*"
  ]
}
```

### 14. 사용자 정의 제외 패턴 추가

```http
POST /api/exclusion-patterns
Content-Type: application/json

{
  "pattern": "C:\\SecureFolder\\*"
}
```

**패턴 예시:**
- `C:\\SecureFolder\\*` - 특정 폴더 전체 제외
- `*/private/*` - 모든 private 폴더 제외
- `*\\confidential\\*` - confidential 폴더 제외

### 15. 사용자 정의 제외 패턴 제거

```http
DELETE /api/exclusion-patterns
Content-Type: application/json

{
  "pattern": "C:\\SecureFolder\\*"
}
```

### 16. 모든 사용자 정의 제외 패턴 삭제

```http
POST /api/exclusion-patterns/clear
```

## 🏗️ 아키텍처

```
python-backend/
├── database.py        # SQLite FTS5 데이터베이스 관리
├── indexer.py         # 파일 크롤링 & 텍스트 추출 (비동기)
├── search.py          # 전문 검색 엔진
├── server.py          # Flask REST API 서버
├── requirements.txt   # Python 의존성
└── file_index.db      # SQLite 데이터베이스 (자동 생성)
```

## 📊 데이터베이스 스키마

### files_fts (FTS5 Virtual Table)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| path | TEXT (UNINDEXED) | 파일 절대 경로 |
| content | TEXT | 파일 텍스트 내용 (검색 대상) |
| mtime | TEXT (UNINDEXED) | 마지막 수정 시간 |

**토크나이저:** `trigram` (한국어 검색 최적화)

### search_history (Table)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| keyword | TEXT (PRIMARY KEY) | 검색어 |
| last_used | REAL | 마지막 검색 시간 (UNIX timestamp) |

최근 검색어를 저장하여 자동완성 및 검색 기록 제공

## 🔗 Electron 통합

### Electron Main Process에서 호출

```javascript
// electron/main.cjs
const { spawn } = require('child_process');
const path = require('path');

// Python 백엔드 시작
function startPythonBackend() {
  const pythonPath = path.join(__dirname, '../python-backend/venv/Scripts/python.exe');
  const scriptPath = path.join(__dirname, '../python-backend/server.py');
  
  const pythonProcess = spawn(pythonPath, [scriptPath]);
  
  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python: ${data}`);
  });
  
  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python Error: ${data}`);
  });
  
  return pythonProcess;
}

// 앱 시작 시 Python 백엔드 실행
app.whenReady().then(() => {
  const pythonBackend = startPythonBackend();
  
  // 앱 종료 시 Python 프로세스도 종료
  app.on('before-quit', () => {
    pythonBackend.kill();
  });
});
```

### React에서 API 호출

```typescript
// src/api/backend.ts
const API_BASE_URL = 'http://127.0.0.1:5000/api';

export async function startIndexing(paths: string[]) {
  const response = await fetch(`${API_BASE_URL}/indexing/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths })
  });
  return response.json();
}

export async function searchFiles(query: string) {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_results: 100, include_content: true })
  });
  return response.json();
}
```

## 🧪 테스트

각 모듈별 테스트:

```bash
# 데이터베이스 테스트
python database.py

# 인덱서 테스트
python indexer.py

# 검색 엔진 테스트
python search.py
```

## 📝 지원 파일 형식

### 텍스트 파일
- `.txt`, `.log`, `.md` - UTF-8 → CP949 → chardet 순서로 인코딩 자동 감지
- 소스 코드: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.cpp`, `.c`, `.h`, `.cs`
- 마크업/데이터: `.json`, `.xml`, `.html`, `.css`, `.yaml`, `.yml`
- 스크립트: `.sql`, `.sh`, `.bat`, `.ps1`

### Microsoft Office 문서
- **Word**: `.docx` (python-docx), `.doc` (pywin32 COM)
- **PowerPoint**: `.pptx` (python-pptx), `.ppt` (pywin32 COM)
- **Excel**: `.xlsx` (openpyxl), `.xls` (pywin32 COM)

### 기타 문서
- **PDF**: `.pdf` (PyMuPDF/fitz - 고속 처리)
- **HWP**: `.hwp` (pywin32 COM 또는 olefile)

## 🚫 제외 규칙 (Exclusion Rules)

### 제외되는 폴더
- **개발 관련**: `.git`, `node_modules`, `venv`, `env`, `__pycache__`, `dist`, `build`, `out`, `target`
- **IDE/에디터**: `.vscode`, `.idea`, `.cache`
- **패키지 관리**: `vendor`, `packages`, `bower_components`
- **프레임워크**: `.next`, `.nuxt`

### 제외되는 파일
- **시스템 파일**: `desktop.ini`, `thumbs.db`, `.DS_Store`
- **Office 임시**: `~$` 또는 `~WRL`로 시작하는 파일
- **Git 설정**: `.gitignore`, `.gitattributes`

### 제외되는 확장자
- **실행파일**: `.exe`, `.dll`, `.sys`, `.bin`, `.so`
- **바이너리**: `.o`, `.obj`, `.class`, `.pyc`, `.pyo`
- **압축파일**: `.zip`, `.rar`, `.7z`, `.tar`, `.gz`
- **미디어**: `.mp3`, `.mp4`, `.avi`, `.jpg`, `.png`
- **폰트**: `.ttf`, `.otf`, `.woff`

### 제외되는 시스템 경로
- `C:\Windows`
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\ProgramData`
- `C:\$Recycle.Bin`
- `C:\System Volume Information`
- `C:\Recovery`

## 📄 파일 파싱 상세

### 인코딩 처리 (.txt)
1. **UTF-8** 시도
2. **CP949** 시도 (한글 Windows 기본)
3. **chardet** 자동 감지
4. 최종: UTF-8 (errors='ignore')

### COM 객체 사용 (.doc, .ppt, .xls, .hwp)
- Windows 전용 (pywin32 필요)
- 백그라운드 스레드에서 `CoInitialize()` 필수
- Microsoft Office 또는 HWP가 설치되어 있어야 함

### Excel 처리 (.xlsx)
- `data_only=True`: 수식 제외, 값만 추출
- 모든 시트 순회하여 데이터 추출

### PDF 처리
- **PyMuPDF (fitz)** 사용
- 기존 PyPDF2/pdfplumber보다 월등히 빠름
- 최대 100페이지까지 추출

### HWP 처리
1. **1차**: pywin32 COM 객체 (가장 정확)
   - HWP 프로그램 설치 필요
2. **2차**: olefile 라이브러리 (제한적)
   - PrvText 스트림에서 미리보기 텍스트 추출
   - UTF-16LE 디코딩

## 🔒 예외 처리 및 안정성

### Skip Logic (skipcheck.txt)

다음 조건에서 파일을 건너뛰고 로그를 남깁니다:

1. **암호화된 파일** - 비밀번호 보호된 문서
2. **파일 잠금** - 다른 프로그램에서 사용 중 (PermissionError)
3. **용량 초과** - 100MB 이상 파일 (OOM 방지)
4. **타임아웃** - 파싱 시간 60초 초과
5. **손상된 파일** - 헤더 손상 또는 읽을 수 없는 파일

**로그 형식:** `[Timestamp] Path : Reason`

**위치:** `python-backend/logs/skipcheck.txt`

### Error Logging (error.txt)

치명적 오류 발생 시 트레이스백을 포함한 상세 로그를 기록합니다.

**위치:** `python-backend/logs/error.txt`

### 팝업 방지

- COM 객체 사용 시 `Visible=False`, `DisplayAlerts=False` 설정
- 오피스 창이나 경고 팝업 최대한 억제
- 타임아웃으로 멈춤 방지

## 🔄 증분 색인 (Incremental Indexing)

### 시작 시 로직

1. **New Files** - DB에 없는 파일 → 파싱 후 INSERT
2. **Modified Files** - mtime 변경 감지 → 재파싱 후 UPDATE
3. **Unchanged Files** - mtime 동일 → SKIP (성능 최적화)

### 종료 시 로직

1. **Deleted Files** - 디스크에 없지만 DB에 있음 → DELETE
2. **VACUUM** - DB 단편화 제거 및 용량 최적화

이를 통해 반복 인덱싱 시 변경된 파일만 처리하여 속도를 대폭 향상시킵니다.

## 📊 실시간 로그

인덱싱 중 다음 정보를 실시간으로 제공합니다:

- **[Success]** filename (1500 chars)
- **[Skip]** filename (Password Protected)
- **[Error]** filename (Corrupted)

## ⚠️ 주의사항

1. **대용량 파일**: 100MB 이상은 자동으로 스킵됩니다.
2. **특수 문자**: `.`, `$`, `~`, `#` 등으로 시작하는 파일/폴더는 자동 제외됩니다.
3. **인코딩**: UTF-8 → CP949 → chardet 순서로 시도하여 정확도 향상.
4. **COM 객체**: `.doc`, `.ppt`, `.xls`, `.hwp`는 해당 프로그램 설치 필요.
5. **pywin32**: Windows 전용, Linux/Mac에서는 COM 파일 지원 불가.
6. **타임아웃**: 파싱 시간 60초 제한으로 무한 대기 방지.

## 🔮 향후 개발 계획

- [ ] WebSocket을 통한 실시간 진행 상황 업데이트
- [x] HWP 파일 지원 (COM/olefile)
- [x] 다양한 Office 문서 형식 지원 (.doc, .ppt, .xls)
- [ ] 파일 형식별 필터링
- [ ] 날짜 범위 검색
- [ ] 고급 쿼리 문법 (AND, OR, NOT)
- [ ] 검색 결과 캐싱
- [ ] OCR 기능 (이미지 내 텍스트 추출)

## 📄 라이선스

MIT License

