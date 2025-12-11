# Advanced Explorer - 개발자 요구사항 명세서

> Developer Requirements Specification

**프로젝트**: Advanced Explorer  
**버전**: 2.0.0  
**최종 수정**: 2025-12-10  
**작성자**: Development Team

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [개발 환경 설정](#4-개발-환경-설정)
5. [API 명세](#5-api-명세)
6. [데이터베이스 설계](#6-데이터베이스-설계)
7. [핵심 모듈](#7-핵심-모듈)
8. [코딩 컨벤션](#8-코딩-컨벤션)
9. [배포 및 빌드](#9-배포-및-빌드)
10. [성능 최적화](#10-성능-최적화)

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목적
- Windows 탐색기를 대체하는 고급 파일 관리 도구
- FTS5 기반 전체 텍스트 검색 기능 제공
- 다양한 문서 형식 지원 (PDF, DOCX, PPTX, XLSX, HWP 등)
- TextRank 알고리즘 기반 문서 요약 기능

### 1.2 주요 기능
- **파일 시스템 탐색**: 멀티 탭, 히스토리, 즐겨찾기
- **전체 텍스트 검색**: SQLite FTS5 인덱싱, 파일명/내용 통합 검색
- **문서 파싱**: 다양한 형식의 문서에서 텍스트 추출
- **사용자 활동 감지**: 키보드/마우스 입력 감지로 인덱싱 자동 일시정지
- **문서 요약**: TextRank 알고리즘 기반 자동 요약
- **접근 권한 관리**: 읽기 권한이 없는 파일/폴더 자동 필터링

### 1.3 대상 플랫폼
- **OS**: Windows 10/11 (주 타겟), macOS, Linux (부분 지원)
- **Node.js**: 18.x 이상
- **Python**: 3.11.x
- **Electron**: 25.x 이상

---

## 2. 기술 스택

### 2.1 Frontend

| 기술 | 버전 | 용도 |
|-----|------|------|
| React | 18.2+ | UI 프레임워크 |
| TypeScript | 5.0+ | 타입 안정성 |
| Vite | 4.3+ | 빌드 도구 |
| Tailwind CSS | 3.3+ | 스타일링 |
| Lucide React | latest | 아이콘 |

### 2.2 Desktop

| 기술 | 버전 | 용도 |
|-----|------|------|
| Electron | 25.0+ | 데스크톱 앱 프레임워크 |
| electron-builder | latest | 앱 빌드/패키징 |

### 2.3 Backend

| 기술 | 버전 | 용도 |
|-----|------|------|
| Python | 3.11 | 백엔드 런타임 |
| Flask | 3.0+ | REST API 서버 |
| Flask-CORS | 4.0+ | CORS 지원 |
| SQLite | 3.x | 데이터베이스 |
| FTS5 | - | 전체 텍스트 검색 |

### 2.4 문서 파싱

| 라이브러리 | 용도 |
|-----------|------|
| PyMuPDF (fitz) | PDF 파싱 |
| python-docx | DOCX 파싱 |
| python-pptx | PPTX 파싱 |
| openpyxl | XLSX 파싱 |
| pywin32 | DOC/PPT/XLS (COM) |
| olefile | HWP 파싱 |
| chardet | 인코딩 감지 |

### 2.5 텍스트 분석

| 라이브러리 | 용도 |
|-----------|------|
| sumy | TextRank 요약 |
| nltk | 자연어 처리 |
| numpy | 수치 연산 |
| pynput | 사용자 입력 감지 |

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Main Process                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │              IPC Communication                   │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼──────┐       ┌───────▼────────┐
│   Renderer   │       │  Python Backend │
│   Process    │◄─────►│  Flask Server   │
│              │ HTTP  │                 │
│  React UI    │       │  ┌──────────┐  │
│  + Vite      │       │  │ Indexer  │  │
│              │       │  │ Search   │  │
│              │       │  │ Parser   │  │
│              │       │  │ Database │  │
└──────────────┘       │  └──────────┘  │
                       │                 │
                       │  SQLite FTS5    │
                       └─────────────────┘
```

### 3.2 프로세스 분리

1. **Electron Main Process**
   - 파일 시스템 접근
   - 창 관리
   - Python 프로세스 관리
   - IPC 통신

2. **Electron Renderer Process**
   - React UI 렌더링
   - 사용자 인터랙션 처리
   - HTTP API 호출

3. **Python Flask Server**
   - REST API 제공
   - 파일 인덱싱
   - 전체 텍스트 검색
   - 문서 요약

### 3.3 통신 프로토콜

```typescript
// IPC (Electron Main ↔ Renderer)
interface ElectronAPI {
  getDrives: () => Promise<Drive[]>;
  readDirectory: (path: string) => Promise<FileEntry[]>;
  readDirectoriesOnly: (path: string) => Promise<DirectoryEntry[]>;
  getFileStats: (path: string) => Promise<FileStats>;
  readImageFile: (path: string) => Promise<ImageData>;
  openFile: (path: string) => Promise<Result>;
}

// HTTP (Renderer ↔ Flask)
const API_BASE_URL = 'http://127.0.0.1:5000/api';
```

---

## 4. 개발 환경 설정

### 4.1 필수 소프트웨어

```bash
# Node.js 설치 확인
node --version  # v18.x 이상

# Python 설치 확인
python --version  # 3.11.x

# npm 패키지 설치
npm install

# Python 가상환경 생성
cd python-backend
python -m venv venv

# 가상환경 활성화 (Windows)
.\venv\Scripts\activate

# Python 패키지 설치
pip install -r requirements.txt
```

### 4.2 개발 서버 실행

```bash
# Terminal 1: Python Backend
cd python-backend
python server.py

# Terminal 2: Vite Dev Server
npm run dev

# Terminal 3: Electron
npm run electron
```

### 4.3 환경 변수

```bash
# .env (선택사항)
PYTHON_PORT=5000
VITE_PORT=5173
NODE_ENV=development
```

### 4.4 VSCode 설정

```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "./python-backend/venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "typescript.tsdk": "node_modules/typescript/lib",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": true
  }
}
```

---

## 5. API 명세

### 5.1 인덱싱 API

#### POST /api/indexing/start
인덱싱 시작

**Request:**
```json
{
  "paths": ["C:\\Users\\Documents"],
  "recursive": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "인덱싱 시작됨",
  "paths": ["C:\\Users\\Documents"]
}
```

#### POST /api/indexing/stop
인덱싱 중지

**Response:**
```json
{
  "success": true,
  "message": "인덱싱 중지 요청"
}
```

#### GET /api/indexing/status
인덱싱 상태 조회

**Response:**
```json
{
  "is_indexing": true,
  "progress": {
    "total": 1000,
    "processed": 250,
    "failed": 5,
    "skipped": 100
  },
  "current_file": "example.pdf",
  "status_message": "인덱싱 중..."
}
```

#### GET /api/indexing/logs?count=100
인덱싱 로그 조회

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-12-10T10:30:00",
      "level": "INFO",
      "message": "파일 처리 완료",
      "file": "example.pdf"
    }
  ]
}
```

#### POST /api/indexing/check-files
파일 인덱싱 여부 확인

**Request:**
```json
{
  "file_paths": [
    "C:\\Users\\Documents\\file1.pdf",
    "C:\\Users\\Documents\\file2.docx"
  ]
}
```

**Response:**
```json
{
  "indexed_status": {
    "C:\\Users\\Documents\\file1.pdf": true,
    "C:\\Users\\Documents\\file2.docx": false
  }
}
```

### 5.2 검색 API

#### POST /api/search/combined
통합 검색 (파일명 + 내용)

**Request:**
```json
{
  "query": "프로젝트",
  "search_path": "C:\\Users\\Documents",
  "options": {
    "content": true,
    "filename": true,
    "recursive": true,
    "max_results": 100
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "path": "C:\\Users\\Documents\\project.docx",
      "name": "project.docx",
      "source": "database",
      "indexed": true,
      "match_count": 5,
      "rank": -2.5,
      "preview": "...프로젝트 계획서...",
      "size": 50240,
      "mtime": "2025-12-10T08:00:00"
    }
  ],
  "total": 15,
  "search_time": 0.125
}
```

#### GET /api/indexing/database/:path
인덱싱된 파일 상세 조회

**Response:**
```json
{
  "path": "C:\\Users\\Documents\\file.docx",
  "content": "문서 전체 내용...",
  "content_length": 5000,
  "mtime": "1702188000",
  "mtime_formatted": "2025-12-10 08:00:00"
}
```

### 5.3 요약 API

#### POST /api/summarize
문서 요약

**Request:**
```json
{
  "file_path": "C:\\Users\\Documents\\report.docx",
  "sentences_count": 5
}
```

**Response:**
```json
{
  "success": true,
  "summary": "요약된 내용...\n\n다음 문장...",
  "original_length": 5000,
  "summary_length": 500,
  "compression_ratio": "10.0%",
  "language": "korean",
  "sentences_count": 5
}
```

### 5.4 통계 API

#### GET /api/statistics
인덱스 통계

**Response:**
```json
{
  "total_files": 1500,
  "total_size": 1073741824,
  "file_types": {
    "pdf": 500,
    "docx": 300,
    "pptx": 200
  },
  "last_indexed": "2025-12-10T10:30:00"
}
```

---

## 6. 데이터베이스 설계

### 6.1 FTS5 테이블

```sql
-- 전체 텍스트 검색 테이블
CREATE VIRTUAL TABLE files_fts USING fts5(
    path UNINDEXED,           -- 파일 경로 (검색 대상 아님)
    content,                  -- 파일 내용 (검색 대상)
    mtime UNINDEXED,          -- 수정 시간 (증분 인덱싱)
    tokenize='unicode61 remove_diacritics 1'
);

-- 검색 기록 테이블
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_timestamp 
    ON search_history(timestamp DESC);
```

### 6.2 데이터베이스 설정

```python
# WAL 모드 활성화 (동시성 향상)
PRAGMA journal_mode=WAL;

# 동기화 레벨 조정 (성능 향상)
PRAGMA synchronous=NORMAL;

# 캐시 크기 설정 (메모리 사용)
PRAGMA cache_size=-64000;  # 64MB
```

### 6.3 트랜잭션 관리

```python
try:
    conn.execute("BEGIN TRANSACTION")
    # ... 작업 수행 ...
    conn.commit()
except sqlite3.Error as e:
    conn.rollback()
    logger.error(f"Transaction failed: {e}")
    raise
```

---

## 7. 핵심 모듈

### 7.1 Indexer (indexer.py)

**책임:**
- 파일 시스템 순회
- 문서 파싱
- 텍스트 추출
- 데이터베이스 저장
- 사용자 활동 감지

**주요 메서드:**
```python
class FileIndexer:
    def start_indexing(self, paths: List[str], recursive: bool)
    def stop_indexing(self)
    def get_stats(self) -> Dict
    def _parse_file(self, file_path: str) -> str
    def _monitor_user_activity(self)
```

### 7.2 Search Engine (search.py)

**책임:**
- FTS5 검색 쿼리 생성
- 파일 시스템 검색
- 결과 통합 및 정렬
- 검색 히스토리 관리

**주요 메서드:**
```python
class SearchEngine:
    def search_combined(self, query: str, search_path: str) -> List[Dict]
    def _search_filesystem(self, query: str, root_path: str) -> List[Dict]
    def parse_search_query(self, query: str) -> Dict
```

### 7.3 Database Manager (database.py)

**책임:**
- SQLite 연결 관리
- FTS5 인덱스 CRUD
- 검색 쿼리 실행
- 트랜잭션 관리

**주요 메서드:**
```python
class DatabaseManager:
    def insert_file(self, path: str, content: str, mtime: float)
    def insert_files_batch(self, files: List[Tuple])
    def search(self, query: str, limit: int) -> List[Dict]
    def get_indexed_file_detail(self, path: str) -> Optional[Dict]
    def is_file_indexed(self, path: str) -> bool
```

### 7.4 Content Summarizer (summarizer.py)

**책임:**
- TextRank 알고리즘 적용
- 중요 문장 추출
- 요약 생성

**주요 메서드:**
```python
class ContentSummarizer:
    def summarize(self, text: str, sentences_count: int) -> Dict
```

---

## 8. 코딩 컨벤션

### 8.1 Python

```python
# PEP 8 준수
# 함수/변수: snake_case
# 클래스: PascalCase
# 상수: UPPER_SNAKE_CASE

# 타입 힌팅 사용
def process_file(file_path: str, options: Dict[str, Any]) -> Optional[str]:
    """
    파일을 처리하고 텍스트를 반환
    
    Args:
        file_path: 파일 경로
        options: 처리 옵션
        
    Returns:
        추출된 텍스트 또는 None
    """
    pass

# Docstring 작성 (Google Style)
```

### 8.2 TypeScript/React

```typescript
// 인터페이스: PascalCase
interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string;
  path?: string;
  indexed?: boolean;
}

// 함수 컴포넌트
export function FileList({ items }: { items: FileItem[] }) {
  return <div>{/* ... */}</div>;
}

// 훅 사용: use로 시작
const useLocalStorage = <T,>(key: string, initialValue: T) => {
  // ...
};
```

### 8.3 네이밍 규칙

| 타입 | 규칙 | 예시 |
|-----|------|------|
| Python 함수/변수 | snake_case | `get_file_stats` |
| Python 클래스 | PascalCase | `FileIndexer` |
| Python 상수 | UPPER_SNAKE_CASE | `API_BASE_URL` |
| TS 인터페이스 | PascalCase | `FileItem` |
| TS 함수/변수 | camelCase | `handleFileClick` |
| React 컴포넌트 | PascalCase | `FileList` |
| CSS 클래스 | kebab-case | `file-list-item` |

---

## 9. 배포 및 빌드

### 9.1 개발 빌드

```bash
# Frontend 빌드
npm run build

# Python 실행 파일 생성 (선택사항)
pyinstaller --onefile python-backend/server.py
```

### 9.2 프로덕션 빌드

```bash
# Electron 앱 패키징
npm run electron:build

# 출력 위치
dist/
  ├── Advanced-Explorer-Setup.exe    # Windows 설치 파일
  ├── Advanced-Explorer.dmg          # macOS 디스크 이미지
  └── Advanced-Explorer.AppImage     # Linux AppImage
```

### 9.3 electron-builder 설정

```json
// package.json
{
  "build": {
    "appId": "com.advanced.explorer",
    "productName": "Advanced Explorer",
    "directories": {
      "output": "dist"
    },
    "files": [
      "dist-electron/**/*",
      "dist/**/*",
      "python-backend/**/*"
    ],
    "win": {
      "target": ["nsis"],
      "icon": "assets/icon.ico"
    },
    "mac": {
      "target": ["dmg"],
      "icon": "assets/icon.icns"
    },
    "linux": {
      "target": ["AppImage"],
      "icon": "assets/icon.png"
    }
  }
}
```

---

## 10. 성능 최적화

### 10.1 인덱싱 최적화

```python
# 배치 삽입 사용
BATCH_SIZE = 2  # 파일 2개마다 커밋

files_batch = []
for file in files:
    content = parse_file(file)
    files_batch.append((file, content, mtime))
    
    if len(files_batch) >= BATCH_SIZE:
        db.insert_files_batch(files_batch)
        files_batch = []
```

### 10.2 검색 최적화

```python
# FTS5 rank 활용
SELECT path, content, rank
FROM files_fts
WHERE files_fts MATCH ?
ORDER BY rank  # 관련도 순 정렬
LIMIT 100;

# 특수문자 검색은 LIKE 사용
SELECT path, content
FROM files_fts
WHERE content LIKE ?
LIMIT 100;
```

### 10.3 UI 최적화

```typescript
// React.memo로 불필요한 리렌더링 방지
export const FileListItem = React.memo(({ file }: Props) => {
  return <div>{file.name}</div>;
});

// useCallback으로 함수 메모이제이션
const handleClick = useCallback(() => {
  // ...
}, [dependencies]);

// 가상 스크롤링 (대용량 목록)
// react-window 또는 react-virtualized 사용 고려
```

### 10.4 메모리 관리

```python
# 대용량 파일 처리 시 스트리밍
def parse_large_file(file_path: str) -> Generator[str, None, None]:
    with open(file_path, 'r', encoding='utf-8') as f:
        while True:
            chunk = f.read(8192)  # 8KB씩 읽기
            if not chunk:
                break
            yield chunk
```

---

## 11. 테스트 가이드

### 11.1 단위 테스트

```python
# pytest 사용
import pytest
from database import DatabaseManager

def test_insert_file():
    db = DatabaseManager(':memory:')
    db.insert_file('/test/file.txt', 'content', 1234567890.0)
    
    result = db.get_indexed_file_detail('/test/file.txt')
    assert result is not None
    assert result['content'] == 'content'
```

### 11.2 통합 테스트

```typescript
// Jest + React Testing Library
import { render, screen, fireEvent } from '@testing-library/react';
import { FileList } from './FileList';

test('renders file list', () => {
  const files = [
    { name: 'test.txt', size: '1KB', date: '2025-12-10', type: 'txt' }
  ];
  
  render(<FileList files={files} />);
  expect(screen.getByText('test.txt')).toBeInTheDocument();
});
```

---

## 12. 보안 고려사항

### 12.1 파일 시스템 접근

```typescript
// 경로 검증
function isValidPath(path: string): boolean {
  // 상대 경로 공격 방지
  const normalized = path.normalize(path);
  return !normalized.includes('..');
}

// 권한 확인
async function checkReadPermission(path: string): Promise<boolean> {
  try {
    await fs.access(path, fs.constants.R_OK);
    return true;
  } catch {
    return false;
  }
}
```

### 12.2 SQL Injection 방지

```python
# 파라미터 바인딩 사용
cursor = conn.execute(
    "SELECT * FROM files_fts WHERE path = ?",
    (user_input,)  # 절대 문자열 포매팅 사용 금지
)
```

### 12.3 XSS 방지

```typescript
// React는 기본적으로 XSS 방지
// dangerouslySetInnerHTML 사용 지양

// 파일 내용 표시 시
<pre className="whitespace-pre-wrap">
  {sanitizeHTML(content)}
</pre>
```

---

## 13. 디버깅 팁

### 13.1 로깅

```python
# Python 로깅 레벨
import logging

# 개발: DEBUG
logging.basicConfig(level=logging.DEBUG)

# 프로덕션: INFO
logging.basicConfig(level=logging.INFO)

# 로그 메시지
logger.debug(f"Processing file: {file_path}")
logger.info(f"Indexing completed: {count} files")
logger.error(f"Failed to parse: {file_path}, error: {e}")
```

```typescript
// TypeScript 디버깅
console.log('🔍 파일 선택:', file.name);
console.error('❌ API 오류:', error);
console.debug('📦 상태 업데이트:', state);
```

### 13.2 Performance Profiling

```python
# Python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... 코드 실행 ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(10)
```

```typescript
// React DevTools Profiler 사용
// Chrome DevTools Performance 탭 활용
```

---

## 14. 라이선스 및 의존성

### 14.1 오픈소스 라이선스

- **프로젝트 라이선스**: MIT
- **주요 의존성 라이선스**:
  - React: MIT
  - Electron: MIT
  - Flask: BSD-3-Clause
  - SQLite: Public Domain
  - PyMuPDF: AGPL (주의)

### 14.2 상용 배포 시 고려사항

- PyMuPDF (AGPL): 상용 라이선스 구매 또는 대체 라이브러리 사용
- 기타 MIT/BSD 라이선스: 상용 사용 가능

---

## 15. 참고 자료

### 15.1 공식 문서

- [React Documentation](https://react.dev/)
- [Electron Documentation](https://www.electronjs.org/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- [Tailwind CSS](https://tailwindcss.com/docs)

### 15.2 관련 프로젝트

- [VSCode](https://github.com/microsoft/vscode) - Electron 앱 참고
- [Notion](https://www.notion.so/) - 문서 관리 UI 참고
- [Everything](https://www.voidtools.com/) - 파일 검색 참고

---

**문서 버전**: 2.0.0  
**최종 검토**: 2025-12-10  
**다음 업데이트**: 기능 추가 시

**기여자**: Development Team  
**문의**: dev@advanced-explorer.com


