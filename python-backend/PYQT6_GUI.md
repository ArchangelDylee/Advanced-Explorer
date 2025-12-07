# PyQt6 GUI 사용 가이드

## 📋 개요

Advanced Explorer의 PyQt6 네이티브 GUI입니다. Flask 백엔드 API와 통신하여 파일 검색 및 인덱싱 기능을 제공합니다.

## 🚀 실행 방법

### 1. Python 백엔드 서버 시작

**터미널 1:**
```bash
cd python-backend
.\venv\Scripts\Activate.ps1
python server.py
```

Flask 서버가 `http://127.0.0.1:5000`에서 실행됩니다.

### 2. PyQt6 GUI 실행

**터미널 2:**
```bash
cd python-backend
.\venv\Scripts\Activate.ps1
python gui_pyqt6.py
```

GUI 창이 열립니다.

## 🎨 UI 구성

### 상단: 검색 바
- **검색어 입력** (Combo Box): Enter 키로 검색 실행
- **검색 버튼**: 통합 검색 시작
- **검색 중지 버튼**: 진행 중인 검색 중지

### 좌측 패널
1. **⭐ 즐겨찾기**
   - 문서, 바탕화면, 다운로드, 사진, 음악
   - 클릭 시 해당 경로 선택

2. **📁 폴더 트리**
   - 모든 드라이브 표시
   - 클릭 시 인덱싱 경로 설정

### 중앙 패널
1. **인덱싱 버튼**
   - **인덱싱 시작**: 선택된 경로 인덱싱
   - **인덱싱 중지**: 진행 중인 인덱싱 중지

2. **📄 파일 리스트**
   - 검색 결과 표시
   - 컬럼: 이름, 크기, 수정한 날짜, 경로
   - ✓ 표시: 인덱싱된 파일
   - 클릭 시 우측에 내용 표시

3. **진행 상황**
   - 총 파일 개수
   - 프로그레스 바

### 우측 패널
- **인덱싱 보기 버튼**: DB 통계 표시
- **📝 내역 보기 및 편집**
  - 인덱싱된 파일: 내용 표시
  - 이미지 파일: 미리보기 (추후 구현)
  - 일반 파일: 경로 정보

### 하단 패널
1. **🔍 검색 로그**
   - 검색 진행 상황
   - 검색 결과 요약

2. **📊 인덱싱 로그**
   - 인덱싱 진행 상황
   - 파일별 처리 상태

3. **상태 바**
   - 현재 작업 상태
   - 백엔드 연결 상태

## 🔍 검색 기능

### 검색 규칙

1. **정확 일치 검색**
   ```
   "정확한 문자열"
   ```
   쌍따옴표로 감싸면 정확히 일치하는 것만 검색

2. **AND 조건 검색**
   ```
   단어1 단어2 단어3
   ```
   공백으로 구분된 모든 단어가 포함된 파일 검색

3. **통합 검색**
   - 파일 시스템: 파일명 검색 (재귀적)
   - 데이터베이스: 내용 검색 (인덱싱된 파일)
   - 중복 제거: DB 결과 우선

### 검색 대상
- 현재 선택된 디렉토리 하위 전체
- 즐겨찾기 또는 폴더 트리에서 선택

## 📊 인덱싱 기능

### 인덱싱 시작
1. 좌측에서 경로 선택 (즐겨찾기 또는 폴더 트리)
2. "인덱싱 시작" 버튼 클릭
3. 확인 대화상자에서 "Yes" 선택

### 진행 상황
- **실시간 로그**: 처리 중인 파일 표시
- **프로그레스 바**: 진행률 표시
- **상태**: "인덱싱 중: X/Y"
- **버튼 상태 변경**: Start 비활성화, Stop 활성화

### 완료
- 완료 메시지 표시
- 버튼 상태 복원
- DB 자동 최적화 (VACUUM)

## 🛠️ 기능 상세

### Worker Thread (QThread)

**SearchWorker**
- Signal: progress_signal, log_signal, status_signal, finished_signal
- Flask API `/api/search/combined` 호출
- 비동기 검색 실행

**IndexingWorker**
- Signal: progress_signal, log_signal, status_signal, finished_signal
- Flask API `/api/indexing/start` 호출
- 상태 폴링 (1초 간격)
- 비동기 인덱싱 실행

### API 통신

모든 Flask API 호출은 `requests` 라이브러리 사용:
- `GET /api/health` - 연결 확인
- `POST /api/search/combined` - 통합 검색
- `POST /api/indexing/start` - 인덱싱 시작
- `POST /api/indexing/stop` - 인덱싱 중지
- `GET /api/indexing/status` - 인덱싱 상태
- `POST /api/indexing/indexed-content` - 파일 내용 조회
- `GET /api/statistics` - DB 통계

## 🎨 UI 스타일

### 파일 리스트
- **수평선**: 없음
- **수직선**: 점선 (dotted #ddd)
- **테두리**: 1px solid #ccc

### 로그 창
- 최대 높이: 150px
- 읽기 전용
- 자동 스크롤

### 상태 바
- 연결 성공: 초록색 배경 (#d4edda)
- 경고: 노란색 배경 (#fff3cd)
- 오류: 빨간색 배경 (#f8d7da)

## 🐛 문제 해결

### GUI가 실행되지 않음

```bash
pip install PyQt6
```

### 백엔드 연결 실패

1. Flask 서버 실행 확인:
   ```bash
   curl http://127.0.0.1:5000/api/health
   ```

2. 방화벽 확인

3. 포트 충돌 확인

### 검색이 느림

- 검색 경로를 구체적으로 설정
- 인덱싱 먼저 실행
- 검색어를 명확하게 입력

## 📝 단축키 (추후 구현 예정)

- `Ctrl+F`: 검색 포커스
- `Ctrl+I`: 인덱싱 시작
- `Ctrl+R`: 새로고침
- `Ctrl+Q`: 종료

## 🔗 관련 파일

- `gui_pyqt6.py` - PyQt6 GUI 메인 파일
- `server.py` - Flask 백엔드 서버
- `search.py` - 검색 엔진
- `indexer.py` - 인덱싱 엔진
- `database.py` - 데이터베이스 관리

## 📄 라이선스

MIT License






