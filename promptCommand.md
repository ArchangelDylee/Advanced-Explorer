# Advanced Explorer 프로그램 생성 명령어

## 📋 목차
1. [프로젝트 초기 설정](#1-프로젝트-초기-설정)
2. [UI 구조 및 디자인](#2-ui-구조-및-디자인)
3. [백엔드 구조](#3-백엔드-구조)
4. [파일 인덱싱 시스템](#4-파일-인덱싱-시스템)
5. [검색 기능](#5-검색-기능)
6. [요약 기능](#6-요약-기능)
7. [기타 기능](#7-기타-기능)

---

## 1. 프로젝트 초기 설정

### 1-1. 프로젝트 구조 생성
```
Advanced Explorer 프로젝트를 다음 구조로 생성해줘:

Advanced Explorer/
├── src/
│   ├── App.tsx          # 메인 React 컴포넌트
│   ├── main.tsx         # React 진입점
│   ├── index.css        # 글로벌 스타일
│   └── api/
│       └── backend.ts   # 백엔드 API 클라이언트
├── electron/
│   ├── main.cjs         # Electron 메인 프로세스
│   └── preload.cjs      # Electron preload 스크립트
├── python-backend/
│   ├── server.py        # Flask 서버
│   ├── database.py      # SQLite FTS5 DB 관리
│   ├── indexer.py       # 파일 인덱싱 엔진
│   ├── search.py        # 검색 엔진
│   ├── summarizer.py    # 요약 엔진
│   └── requirements.txt # Python 의존성
├── config.json          # 설정 파일
├── package.json         # Node.js 의존성
├── vite.config.ts       # Vite 설정
├── tsconfig.json        # TypeScript 설정
└── tailwind.config.js   # Tailwind CSS 설정
```

### 1-2. 기술 스택 선정
```
다음 기술 스택으로 프로젝트 설정해줘:

Frontend:
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Lucide React (아이콘)

Desktop:
- Electron

Backend:
- Python 3.11
- Flask
- Flask-CORS
- SQLite (FTS5)

의존성:
- 문서 파싱: python-docx, python-pptx, PyMuPDF, openpyxl, pywin32
- 텍스트 처리: chardet, sumy, nltk, numpy
- 사용자 입력 감지: pynput
```

### 1-3. package.json 설정
```json
{
  "name": "advanced-explorer",
  "version": "1.0.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "electron": "electron .",
    "start": "npm run dev & npm run electron"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "latest"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.0.0",
    "autoprefixer": "^10.4.14",
    "electron": "^25.0.0",
    "postcss": "^8.4.24",
    "tailwindcss": "^3.3.2",
    "typescript": "^5.0.0",
    "vite": "^4.3.9"
  }
}
```

---

## 2. UI 구조 및 디자인

### 2-1. Windows 11 Dark Mica 디자인 테마
```
Windows 11 Dark 테마로 다음 색상을 사용해줘:

색상 팔레트:
- windowBg: #191919 (메인 배경)
- titleBarBg: #121212 (타이틀바)
- panelBg: #202020 (패널 배경)
- border: #444444 (테두리)
- textPrimary: #FFFFFF (주요 텍스트)
- textSecondary: #D0D0D0 (보조 텍스트)
- textMuted: #AAA (비활성)
- accent: #0067C0 (강조색 - Microsoft Blue)
```

### 2-2. 레이아웃 구조
```
다음과 같은 레이아웃으로 UI를 구성해줘:

┌─────────────────────────────────────────────────┐
│  타이틀바 (드래그 가능, 탭 영역)                  │
├─────────────────────────────────────────────────┤
│  주소 표시줄 & 탐색 버튼 (뒤로, 앞으로, 위로)     │
│  검색바                                          │
├──────────┬────────────────────┬─────────────────┤
│          │                    │                 │
│  왼쪽    │   중앙 파일 리스트  │   오른쪽        │
│  사이드바 │   (테이블 뷰)      │   패널          │
│          │                    │                 │
│  - 즐겨찾기│   Name | Size | Date│  - 내용 보기   │
│  - 폴더 트리│                   │  - 검색 로그   │
│          │                    │  - 인덱싱 로그  │
│          │                    │  - 색인 관리   │
│          │                    │                 │
└──────────┴────────────────────┴─────────────────┘

크기 조절 가능한 Resizer로 각 패널 구분
```

### 2-3. 주요 컴포넌트 생성
```
다음 컴포넌트들을 생성해줘:

1. TreeItem: 폴더 트리 아이템
   - 아이콘, 라벨, 확장/축소
   - 선택 상태 표시
   - 우클릭 메뉴

2. Resizer: 패널 크기 조절
   - 수평/수직 방향 지원
   - 드래그 앤 드롭

3. ContextMenu: 우클릭 메뉴
   - 경로 복사, 이름 복사

4. TypeFilter: 파일 타입 필터 체크박스
   - 문서, 이미지, 압축파일 등

5. FileList: 파일 목록 테이블
   - 정렬 기능 (이름, 크기, 날짜)
   - 인덱싱 상태 표시 (✓/○)
   - 더블클릭으로 열기
```

---

## 3. 백엔드 구조

### 3-1. Flask 서버 생성
```python
# python-backend/server.py

Flask 서버를 다음과 같이 생성해줘:

1. CORS 활성화 (프론트엔드 통신)
2. UTF-8 인코딩 설정 (한글 지원)
3. 전역 객체:
   - db_manager: DatabaseManager
   - indexer: FileIndexer
   - search_engine: SearchEngine
   - summarizer: ContentSummarizer

4. 초기화 함수 (initialize):
   - 데이터베이스 초기화
   - 인덱서 초기화
   - 검색 엔진 초기화
   - 요약 엔진 초기화

5. 종료 처리 (cleanup):
   - 인덱서 리소스 정리
   - 데이터베이스 커밋 및 연결 종료
```

### 3-2. API 엔드포인트 정의
```
다음 REST API 엔드포인트들을 생성해줘:

파일 시스템:
- GET /api/filesystem/<path:directory> - 디렉토리 내용 조회

검색:
- POST /api/search - 검색 (파일명 + 내용)
- GET /api/search/history - 검색 기록
- DELETE /api/search/history - 검색 기록 삭제

인덱싱:
- POST /api/indexing/start - 인덱싱 시작
- POST /api/indexing/stop - 인덱싱 중지
- GET /api/indexing/status - 인덱싱 상태
- GET /api/indexing/logs - 인덱싱 로그
- POST /api/indexing/clear - 인덱스 초기화
- GET /api/indexing/database/<path> - 인덱싱된 파일 상세
- POST /api/indexing/check-files - 파일 인덱싱 여부 확인

통계:
- GET /api/statistics - DB 통계

요약:
- POST /api/summarize - 파일 내용 요약
```

---

## 4. 파일 인덱싱 시스템

### 4-1. 데이터베이스 설계
```sql
-- SQLite FTS5 전체 텍스트 검색 테이블 생성

CREATE VIRTUAL TABLE files_fts USING fts5(
    path UNINDEXED,    -- 파일 경로 (검색 대상 아님)
    content,           -- 파일 내용 (검색 대상)
    mtime UNINDEXED,   -- 수정 시간 (증분 인덱싱용)
    tokenize='unicode61 remove_diacritics 1'
);

-- 검색 기록 테이블
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_search_timestamp 
    ON search_history(timestamp DESC);
```

### 4-2. 파일 파서 구현
```python
다음 파일 형식을 파싱할 수 있는 함수들을 구현해줘:

지원 형식:
1. PDF - PyMuPDF (fitz)
2. DOCX - python-docx
3. PPTX - python-pptx
4. XLSX - openpyxl
5. TXT, MD, JSON, XML, CSV - 텍스트 파일
6. DOC, PPT, XLS - pywin32 (Windows COM)
7. HWP - olefile (한글 문서)

각 파서는:
- 텍스트 추출
- 예외 처리
- 인코딩 감지 (chardet)
- 토큰 수 계산
```

### 4-3. 인덱싱 워커 구현
```
다음 기능을 가진 인덱싱 워커를 구현해줘:

1. 멀티스레드 처리
2. 사용자 활동 감지 (pynput)
   - 키보드/마우스 입력 감지
   - 자동 일시정지 (2초 대기)
3. 증분 인덱싱
   - mtime 비교로 변경된 파일만 처리
4. 배치 처리
   - 2개 파일마다 DB 커밋
5. 진행률 표시
   - 처리 중: 파일명, 크기, 토큰 수
   - 이전 처리 완료: "이전 처리 완료" 표시
6. 오류 처리 및 재시도
```

### 4-4. DB 트랜잭션 관리
```python
다음과 같이 안정적인 DB 트랜잭션을 구현해줘:

1. WAL 모드 활성화:
   PRAGMA journal_mode=WAL
   PRAGMA synchronous=NORMAL

2. 명시적 트랜잭션:
   BEGIN TRANSACTION
   ... SQL 작업 ...
   COMMIT

3. 롤백 처리:
   try:
       트랜잭션 시작
       작업 수행
       커밋
   except:
       롤백
   finally:
       정리

4. 배치 삽입:
   - 여러 파일을 한 번에 처리
   - 트랜잭션 범위 최적화
```

---

## 5. 검색 기능

### 5-1. 통합 검색 구현
```python
다음 기능을 가진 검색 엔진을 구현해줘:

1. 파일명 검색:
   - 파일 시스템 탐색
   - 부분 일치 검색 (대소문자 무시)

2. 내용 검색:
   - FTS5 전체 텍스트 검색
   - 관련도 순 정렬 (BM25)
   - 매칭 위치 하이라이트

3. 통합 결과:
   - 파일명 매칭
   - 내용 N개 매칭
   - 중복 제거

4. 검색 기록 관리:
   - 저장 (최대 100개)
   - 조회
   - 삭제
```

### 5-2. 검색 로그 표시
```
검색 결과를 다음과 같이 로그에 표시해줘:

형식:
🔍 검색 시작: "검색어" (경로)
   파일명 매칭: 총 N개 발견
   내용 매칭: 총 M개 발견
✓ 검색 완료: 총 K개 파일 (소요시간: X.Xs)

개별 파일:
- 파일명 매칭: 파일명.ext
- 내용 3개 매칭: 파일명.ext
```

---

## 6. 요약 기능

### 6-1. TextRank 요약 엔진
```python
다음과 같이 요약 엔진을 구현해줘:

라이브러리:
- sumy (TextRank 구현)
- nltk
- numpy (의존성)

기능:
1. 자동 언어 감지
   - 한글 포함 여부 확인
   - 모든 언어를 english 토크나이저로 처리

2. 요약 생성:
   - TextRank 알고리즘 사용
   - 문장 수 지정 가능 (기본 5개)
   - 문장 간 빈 줄 추가 (\n\n)

3. 결과 반환:
   - 원본 길이
   - 요약 길이
   - 압축률
   - 언어 정보
```

### 6-2. 요약 UI 구현
```
요약 기능 UI를 다음과 같이 구현해줘:

위치: 내용 보기 및 편집 패널

1. 요약 생성 버튼:
   - 아이콘 + "요약 생성" 텍스트
   - 로딩 중: 스피너 + "요약 중..."

2. 요약 결과 표시:
   - 배경색: 녹색 계열 (#1a3a1a)
   - 제목: "📝 AI 요약 (TextRank)"
   - 내용: 줄 간격 1.8
   - whitespace-pre-wrap으로 줄바꿈 유지

3. 전체 내용:
   - 요약 아래에 표시
   - 스크롤 가능
```

---

## 7. 기타 기능

### 7-1. 즐겨찾기 구현
```typescript
다음 즐겨찾기를 기본으로 추가해줘:

const FAVORITES = [
  { name: '문서', path: `${userHome}\\Documents`, icon: Folder },
  { name: '바탕화면', path: `${userHome}\\Desktop`, icon: Monitor },
  { name: '다운로드', path: `${userHome}\\Downloads`, icon: Folder },
  { name: '사진', path: `${userHome}\\Pictures`, icon: ImageIcon },
  { name: '음악', path: `${userHome}\\Music`, icon: FileText }
];

기능:
- 클릭 시 해당 폴더로 이동
- 선택 상태 하이라이트
- 우클릭 메뉴 (경로 복사)
```

### 7-2. 폴더 트리 구현
```
재귀적 폴더 트리를 구현해줘:

기능:
1. 지연 로딩:
   - 확장 시 하위 폴더 로드
   - 성능 최적화

2. 상태 관리:
   - expanded: 확장/축소
   - selected: 선택 상태
   - childrenLoaded: 로드 여부

3. UI:
   - 들여쓰기로 계층 표시
   - ChevronRight/Down 아이콘
   - 폴더 아이콘 색상 구분
```

### 7-3. 탭 시스템 구현
```
멀티 탭을 지원하는 시스템을 구현해줘:

기능:
1. 탭 생성/삭제
2. 탭 간 전환
3. 탭별 상태 관리:
   - 현재 경로
   - 파일 목록
   - 선택된 파일
   - 정렬 설정
   - 히스토리 (뒤로/앞으로)

4. localStorage 저장:
   - 세션 유지
   - 재시작 시 복원

5. 초기 탭:
   - "문서" 탭
   - Documents 폴더로 시작
```

### 7-4. 파일 인덱싱 상태 표시
```
파일 리스트에 인덱싱 상태를 표시해줘:

표시 방법:
- ✓ (녹색): 인덱싱 완료
- ○ (회색): 인덱싱 안됨

구현:
1. FileItem 인터페이스에 indexed 필드 추가
2. 폴더 탐색 시 checkFilesIndexed API 호출
3. 각 파일의 인덱싱 여부 확인
4. 파일명 옆에 상태 아이콘 표시
```

### 7-5. 컨텍스트 메뉴
```
다음 기능을 가진 컨텍스트 메뉴를 구현해줘:

트리거:
- 파일 우클릭
- 폴더 우클릭

메뉴 항목:
1. 경로 복사
   - 디렉토리 경로 복사
   - 클립보드에 저장

2. 이름 복사
   - 파일/폴더 이름 복사
   - 클립보드에 저장

UI:
- 마우스 위치에 표시
- 클릭 시 닫기
- 다른 영역 클릭 시 닫기
```

### 7-6. 정렬 기능
```
파일 리스트 정렬 기능을 구현해줘:

정렬 기준:
1. 이름 (오름차순/내림차순)
2. 크기 (오름차순/내림차순)
3. 날짜 (오름차순/내림차순)

UI:
- 컬럼 헤더 클릭 시 정렬
- 정렬 방향 화살표 표시
- 폴더 우선 정렬 유지
```

### 7-7. 로컬 스토리지 활용
```typescript
다음 데이터를 localStorage에 저장해줘:

저장 항목:
1. tabs: 탭 목록 및 상태
2. activeTabId: 활성 탭 ID
3. nextTabId: 다음 탭 ID
4. layoutState: 패널 크기
5. typeFilters: 파일 타입 필터 상태

커스텀 훅:
function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void]

세션 복원:
- 앱 재시작 시 이전 상태 복원
- 탭, 경로, 선택 파일 등 유지
```

### 7-8. 즐겨찾기/폴더 트리 높이 조절
```
즐겨찾기와 폴더 트리 사이의 높이를 조절할 수 있도록 구현해줘:

구현:
1. layoutState에 favoritesHeight 추가 (기본값: 180px)
2. Tree Area를 flex flex-col로 변경
3. 즐겨찾기 섹션:
   - style={{ height: layout.favoritesHeight }}
   - overflow-y-auto로 스크롤 지원
4. Resizer 추가:
   - 즐겨찾기와 폴더 트리 사이에 vertical Resizer
   - onResize로 favoritesHeight 조정
   - 최소 높이: 50px
5. 폴더 트리:
   - flex-1로 나머지 공간 차지
   - overflow-y-auto로 스크롤 지원

사용자 경험:
- 마우스로 경계선 드래그하여 높이 조절
- localStorage에 저장되어 세션 유지
- 양쪽 모두 독립적인 스크롤
```

---

## 8. Electron 통합

### 8-1. main.cjs 설정
```javascript
Electron 메인 프로세스를 다음과 같이 설정해줘:

1. 창 생성:
   - 크기: 1400x900
   - 프레임 없음 (frameless)
   - 최소 크기: 1200x800
   - 아이콘 설정

2. Python 백엔드 자동 시작:
   - config.json에서 설정 읽기
   - 가상환경 Python 사용
   - 개발/프로덕션 모드 구분

3. 앱 안전 모드:
   - 비정상 종료 감지
   - 3회 연속 크래시 시 안전 모드
   - Python 자동 시작 비활성화

4. IPC 통신:
   - openFile: 파일 열기 (기본 프로그램)
   - 보안 설정
```

### 8-2. preload.cjs 설정
```javascript
preload 스크립트를 다음과 같이 설정해줘:

노출 API:
- electronAPI.openFile(path): 파일 열기

보안:
- contextIsolation: true
- nodeIntegration: false
- contextBridge 사용
```

### 8-3. config.json
```json
{
  "python": {
    "venv": "python-backend/venv/Scripts/python.exe",
    "useVenv": true,
    "autoStart": true
  },
  "indexing": {
    "enableActivityMonitor": true,
    "idleThreshold": 2.0
  }
}
```

---

## 9. 실행 및 배포

### 9-1. 개발 모드 실행
```bash
# 1단계: Python 백엔드 시작
cd python-backend
python server.py

# 2단계: Vite 개발 서버 시작 (새 터미널)
npm run dev

# 3단계: Electron 앱 시작 (새 터미널)
npm run electron
```

### 9-2. 의존성 설치
```bash
# Node.js 의존성
npm install

# Python 의존성
cd python-backend
pip install -r requirements.txt
```

### 9-3. requirements.txt
```
Flask==3.0.0
Flask-CORS==4.0.0
chardet==5.2.0
python-docx==1.1.0
python-pptx==0.6.23
PyMuPDF==1.23.8
openpyxl==3.1.2
pywin32==306
olefile==0.47
Werkzeug==3.0.1
pynput==1.7.6
sumy==0.11.0
nltk==3.8.1
numpy==1.24.3
```

---

## 10. 스타일링 및 UX

### 10-1. Tailwind CSS 설정
```javascript
// tailwind.config.js
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0067C0',
      }
    }
  }
}
```

### 10-2. 글로벌 스타일
```css
/* src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  overflow: hidden;
}

/* 스크롤바 스타일링 */
::-webkit-scrollbar {
  width: 12px;
  height: 12px;
}

::-webkit-scrollbar-track {
  background: #2C2C2C;
}

::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 6px;
}

::-webkit-scrollbar-thumb:hover {
  background: #777;
}
```

### 10-3. 반응형 동작
```
다음과 같은 인터랙션을 구현해줘:

1. 호버 효과:
   - 파일 항목: 배경색 변경
   - 버튼: 색상 변경
   - 트리 항목: 하이라이트

2. 클릭 효과:
   - active:scale-[0.99] (살짝 축소)
   - active:bg-[색상] (배경 변경)

3. 트랜지션:
   - transition-colors duration-75
   - transition-transform duration-100

4. 포커스 표시:
   - 선택된 항목: 테두리 강조
   - 파란색 강조 (#0067C0)
```

---

## 📝 추가 요구사항

### A. 성능 최적화
```
1. 파일 리스트 가상화 (큰 폴더)
2. 인덱싱 배치 처리
3. 검색 결과 페이지네이션
4. 이미지 미리보기 지연 로딩
```

### B. 오류 처리
```
1. 파일 접근 오류 처리
2. 네트워크 오류 처리
3. 백엔드 연결 실패 처리
4. 인덱싱 오류 로깅
```

### C. 로깅
```
1. 인덱싱 로그 (성공/실패/스킵)
2. 검색 로그
3. 시스템 로그 (백엔드)
4. 오류 로그
```

---

## ✅ 완성 기준

다음 기능이 모두 정상 작동하면 완성:

- [x] 파일 시스템 탐색
- [x] 즐겨찾기 및 폴더 트리
- [x] 멀티 탭
- [x] 파일 검색 (파일명 + 내용)
- [x] 파일 인덱싱 (PDF, DOCX, PPTX, XLSX 등)
- [x] TextRank 요약
- [x] 사용자 활동 감지
- [x] 인덱싱 상태 표시
- [x] 검색 로그 및 인덱싱 로그
- [x] 컨텍스트 메뉴
- [x] 정렬 및 필터
- [x] localStorage 세션 유지
- [x] Electron 통합
- [x] 초기 디렉토리: 문서 폴더
- [x] 즐겨찾기/폴더 트리 높이 조절

---

**작성일**: 2025-12-10  
**최종 수정**: 2025-12-10  
**버전**: 1.1.0  
**프로젝트**: Advanced Explorer

