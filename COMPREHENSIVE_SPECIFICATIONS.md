# Advanced Explorer - 종합 규격 명세서

Advanced Explorer의 모든 기능 규격을 통합 정리한 문서입니다.

---

## 📋 목차

1. [색인(인덱싱) 시스템](#1-색인인덱싱-시스템)
2. [Indexing Log 규격](#2-indexing-log-규격)
3. [Search Log 규격](#3-search-log-규격)
4. [DB 조회 및 파일 기록](#4-db-조회-및-파일-기록)
5. [UI 컨트롤 (버튼/상태)](#5-ui-컨트롤-버튼상태)
6. [스레드 및 리소스 관리](#6-스레드-및-리소스-관리)
7. [파일 접근 로직](#7-파일-접근-로직)
8. [다국어/인코딩 지원](#8-다국어인코딩-지원)

---

## 1. 색인(인덱싱) 시스템

### 1.1 상태 표시

#### 색인 라인 상태 문구
| 상황 | 표시 문구 | 색상 |
|------|----------|------|
| 대기 | "인덱싱 대기 중..." | 회색 |
| 시작 | "인덱싱 시작 중..." | 파란색 |
| **진행 중** | **"인덱싱 중... (50/100)"** | **파란색** |
| 완료 | "인덱싱 완료" | 초록색 |
| 중지 | "중지됨" | 노란색 |
| 재시도 대기 | "대기 중 (재시도 5개)" | 주황색 |

**✅ 개선 완료**: ~~"대기중"~~ → **"인덱싱 중"**

```typescript
// App.tsx
setIndexingStatus(`인덱싱 중... (${indexed}/${total})`);
```

#### 누적 카운트 라벨
```
인덱싱 DB 저장 파일 수: 1,234 개
```

**✅ 구현 완료**: DB에 저장 완료된 파일 수를 실시간 표시

```typescript
<span className="text-[#D0D0D0]">
  인덱싱 DB 저장 파일 수: {dbTotalCount.toLocaleString()} 개
</span>
```

---

## 2. Indexing Log 규격

### 2.1 표시 항목

| 항목 | 설명 | 필수 |
|------|------|------|
| **시간** | HH:MM:SS | ✅ |
| **파일명** | 현재 인덱싱 파일 | ✅ |
| **토큰 수** | 추출된 토큰 개수 | ✅ |
| **진행상태** | 3단계 구분 | ✅ |
| **DB 저장 여부** | 저장 완료/대기/오류 | ✅ |

### 2.2 진행상태 3단계

#### Stage 1: "처리중"
```
[12:34:56] ⟳ 처리중  document.pdf
```
- 파일 처리 시작
- 텍스트 추출 중

#### Stage 2: "인덱싱 완료"
```
[12:34:57] ✓ 인덱싱 완료  document.pdf  1,234토큰  [⊗ DB 대기]
```
- 텍스트 추출 완료
- 토큰 계산 완료
- 배치에 추가됨

#### Stage 3: "DB 저장 완료"
```
[12:35:00] ✓ DB 저장 완료  document.pdf  1,234토큰  [✓ DB 완료]
```
- 20개 파일 배치 커밋 완료
- DB에 영구 저장됨

### 2.3 표시 위치

**✅ 올바른 위치**: Indexing Log 영역 (우측 하단)
**❌ 표시 안 함**: Search Log 영역

```
┌─────────────────────────────────────┐
│      Indexing Log 영역               │
├─────────────────────────────────────┤
│ [12:34:56] ⟳ 처리중  file1.pdf     │
│ [12:34:57] ✓ 완료    file2.docx    │
│ [12:34:58] ⟳ 처리중  file3.xlsx    │
└─────────────────────────────────────┘
```

### 2.4 로그 파일 통합

**파일**: `python-backend/logs/indexing_log.txt`

**기록 내용**:
- 파일명
- 토큰 수
- 성공/실패 상태
- 실패 사유 (해당 시)
- 타임스탬프

**포맷**:
```
[2025-12-07 12:34:56] Success | document.pdf | 12,345자 / 1,234토큰 | ✓ DB 저장 완료
[2025-12-07 12:34:57] Skip    | locked.xlsx  | File is open in another program
[2025-12-07 12:34:58] Error   | corrupt.pdf  | Parse error: Invalid PDF structure
```

**✅ 구현 완료**: `indexer.py`의 `_write_indexing_log()` 메서드

---

## 3. Search Log 규격

### 3.1 표시 항목 (검색만)

| 항목 | 설명 | 예시 |
|------|------|------|
| **검색어** | 사용자 입력 | "Python" |
| **탐색 과정** | 검색 진행 상황 | "검색 중...", "100개 파일 검색 완료" |
| **일치 단어 수** | 파일별 매칭 개수 | "file.txt - 5개 일치" |
| **검색 결과** | 총 결과 수 | "총 23개 파일 발견" |

### 3.2 표시 형식

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 검색 시작
  검색어: "Python"
  대상: C:\Projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

검색 중... 데이터베이스 조회

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 검색 완료 (0.234초)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 검색 결과: 총 23개 파일 발견

📄 #1: C:\Projects\main.py
   매칭: 5개 일치
   
📄 #2: C:\Projects\utils.py
   매칭: 3개 일치

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3.3 제외 항목

**❌ Search Log에 표시하지 않음**:
- ~~색인 시작/완료~~
- ~~인덱싱 진행 상황~~
- ~~파일 처리 과정~~
- ~~DB 저장 상태~~

**✅ 이미 구현됨**: 색인 상황은 `addIndexingMessage()`로 Indexing Log에만 표시

---

## 4. DB 조회 및 파일 기록

### 4.1 DB 조회 화면

#### 진입 방법
```
내용 보기 및 편집 → [인덱싱 보기] 버튼 클릭
```

#### 조회 쿼리
```sql
SELECT * FROM files_fts 
ORDER BY mtime DESC 
LIMIT 1000
```

#### 표시 형식 (텍스트)
```
============================================================
인덱싱 DB 조회 결과 (총 1,234개)
============================================================

#1. C:\Documents\report.docx
    수정: 2025-12-07 12:34:56
    크기: 12,345자
    내용 미리보기: "이 문서는 2025년도 연간 보고서입니다..."

#2. C:\Projects\main.py
    수정: 2025-12-07 11:22:33
    크기: 8,765자
    내용 미리보기: "import os\nimport sys\n\ndef main()..."

...

============================================================
```

**✅ 구현 완료**: `showIndexingLog` 상태로 전환

### 4.2 자동 새로고침

**주기**: 1분 (60초)
**조건**: "인덱싱 보기" 화면이 열려있을 때만

```typescript
useEffect(() => {
  if (!showIndexingLog) return;
  
  const refreshDB = async () => {
    const dbResponse = await BackendAPI.getIndexedDatabase(1000, 0);
    setIndexedDatabase(dbResponse.files);
    setDbTotalCount(dbResponse.total_count);
  };
  
  const dbRefreshInterval = setInterval(refreshDB, 60000); // 1분
  
  return () => clearInterval(dbRefreshInterval);
}, [showIndexingLog]);
```

**✅ 구현 완료**: `App.tsx`

### 4.3 Indexed.txt 파일 기록

**파일**: `python-backend/logs/Indexed.txt`

**기록 시점**: DB 저장 완료 시

**포맷**:
```
============================================================
[2025-12-07 12:34:56] C:\Documents\report.docx
============================================================
디렉토리: C:\Documents
파일명: report.docx
파일 크기: 12,345자
토큰 수: 1,234토큰
DB 상태: ✓ 저장 완료

--- 인덱싱 내용 미리보기 (첫 500자) ---
이 문서는 2025년도 연간 보고서입니다. 
주요 성과와 향후 계획을 포함하고 있습니다.
...
============================================================


============================================================
[2025-12-07 12:35:01] C:\Projects\main.py
============================================================
디렉토리: C:\Projects
파일명: main.py
파일 크기: 8,765자
토큰 수: 987토큰
DB 상태: ✓ 저장 완료

--- 인덱싱 내용 미리보기 (첫 500자) ---
import os
import sys

def main():
    print("Hello, World!")
...
============================================================
```

**✅ 구현 완료**: `indexer.py`의 `_write_indexed_file()` 메서드

### 4.4 앱 종료 시 Lock 해제

**대상**:
- ✅ SQLite DB (`file_index.db`)
- ✅ 로그 파일 (`indexing_log.txt`, `Indexed.txt`, `error.txt`, `skipcheck.txt`)
- ✅ 모든 파일 핸들

**구현**:
```python
# server.py - cleanup()
def cleanup():
    # 1. 인덱서 정리
    if indexer:
        indexer.cleanup()
    
    # 2. DB 연결 종료
    if db_manager:
        db_manager.conn.commit()  # 보류 중인 변경사항 커밋
        db_manager.close()
    
    # 3. 로깅 핸들러 종료
    for handler in logging.root.handlers[:]:
        handler.flush()
        handler.close()
        logging.root.removeHandler(handler)
```

**✅ 구현 완료**: `server.py`, `database.py`, `indexer.py`

---

## 5. UI 컨트롤 (버튼/상태)

### 5.1 버튼 Enable/Disable

#### 시작 버튼
| 상황 | 상태 | 이유 |
|------|------|------|
| 대기 중 | **Enable** | 인덱싱 시작 가능 |
| **인덱싱 중** | **Disable** | 중복 시작 방지 |
| 중지 중 | Disable | 중지 처리 중 |

#### 중지 버튼
| 상황 | 상태 | 이유 |
|------|------|------|
| 대기 중 | Disable | 중지할 작업 없음 |
| **인덱싱 중** | **Enable** | 중지 가능 |
| 중지 중 | Disable | 중지 처리 중 |

### 5.2 구현 코드

```typescript
// App.tsx

// 시작 버튼
<button
  onClick={handleIndexStart}
  disabled={isIndexing || isIndexStopping}  // 인덱싱 중이거나 중지 중이면 비활성화
  className={`... ${isIndexing || isIndexStopping ? 'opacity-50 cursor-not-allowed' : ''}`}
>
  <Play size={14} />
  시작
</button>

// 중지 버튼
<button
  onClick={handleIndexStop}
  disabled={!isIndexing || isIndexStopping}  // 인덱싱 중이 아니거나 중지 중이면 비활성화
  className={`... ${!isIndexing || isIndexStopping ? 'opacity-50 cursor-not-allowed' : ''}`}
>
  <Square size={14} />
  중지
</button>
```

**✅ 구현 필요**: 현재 버튼 상태 제어 로직 추가

---

## 6. 스레드 및 리소스 관리

### 6.1 백그라운드 스레드

#### 인덱싱 스레드
- **역할**: 파일 크롤링 및 텍스트 추출
- **생명주기**: 인덱싱 시작 → 완료/중지
- **종료 조건**: 
  - 모든 파일 처리 완료
  - 사용자가 중지 버튼 클릭
  - 앱 종료

#### 재시도 워커 스레드
- **역할**: Skip된 파일 5분마다 재시도
- **생명주기**: 인덱싱 완료 후 자동 시작
- **종료 조건**:
  - 재시도할 파일 없음
  - 앱 종료

### 6.2 안전 종료 프로세스

#### Electron → Python Backend 종료 요청
```javascript
// electron/main.cjs
app.on('before-quit', async (event) => {
  if (pythonProcess) {
    event.preventDefault();  // 앱 종료 일시 중단
    
    try {
      // 1. Shutdown API 호출 (5초 타임아웃)
      await fetch('http://127.0.0.1:5000/api/shutdown', { 
        method: 'POST' 
      });
      
      console.log('✓ 백엔드 안전 종료 완료');
    } catch (error) {
      // 2. 실패 시 프로세스 강제 종료
      pythonProcess.kill('SIGTERM');
      
      setTimeout(() => {
        if (!pythonProcess.killed) {
          pythonProcess.kill('SIGKILL');
        }
      }, 1000);
    } finally {
      pythonProcess = null;
      app.quit();  // 앱 종료 재개
    }
  }
});
```

#### Python Backend 종료 순서
```python
# server.py - cleanup()
def cleanup():
    # 1. 인덱싱 스레드 중지
    indexer.stop_indexing()
    if indexer.current_thread.is_alive():
        indexer.current_thread.join(timeout=10)
    
    # 2. 재시도 워커 중지
    indexer.stop_retry_worker()
    if indexer.retry_thread.is_alive():
        indexer.retry_thread.join(timeout=5)
    
    # 3. DB 커밋 및 종료
    db_manager.conn.commit()
    db_manager.close()
    
    # 4. 로그 핸들러 종료
    for handler in logging.root.handlers:
        handler.flush()
        handler.close()
```

**✅ 구현 완료**: `electron/main.cjs`, `server.py`

---

## 7. 파일 접근 로직

### 7.1 열린 파일 처리

**원칙**: 사용자가 열어둔 파일은 절대 닫지 않음

#### 처리 흐름
```
파일 발견
    ↓
열려있는가?
    ↓
  YES → ReadOnly 접근 시도
         ↓
       성공? → 인덱싱
         ↓
       실패? → Skip + skipcheck.txt + 재시도 큐
    ↓
   NO → 일반 읽기 → 인덱싱
```

#### Office 파일 (COM Automation)
```python
# ReadOnly=True로 열기
doc = word.Documents.Open(file_path, ReadOnly=True)
ppt = ppt_app.Presentations.Open(file_path, ReadOnly=True, WithWindow=False)
workbook = excel.Workbooks.Open(file_path, ReadOnly=True)
```

#### 텍스트 파일
```python
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
except PermissionError:
    # 파일이 열려있음 → Skip
    self._log_skip(file_path, "File is open in another program")
```

**✅ 구현 완료**: `indexer.py`

### 7.2 재시도 메커니즘

**간격**: 5분 (300초)
**최대 재시도**: 5회
**대상**: 파일 잠금, 권한 오류, 타임아웃, 암호 보호

```python
self.retry_interval = 300  # 5분
```

**✅ 구현 완료**: `indexer.py`의 `_retry_worker()`

### 7.3 배치 커밋

**크기**: 20개 파일
**목적**: 실시간성 + 메모리 효율 + 안정성

```python
batch_size = 20

if len(batch) >= batch_size:
    self.db.insert_files_batch(batch_for_db)
    # → UI에 "DB 저장 완료" 표시
```

**✅ 구현 완료**: `indexer.py`

---

## 8. 다국어/인코딩 지원

### 8.1 UTF-8 통일

**모든 영역**:
- ✅ HTML: `<meta charset="UTF-8" />`
- ✅ Python: `# -*- coding: utf-8 -*-`
- ✅ Flask: `JSON_AS_ASCII = False`
- ✅ SQLite: `PRAGMA encoding = 'UTF-8'`
- ✅ 로그 파일: `encoding='utf-8'`
- ✅ Electron: `PYTHONIOENCODING='utf-8'`

### 8.2 지원 언어

- ✅ 한글
- ✅ 영어
- ✅ 일본어
- ✅ 중국어
- ✅ 이모지

**✅ 검증 완료**: `test_encoding.py` 테스트 스크립트

---

## 📊 전체 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                   Electron (Main Process)               │
│                                                         │
│  ┌─────────────┐         ┌──────────────┐             │
│  │ Python 프로세스│◄─────►│ Shutdown API │             │
│  │   관리       │         │   (안전종료)  │             │
│  └─────────────┘         └──────────────┘             │
└──────────────┬──────────────────────────────────────────┘
               │
               │ HTTP API
               │
┌──────────────▼──────────────────────────────────────────┐
│              Flask Backend (Python)                     │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  Indexer     │  │  DB Manager  │  │ Search      │  │
│  │  (스레드)     │  │  (SQLite)    │  │  Engine     │  │
│  └──────────────┘  └──────────────┘  └─────────────┘  │
│         │                 │                            │
│         ├─ indexing_thread (파일 처리)                  │
│         └─ retry_thread    (재시도)                     │
│                                                         │
└──────────────┬──────────────────────────────────────────┘
               │
               │ JSON Response
               │
┌──────────────▼──────────────────────────────────────────┐
│           React Frontend (TypeScript)                   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ Indexing Log │  │ Search Log   │  │ DB 조회     │  │
│  │ (색인 전용)   │  │ (검색 전용)   │  │ (1분 자동)  │  │
│  └──────────────┘  └──────────────┘  └─────────────┘  │
│                                                         │
│  [시작 버튼 Enable/Disable]                             │
│  [중지 버튼 Enable/Disable]                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ 구현 상태 종합

| 번호 | 항목 | 상태 | 비고 |
|-----|------|------|------|
| 1 | "대기중" → "인덱싱 중" | ✅ 완료 | App.tsx |
| 2 | indexing_log.txt 통합 | ✅ 완료 | indexer.py |
| 3 | Indexing Log만 표시 | ✅ 완료 | addIndexingMessage() |
| 4 | "인덱싱 DB 저장 파일 수" | ✅ 완료 | dbTotalCount |
| 5 | Search Log 규격 | ✅ 완료 | addSearchLog() |
| 6 | DB 조회 화면 | ✅ 완료 | showIndexingLog |
| 7 | 1분 자동 새로고침 | ✅ 완료 | useEffect(60s) |
| 8 | Indexed.txt 기록 | ✅ 완료 | _write_indexed_file() |
| 9 | Lock 해제 | ✅ 완료 | cleanup() |
| 10 | 버튼 Enable/Disable | ⚠️ 개선 필요 | 코드 추가 |
| 11 | 스레드 안전 종료 | ✅ 완료 | cleanup(), before-quit |
| 12 | 열린 파일 처리 | ✅ 완료 | ReadOnly + 재시도 |
| 13 | 20개마다 Commit | ✅ 완료 | batch_size=20 |
| 14 | 멈춤 원인 로깅 | ✅ 완료 | 타입별 구분, 지연 감지 |
| 15 | UTF-8 통일 | ✅ 완료 | 전체 영역 |

---

## 📚 관련 문서

1. **FILE_ACCESS_LOGIC.md** - 파일 접근 및 인덱싱 처리 로직
2. **UTF8_ENCODING_GUIDE.md** - 다국어/인코딩 통합 가이드
3. **INDEXING_LOG_SPEC.md** - Indexing Log 상세 규격
4. **IMPLEMENTATION_STATUS.md** - 항목 14-20 구현 상태

---

**모든 기능이 체계적으로 정의되고 대부분 구현 완료되었습니다!** ✅

남은 작업: 버튼 Enable/Disable 로직 보강

