# Advanced Explorer - 설치 및 실행 가이드

## 📋 시스템 요구사항

- **Node.js**: 16.x 이상
- **Python**: 3.8 이상
- **OS**: Windows 10/11
- **SQLite**: 3.35 이상 (FTS5 지원)

## 🚀 설치 방법

### 1. 프로젝트 클론

```bash
git clone https://github.com/ArchangelDylee/Advanced-Explorer.git
cd Advanced-Explorer
```

### 2. Node.js 의존성 설치

```bash
npm install
```

### 3. Python 백엔드 설정

#### 3.1. 가상 환경 생성

```bash
cd python-backend
python -m venv venv
```

#### 3.2. 가상 환경 활성화

**PowerShell:**
```bash
.\venv\Scripts\Activate.ps1
```

**CMD:**
```bash
.\venv\Scripts\activate.bat
```

#### 3.3. Python 의존성 설치

```bash
pip install -r requirements.txt
```

#### 3.4. 백엔드 테스트 (선택사항)

```bash
python database.py    # 데이터베이스 테스트
python indexer.py     # 인덱서 테스트
python search.py      # 검색 엔진 테스트
```

### 4. 프로젝트 루트로 이동

```bash
cd ..
```

## 🏃 실행 방법

### 개발 모드

2개의 터미널이 필요합니다:

#### 터미널 1: Vite 개발 서버

```bash
npm run dev
```

#### 터미널 2: Electron 앱

```bash
npm run electron
```

**또는** 한 번에 실행 (권장):

```bash
npm run electron:dev
```

> Python 백엔드는 Electron 앱이 시작될 때 자동으로 실행됩니다.

### 프로덕션 빌드

```bash
npm run build
npm run electron
```

## 🔧 개발 환경 설정

### Python 백엔드 독립 실행 (디버깅용)

```bash
cd python-backend
.\venv\Scripts\Activate.ps1
python server.py
```

서버가 `http://127.0.0.1:5000`에서 실행됩니다.

### API 테스트

```bash
# 서버 상태 확인
curl http://127.0.0.1:5000/api/health

# 인덱싱 시작
curl -X POST http://127.0.0.1:5000/api/indexing/start ^
  -H "Content-Type: application/json" ^
  -d "{\"paths\": [\"C:\\Users\\dylee\\Documents\"]}"

# 검색
curl -X POST http://127.0.0.1:5000/api/search ^
  -H "Content-Type: application/json" ^
  -d "{\"query\": \"test\", \"max_results\": 10}"
```

## 📦 프로젝트 구조

```
Advanced-Explorer/
├── electron/              # Electron 메인 프로세스
│   ├── main.cjs          # 앱 진입점
│   └── preload.cjs       # Preload 스크립트
├── python-backend/        # Python 백엔드
│   ├── venv/             # 가상 환경 (생성 필요)
│   ├── database.py       # SQLite FTS5 DB 관리
│   ├── indexer.py        # 파일 인덱싱 엔진
│   ├── search.py         # 검색 엔진
│   ├── server.py         # Flask API 서버
│   ├── requirements.txt  # Python 의존성
│   └── README.md         # 백엔드 상세 문서
├── src/                  # React 프론트엔드
│   ├── App.tsx           # 메인 컴포넌트
│   ├── api/
│   │   └── backend.ts    # Python API 클라이언트
│   └── main.tsx          # React 진입점
├── package.json
└── vite.config.ts
```

## 🔍 주요 기능

### 1. 파일 탐색기
- 실제 컴퓨터의 모든 드라이브 및 폴더 표시
- 재귀적 폴더 탐색
- 특수 문자로 시작하는 파일/폴더 자동 필터링

### 2. 파일 인덱싱
- 비동기 백그라운드 인덱싱
- 증분 인덱싱 (수정된 파일만 재인덱싱)
- 지원 형식:
  - 텍스트: TXT, MD, 소스 코드 (UTF-8/CP949/chardet 자동 감지)
  - Office: DOCX, DOC, PPTX, PPT, XLSX, XLS
  - 문서: PDF (PyMuPDF 고속 처리), HWP
  - 기타: JSON, XML, HTML, YAML 등

### 3. 전문 검색
- SQLite FTS5 + trigram 토크나이저
- 한국어 검색 최적화
- 검색어 하이라이트 및 미리보기

## ⚙️ 설정

### 검색 인덱스 초기화

```bash
# Python 백엔드 서버 실행 후
curl -X POST http://127.0.0.1:5000/api/database/clear
```

### 인덱싱할 경로 설정

앱 내에서 "색인" 탭의 "시작" 버튼을 클릭하여 인덱싱할 폴더를 지정합니다.

## 🐛 문제 해결

### Python 백엔드가 시작되지 않음

1. Python이 설치되어 있는지 확인:
   ```bash
   python --version
   ```

2. 가상 환경이 활성화되어 있는지 확인

3. 의존성이 설치되어 있는지 확인:
   ```bash
   pip list
   ```

### "Module not found" 오류

```bash
cd python-backend
pip install -r requirements.txt
```

### pywin32 설치 오류 (Windows)

pywin32가 제대로 설치되지 않으면:

```bash
pip install --upgrade pywin32
python [Python경로]\Scripts\pywin32_postinstall.py -install
```

예: `python C:\Users\dylee\AppData\Local\Programs\Python\Python311\Scripts\pywin32_postinstall.py -install`

### COM 객체 사용 불가 (.doc, .hwp 등)

- Microsoft Office 또는 HWP가 설치되어 있어야 함
- 해당 프로그램이 없으면 COM 파일은 스킵됨
- .docx, .pptx, .xlsx는 프로그램 없이도 작동함

### 포트 충돌 (5000번 포트)

`python-backend/server.py`에서 포트 변경:
```python
run_server(host='127.0.0.1', port=5001, debug=True)
```

그리고 `src/api/backend.ts`에서도 포트 변경:
```typescript
const API_BASE_URL = 'http://127.0.0.1:5001/api';
```

### SQLite FTS5 지원 확인

```bash
python
>>> import sqlite3
>>> sqlite3.sqlite_version
'3.35.0'  # 3.35 이상이어야 함
```

## 📝 개발 참고사항

### 코드 수정 시 자동 새로고침

- **React**: Vite가 자동으로 Hot Module Replacement (HMR) 적용
- **Electron Main**: 수동으로 재시작 필요
- **Python**: Flask debug 모드에서 자동 재시작

### 로그 확인

- **Electron**: DevTools 콘솔 (Ctrl+Shift+I)
- **Python**: 터미널에서 실시간 로그 출력
- **Vite**: 브라우저 콘솔

## 🔐 보안

- Python 백엔드는 `127.0.0.1`에서만 접근 가능
- CORS는 모든 출처 허용 (개발용, 프로덕션에서는 제한 필요)
- 파일 시스템 접근은 Electron의 contextIsolation으로 보호

## 📄 라이선스

MIT License

## 🤝 기여

버그 리포트 및 기능 제안은 GitHub Issues에 등록해주세요.

