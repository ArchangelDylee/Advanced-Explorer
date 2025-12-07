# 개발 진행 사항 (Development Note)

## 📝 프로젝트 정보

- **프로젝트명**: Advanced Explorer
- **개발자**: dylee.kyle@gmail.com
- **GitHub**: https://github.com/ArchangelDylee/Advanced-Explorer.git
- **개발 기간**: 2025년 12월
- **개발 도구**: Cursor AI

---

## 🎨 UI 개발 단계

### 초기 UI 작성
- **방법**: Gemini AI로 UI Template 생성
- **파일**: `GUI_layer.tsx` (초기 템플릿)
- **기술 스택**: React + TypeScript + Tailwind CSS
- **스타일**: Windows 11 Explorer 스타일, 다크 테마

---

## 🔧 Fine Tuning Task 진행사항

### 1. UI Template 업데이트 및 구성
**요청**: UI Template 를 새로 만들고, UI Template 파일에 업데이트 했으니, 이것으로 UI를 구성하시요

**구현**:
- `GUI_layer.tsx` 내용을 `src/App.tsx`로 복사
- Electron + Vite 프로젝트 구조 생성
- React 컴포넌트 기반으로 파일 탐색기 UI 구현
- 사용자 정보 설정: `dylee.kyle@gmail.com`

**결과**: ✅ Electron 데스크톱 앱으로 전환 완료

---

### 2. GitHub 저장소 연결
**요청**: GitHub URL을 알려줌

**정보**:
- **Repository**: https://github.com/ArchangelDylee/Advanced-Explorer.git
- **Branch**: main
- **User Email**: dylee.kyle@gmail.com

**결과**: ✅ Git 설정 및 초기 커밋 완료

---

### 3. 버튼 클릭 효과 통일 (일부 미작동)
**요청**: 색인의 시작 버튼도 검색의 시작 버튼 처럼 클릭시 효과를 동일하게 해주되 효과 시간을 둘다 모두 0.1초로 짧게 해줘

**시도**:
- `transition-all duration-100` 적용
- `active:scale-95` 클릭 효과
- `active:bg-[#005a9e]` 배경색 변경

**결과**: ⚠️ 일부 버튼에서 효과가 제대로 작동하지 않음

---

### 4. 실제 디렉토리 표시
**요청**: 폴더 트리 창에 실제 이 프로그램을 사용하는 컴퓨터의 디렉토리가 표시되도록 수정해

**구현**:
- Electron IPC를 통한 실제 파일 시스템 접근
- `fs.promises.readdir`로 디렉토리 읽기
- 모든 드라이브 자동 감지 (A-Z 검사)
- 재귀적 폴더 로딩 (클릭 시 동적 로드)
- 실제 파일 크기, 수정 날짜 표시

**결과**: ✅ 실제 컴퓨터의 디렉토리 구조 완벽 표시

**Push & Commit**: ✅ 완료

---

### 5. 특수 문자로 시작하는 파일/폴더 제외
**요청**: 특수 문자로 시작되는 디렉토리 및 파일은 즐겨찾기, 파일 트리 및 파일 리스트에서 제외해줘

**구현**:
- `isValidName()` 함수 추가
- 정규식: `/^[a-zA-Z0-9가-힣]/` (영문, 숫자, 한글만 허용)
- 제외되는 특수 문자: `.`, `$`, `~`, `#`, `@`, `!`
- 적용 위치:
  - 즐겨찾기 목록
  - 폴더 트리
  - 파일 리스트
  - 파일 시스템 읽기

**결과**: ✅ `.git`, `$Recycle.Bin`, `.vscode` 등 시스템 폴더 자동 숨김

**Push & Commit**: ✅ 완료

---

### 6. 파일 인덱싱 엔진 구현 (Req_file_indexing.DOC)
**요청**: 모든 명령어를 바탕으로 백엔드 구현

**구현 내용**:

#### A. 데이터베이스 (SQLite FTS5)
- **files_fts** 테이블: trigram 토크나이저 (한국어 최적화)
- **search_history** 테이블: 검색 히스토리 관리

#### B. 파일 파싱 엔진 (`indexer.py`)
| 확장자 | 라이브러리 | 구현 상태 |
|--------|-----------|----------|
| `.txt` | Built-in | ✅ UTF-8 → CP949 → chardet |
| `.docx` | python-docx | ✅ |
| `.doc` | pywin32 COM | ✅ CoInitialize 포함 |
| `.pptx` | python-pptx | ✅ |
| `.ppt` | pywin32 COM | ✅ |
| `.xlsx` | openpyxl | ✅ data_only=True, 모든 시트 |
| `.xls` | pywin32 COM | ✅ |
| `.pdf` | PyMuPDF (fitz) | ✅ 고속 처리 |
| `.hwp` | pywin32/olefile | ✅ 1차 COM, 2차 olefile |

#### C. 제외 규칙
- **폴더**: `.git`, `node_modules`, `venv`, `__pycache__` 등 17개
- **파일**: `desktop.ini`, `thumbs.db`, `~$` (Office 임시)
- **확장자**: `.exe`, `.dll`, `.zip`, `.mp3`, `.jpg` 등 30개+
- **시스템 경로**: `C:\Windows`, `C:\Program Files`, `C:\$Recycle.Bin`
- **사용자 정의**: 와일드카드 패턴 지원

#### D. 예외 처리 (skipcheck.txt, error.txt)
- 암호화된 파일 (Password Protected)
- 파일 잠금 (PermissionError)
- 용량 초과 (100MB)
- 타임아웃 (60초)
- 손상된 파일 (Corrupted)
- 팝업 방지: `Visible=False`, `DisplayAlerts=False`

#### E. 증분 색인
- **New Files**: DB에 없음 → INSERT
- **Modified Files**: mtime 변경 → UPDATE
- **Deleted Files**: 디스크에 없음 → DELETE
- **종료 시**: VACUUM으로 DB 최적화

#### F. Flask REST API (`server.py`)
- 18개 API 엔드포인트
- 검색, 인덱싱, 통합 검색, DB 관리

#### G. 검색 엔진 (`search.py`)
- 정확 일치 검색: `"문자열"`
- AND 조건: `단어1 단어2`
- 통합 검색: 파일명(파일시스템) + 내용(DB)
- 중복 제거 (DB 우선)

#### H. PyQt6 GUI (`gui_pyqt6.py`)
- QThread Worker (비동기)
- SearchWorker, IndexingWorker
- Flask API 통신
- 실시간 로그 및 진행 상황

**결과**: ✅ 완전한 백엔드 인덱싱 시스템 구현

**Push & Commit**: ✅ 완료

---

### 7. 이미지 미리보기 구현
**요청**: 파일리스트에서 이미지가 클릭되면 "내용 보기 및 편집"에서 미리 보기 가 나오도록 해줘

**구현**:
- Electron IPC: `read-image-file` 핸들러
- Base64 인코딩으로 이미지 데이터 전송
- MIME 타입 자동 감지
- React에서 Data URL로 이미지 표시
- 지원 형식: JPG, PNG, GIF, BMP, WEBP, SVG, ICO

**UI 개선**:
- 파일 정보 표시 (이름, 크기, 수정 날짜)
- 중앙 정렬 및 크기 자동 조정
- 다크 테마 배경

**결과**: ✅ 이미지 파일 미리보기 완벽 작동

---

### 8. 개발자 콘솔 비활성화
**요청**: 개발자 Console이 안나오도록 설정해줘

**구현**:
- `electron/main.cjs`에서 `openDevTools()` 주석 처리
- 개발 모드에서도 자동으로 열리지 않음
- 수동 열기: `Ctrl+Shift+I` 단축키

**결과**: ✅ 깔끔한 UI, 개발자 도구 숨김

---

## 📊 최종 프로젝트 구조

```
Advanced-Explorer/
├── electron/                  # Electron 메인 프로세스
│   ├── main.cjs              # 앱 진입점, Python 백엔드 자동 시작
│   └── preload.cjs           # IPC API 노출
├── python-backend/            # Python 백엔드 인덱싱 엔진
│   ├── venv/                 # 가상 환경
│   ├── logs/                 # 로그 파일 (skipcheck.txt, error.txt)
│   ├── database.py           # SQLite FTS5 DB 관리
│   ├── indexer.py            # 파일 인덱싱 엔진 (9개 형식)
│   ├── search.py             # 통합 검색 엔진
│   ├── server.py             # Flask REST API (18 endpoints)
│   ├── gui_pyqt6.py          # PyQt6 네이티브 GUI
│   ├── requirements.txt      # Python 의존성
│   ├── README.md             # 백엔드 문서
│   └── PYQT6_GUI.md          # PyQt6 사용 가이드
├── src/                      # React 프론트엔드
│   ├── App.tsx               # 메인 컴포넌트 (1000+ 라인)
│   ├── api/
│   │   └── backend.ts        # Python API 클라이언트
│   ├── main.tsx              # React 진입점
│   └── index.css             # Tailwind CSS
├── SETUP.md                  # 설치 및 실행 가이드
├── DEVELOPMENT_NOTE.md       # 개발 진행 노트 (이 파일)
└── package.json              # Node.js 의존성
```

---

## 🎯 구현된 주요 기능

### Frontend (React/Electron)
- ✅ Windows 11 스타일 파일 탐색기 UI
- ✅ 실제 파일 시스템 연동
- ✅ 모든 드라이브 및 디렉토리 표시
- ✅ 동적 폴더 로딩 (재귀적)
- ✅ 특수 문자 파일/폴더 필터링
- ✅ 이미지 미리보기 (JPG, PNG, GIF 등)
- ✅ 탭 시스템 (멀티 인스턴스)
- ✅ 히스토리 (뒤로/앞으로)
- ✅ 컨텍스트 메뉴
- ✅ 파일 복사/붙여넣기
- ✅ 파일 삭제

### Backend (Python)
- ✅ SQLite FTS5 전문 검색 (trigram, 한국어 최적화)
- ✅ 9가지 파일 형식 파싱
- ✅ 비동기 인덱싱 (Worker Thread)
- ✅ 증분 색인 (New/Modified/Deleted)
- ✅ 제외 규칙 (폴더, 파일, 확장자, 경로, 사용자 정의)
- ✅ 예외 처리 (Skip Logic, Error Logging)
- ✅ 타임아웃 (60초)
- ✅ 팝업 방지 (COM 객체)
- ✅ 검색어 파싱 (정확 일치, AND 조건)
- ✅ 통합 검색 (파일명 + 내용)
- ✅ Flask REST API (18 endpoints)
- ✅ PyQt6 GUI (QThread Worker)

---

## 🚀 실행 방법

### Option 1: React/Electron (권장)
```bash
# 터미널 1
npm run dev

# 터미널 2  
npm run electron
```

### Option 2: PyQt6 GUI
```bash
# 터미널 1: Flask 백엔드
cd python-backend
.\venv\Scripts\Activate.ps1
python server.py

# 터미널 2: PyQt6 GUI
cd python-backend
.\venv\Scripts\Activate.ps1
python gui_pyqt6.py
```

---

## 📈 개발 통계

- **총 커밋 수**: 10+
- **총 코드 라인**: 5,000+ 라인
- **Python 모듈**: 5개 (database, indexer, search, server, gui_pyqt6)
- **React 컴포넌트**: 1,000+ 라인
- **API 엔드포인트**: 18개
- **지원 파일 형식**: 9개 (TXT, DOCX, DOC, PPTX, PPT, XLSX, XLS, PDF, HWP)
- **제외 규칙**: 70+ 항목

---

## 🎓 학습 내용

### 기술 스택
1. **Electron**: IPC, Context Isolation, Preload Script
2. **React**: Hooks, State Management, Custom Hooks
3. **Python**: Threading, COM Objects, SQLite FTS5
4. **PyQt6**: QThread, Signals/Slots, QTreeWidget
5. **Flask**: REST API, CORS
6. **SQLite**: FTS5, trigram, VACUUM

### 아키텍처 패턴
- Worker Thread (UI 블로킹 방지)
- IPC (Inter-Process Communication)
- REST API (Frontend-Backend 분리)
- 증분 색인 (성능 최적화)
- 예외 처리 (안정성)

---

## 🐛 해결한 문제들

1. **PowerShell && 토큰 오류** → 명령어 분리 실행
2. **Electron ERR_CONNECTION_REFUSED** → Vite 서버 먼저 시작
3. **Mock 경로 오류** → 실제 Windows 경로로 매핑
4. **Python ModuleNotFoundError** → venv의 pip로 설치
5. **wmic 명령어 오류** → fs.existsSync로 드라이브 감지
6. **파일 잠금 오류** → PermissionError 예외 처리
7. **COM 팝업** → Visible=False, DisplayAlerts=False

---

## 🔮 향후 개발 계획

- [ ] HWP 파일 완벽 지원
- [ ] WebSocket 실시간 진행 상황
- [ ] 고급 쿼리 문법 (AND, OR, NOT)
- [ ] OCR 기능 (이미지 내 텍스트)
- [ ] 파일 형식별 필터링
- [ ] 날짜 범위 검색
- [ ] 검색 결과 캐싱
- [ ] 썸네일 생성
- [ ] 비디오 미리보기

---

## 📄 라이선스

MIT License

---

## 👨‍💻 개발자

- **Email**: dylee.kyle@gmail.com
- **GitHub**: https://github.com/ArchangelDylee
- **Tool**: Cursor AI (Claude Sonnet 4.5)

---

**Last Updated**: 2025-12-06





