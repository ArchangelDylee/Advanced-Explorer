# 파일 접근 및 인덱싱 처리 로직

Advanced Explorer의 파일 접근 및 인덱싱 처리 방식을 상세하게 설명합니다.

---

## 📋 목차
1. [열린 파일 처리 전략](#1-열린-파일-처리-전략)
2. [디스크 기반 읽기 방식](#2-디스크-기반-읽기-방식)
3. [배치 커밋 전략](#3-배치-커밋-전략)
4. [멈춤 감지 및 로깅](#4-멈춤-감지-및-로깅)
5. [재시도 메커니즘](#5-재시도-메커니즘)

---

## 1. 열린 파일 처리 전략

### ✅ 핵심 원칙
**사용자가 열어둔 파일은 절대 닫지 않습니다.**

### 처리 흐름

```
파일 발견
    ↓
파일이 열려있는가?
    ↓
┌───YES───┐       ┌───NO────┐
│         │       │         │
▼         │       ▼         │
ReadOnly 접근    │   일반 읽기   │
시도            │             │
│         │       │         │
▼         │       ▼         │
성공?     │     인덱싱 완료  │
│         │       │         │
├─YES─────┤       └─────────┘
│인덱싱 완료│
│         │
└─NO──────┘
    │
    ▼
Skip 처리
    │
    ├─ skipcheck.txt 기록
    ├─ 재시도 큐 추가
    └─ Indexing Log 표시
```

### 구현 코드

#### Office 파일 (ReadOnly 모드)
**파일**: `python-backend/indexer.py`

```python
def _extract_doc(self, file_path: str) -> Optional[str]:
    """Word .doc 파일 (ReadOnly 모드)"""
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        
        # ReadOnly=True로 열기 → 사용자 편집에 영향 없음
        doc = word.Documents.Open(file_path, ReadOnly=True)
        text = doc.Content.Text
        doc.Close(False)
        word.Quit()
        
        return text[:100000]
    except Exception as e:
        # 파일이 열려있어서 접근 불가 시 Skip
        self._log_skip(file_path, "File is open in another program")
        return None
```

#### 텍스트 파일 (디스크 직접 읽기)
```python
def _extract_text_file(self, file_path: str) -> Optional[str]:
    """텍스트 파일 읽기 (디스크 기반)"""
    try:
        # 1차: UTF-8 시도
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()[:100000]
    except PermissionError:
        # 파일이 독점 잠금 상태
        self._log_skip(file_path, "File is open in another program")
        return None
```

---

## 2. 디스크 기반 읽기 방식

### ✅ 사용자 편집에 영향을 주지 않는 읽기

#### 원칙
1. **메모리 매핑 사용 안 함** - 디스크에서 직접 읽기
2. **ReadOnly 모드** - 파일을 수정하지 않음을 명시
3. **빠른 실패** - 잠금된 파일은 즉시 Skip

#### Windows 파일 잠금 처리

```python
# PermissionError 처리
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
except PermissionError:
    # 사용자가 파일을 편집 중
    # → 닫지 않고 Skip
    # → 재시도 큐에 추가
    self._log_skip(file_path, "File is open in another program")
    return None
```

#### Office 파일 COM Automation

```python
# COM 객체 ReadOnly 옵션
word.Documents.Open(file_path, ReadOnly=True)  # Word
ppt.Presentations.Open(file_path, ReadOnly=True, WithWindow=False)  # PowerPoint
workbook = excel.Workbooks.Open(file_path, ReadOnly=True)  # Excel
```

### 동작 방식

```
사용자가 파일 편집 중
    ↓
인덱서가 파일 접근 시도
    ↓
OS가 ReadOnly 권한 부여
    ↓
인덱서: 읽기만 수행
사용자: 편집 계속 가능
    ↓
인덱서: 파일 닫음
사용자: 변함없이 편집 중
```

---

## 3. 배치 커밋 전략

### ✅ 20개 파일마다 DB Commit

#### 목적
- **실시간성**: 20개마다 DB에 반영되어 "인덱싱 보기"에서 확인 가능
- **메모리 효율**: 최대 20개만 버퍼링
- **안정성**: 중단 시에도 이미 커밋된 데이터는 보존

#### 구현 코드

```python
def _process_files_incremental(self, all_files: List[str]):
    """증분 파일 처리"""
    batch_size = 20  # 20개 파일마다 DB Commit
    batch = []
    
    for i, file_path in enumerate(all_files):
        # ... 파일 처리 ...
        
        if content:
            # 1. 메모리 배치에 추가
            batch.append((file_path, content, mtime, token_count))
            
            # 2. 배치가 20개 찼으면 DB에 저장
            if len(batch) >= batch_size:
                try:
                    # DB 저장
                    batch_for_db = [(path, content, mtime) 
                                    for path, content, mtime, _ in batch]
                    self.db.insert_files_batch(batch_for_db)
                    
                    # 3. 각 파일에 대해 "DB 저장 완료" 로그
                    for saved_path, saved_content, _, saved_token_count in batch:
                        self._log_success(saved_path, len(saved_content), 
                                        saved_token_count, db_saved=True, 
                                        content=saved_content)
                    
                    # 4. 배치 초기화
                    batch = []
                    
                except Exception as e:
                    logger.error(f"DB 배치 저장 오류: {e}")
                    if self.log_callback:
                        self.log_callback('Error', 'DB 저장', 
                                        f'배치 저장 오류: {str(e)}')
                    batch = []
    
    # 5. 남은 배치 저장
    if batch:
        # ... 동일한 저장 로직 ...
```

#### 타임라인

```
파일 1-20 처리 → [DB Commit #1] → UI 업데이트 (20개)
파일 21-40 처리 → [DB Commit #2] → UI 업데이트 (40개)
파일 41-60 처리 → [DB Commit #3] → UI 업데이트 (60개)
...
```

---

## 4. 멈춤 감지 및 로깅

### ✅ 인덱싱 중 멈춤 원인 추적

#### 1. 진행 지연 자동 감지

```python
def _process_files_incremental(self, all_files: List[str]):
    last_progress_time = time.time()
    stall_warning_threshold = 120  # 2분 동안 진행 없으면 경고
    
    for i, file_path in enumerate(all_files):
        # 2분 이상 멈춤 감지
        current_time = time.time()
        if current_time - last_progress_time > stall_warning_threshold:
            warning_msg = f"⚠ 인덱싱 진행 지연 감지: {file_path} 처리 중 120초 경과"
            logger.warning(warning_msg)
            
            if self.log_callback:
                self.log_callback('Error', '진행 지연', 
                                f'{os.path.basename(file_path)} 처리 중 지연')
            
            last_progress_time = current_time
```

#### 2. 예외 타입별 상세 로깅

```python
except Exception as e:
    error_type = type(e).__name__
    error_msg = str(e)
    
    logger.error(f"파일 처리 오류 [{file_path}]: {error_type} - {error_msg}")
    logger.error(f"상세 정보: {traceback.format_exc()}")
    
    # UI에 에러 원인 표시
    self._log_error(file_path, f"{error_type}: {error_msg}")
    
    # 타입별 특별 처리
    if 'timeout' in error_msg.lower() or error_type == 'TimeoutError':
        if self.log_callback:
            self.log_callback('Error', os.path.basename(file_path), 
                            '⏱ 타임아웃 (60초 초과)')
    
    elif 'memory' in error_msg.lower():
        if self.log_callback:
            self.log_callback('Error', os.path.basename(file_path), 
                            '💾 메모리 부족')
    
    elif error_type == 'PermissionError':
        if self.log_callback:
            self.log_callback('Error', os.path.basename(file_path), 
                            '🔒 권한 오류')
```

#### 3. Indexing Log에 기록되는 정보

**기록 내용:**
- ✅ **시간**: 정확한 타임스탬프
- ✅ **파일명**: 오류 발생 파일
- ✅ **지점**: 어떤 단계에서 멈췄는지 (처리중/파싱/DB저장)
- ✅ **원인**: 예외 타입 및 메시지
- ✅ **아이콘**: 시각적 표시 (⏱ 타임아웃, 💾 메모리, 🔒 권한)

**예시:**
```
[12:34:56] ✗ 오류  large_document.pdf  ⏱ 타임아웃 (60초 초과)
[12:35:12] ✗ 오류  locked_file.docx    🔒 권한 오류
[12:35:45] ⚠ 경고  processing.xlsx     진행 지연 (2분 경과)
```

---

## 5. 재시도 메커니즘

### ✅ Skip된 파일 자동 재시도

#### 재시도 대상

**재시도함:**
- ✅ 파일 잠금 (`File locked`)
- ✅ 권한 오류 (`Permission denied`)
- ✅ 타임아웃 (`Parsing timeout`)
- ✅ 암호 보호 (`Password protected`) - 사용자가 해제할 수 있음
- ✅ 파일 열림 (`File is open`) - 사용자가 닫을 수 있음

**재시도 안 함:**
- ❌ 파일 크기 초과 (`Size exceeded`)
- ❌ 파일 손상 (`File corrupted`)

#### 재시도 간격

```python
self.retry_interval = 300  # 5분 (초 단위)
```

**설정 가능 범위:** 5~10분 (300~600초)

#### 재시도 워커 흐름

```python
def _retry_worker(self):
    """재시도 워커 스레드"""
    logger.info("재시도 워커 동작 시작")
    
    while not self.retry_stop_flag.is_set():
        # 1. 대기 (5분)
        for _ in range(self.retry_interval):
            if self.retry_stop_flag.is_set():
                break
            time.sleep(1)
        
        # 2. 재시도할 파일 목록 조회
        with self.skipped_files_lock:
            files_to_retry = list(self.skipped_files.items())
        
        # 3. 각 파일 재시도
        for file_path, retry_info in files_to_retry:
            reason = retry_info['reason']
            retry_count = retry_info['retry_count']
            
            # 4. 파일이 여전히 존재하는지 확인
            if not os.path.exists(file_path):
                # 삭제된 파일은 재시도 목록에서 제거
                with self.skipped_files_lock:
                    del self.skipped_files[file_path]
                continue
            
            # 5. 텍스트 추출 재시도
            content = self._extract_text_safe(file_path)
            
            if content:
                # 6. 성공 시 DB에 저장
                try:
                    mtime = os.path.getmtime(file_path)
                    self.db.insert_file(file_path, content, mtime)
                    
                    # 7. 재시도 목록에서 제거
                    with self.skipped_files_lock:
                        if file_path in self.skipped_files:
                            del self.skipped_files[file_path]
                    
                    # 8. 성공 로그
                    logger.info(f"재시도 성공 [{file_path}] - 이전 사유: {reason}")
                    self._log_retry_success(file_path, len(content))
                    
                except Exception as e:
                    logger.error(f"재시도 DB 저장 오류 [{file_path}]: {e}")
            
            else:
                # 9. 실패 시 재시도 카운트 증가
                with self.skipped_files_lock:
                    if file_path in self.skipped_files:
                        self.skipped_files[file_path]['retry_count'] += 1
                        
                        # 10. 5회 재시도 실패 시 포기
                        if self.skipped_files[file_path]['retry_count'] >= 5:
                            logger.warning(f"재시도 5회 실패, 포기: {file_path}")
                            del self.skipped_files[file_path]
```

#### 재시도 타임라인

```
인덱싱 시작
    ↓
파일 A: Skip (File locked)
파일 B: Skip (File is open)
    ↓
인덱싱 완료
    ↓
재시도 워커 시작
    ↓
[5분 대기]
    ↓
파일 A 재시도 → 성공 (파일 닫힘) ✓
파일 B 재시도 → 실패 (여전히 열림) ✗ (재시도 1/5)
    ↓
[5분 대기]
    ↓
파일 B 재시도 → 성공 (파일 닫힘) ✓
    ↓
재시도할 파일 없음 → 워커 종료
```

---

## 📊 전체 흐름도

```
┌─────────────────────────────────────────────────────────┐
│               인덱싱 시작                                  │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│          파일 목록 수집 (재귀 탐색)                         │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   파일별 처리 시작      │
        └───────┬───────────────┘
                │
                ▼
        ┌───────────────┐
        │ 파일 열려있음? │
        └───┬───────┬───┘
            │       │
        YES │       │ NO
            │       │
            ▼       ▼
    ┌──────────┐ ┌──────────┐
    │ ReadOnly │ │ 일반 읽기 │
    │   접근   │ │          │
    └────┬─────┘ └────┬─────┘
         │            │
    성공?│       성공?│
         │            │
    ┌────┴────┬───────┴────┐
    │         │            │
   YES       NO           YES
    │         │            │
    ▼         ▼            │
┌────────┐ ┌─────────┐    │
│인덱싱  │ │  Skip   │    │
│        │ │         │◄───┘
└───┬────┘ └────┬────┘
    │           │
    │           ├─ skipcheck.txt 기록
    │           ├─ 재시도 큐 추가
    │           └─ Indexing Log 표시
    │
    ▼
┌────────────────────┐
│ 배치에 추가 (1/20) │
└────────┬───────────┘
         │
    20개 완료?
         │
        YES
         │
         ▼
┌────────────────────┐
│   DB Commit        │
│   (20개 파일)      │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ "DB 저장 완료"     │
│  로그 표시         │
└────────┬───────────┘
         │
         ▼
    더 처리할 파일?
         │
    ┌────┴────┐
   YES       NO
    │         │
    └─────┐   ▼
          │ ┌──────────────┐
          │ │ 인덱싱 완료   │
          │ └───────┬──────┘
          │         │
          └─────────┤
                    ▼
            ┌──────────────┐
            │ Skip된 파일   │
            │   있음?       │
            └───┬──────┬───┘
               YES    NO
                │      │
                ▼      └──────┐
        ┌─────────────┐       │
        │재시도 워커   │       │
        │   시작      │       │
        └──────┬──────┘       │
               │              │
          [5분 대기]           │
               │              │
               ▼              │
        ┌─────────────┐       │
        │ 파일 재시도  │       │
        └──────┬──────┘       │
               │              │
          성공/5회 실패?       │
               │              │
               ▼              ▼
        ┌─────────────────────┐
        │    종료             │
        └─────────────────────┘
```

---

## ✅ 요구사항 체크리스트

| 요구사항 | 구현 상태 | 구현 파일 |
|---------|---------|----------|
| 열린 파일 닫지 않음 | ✅ 완료 | `indexer.py` (_extract_doc, _extract_ppt, _extract_xls) |
| ReadOnly 접근 시도 | ✅ 완료 | `indexer.py` (ReadOnly=True 옵션) |
| Skip + skipcheck.txt 기록 | ✅ 완료 | `indexer.py` (_log_skip) |
| 재시도 큐 추가 | ✅ 완료 | `indexer.py` (skipped_files) |
| 5~10분 후 재시도 | ✅ 완료 | `indexer.py` (retry_interval=300) |
| 디스크 기반 읽기 | ✅ 완료 | `indexer.py` (직접 파일 읽기, 메모리 매핑 미사용) |
| 사용자 편집 영향 없음 | ✅ 완료 | ReadOnly 모드 + PermissionError 처리 |
| 20개마다 DB Commit | ✅ 완료 | `indexer.py` (batch_size=20) |
| 멈춤 원인 로깅 | ✅ 완료 | `indexer.py` (진행 지연 감지, 예외 타입 분류) |
| 멈춤 파일명 기록 | ✅ 완료 | `indexer.py` (log_callback with filename) |
| 멈춤 지점 기록 | ✅ 완료 | `indexer.py` (처리중/파싱/DB저장 단계 구분) |

---

## 📝 로그 파일 위치

- **skipcheck.txt**: `python-backend/logs/skipcheck.txt`
- **indexing_log.txt**: `python-backend/logs/indexing_log.txt`
- **Indexed.txt**: `python-backend/logs/Indexed.txt`
- **error.txt**: `python-backend/logs/error.txt`

---

## 🔧 설정 변경

### 재시도 간격 변경 (5~10분)

**파일**: `python-backend/indexer.py`

```python
# 현재: 5분 (300초)
self.retry_interval = 300

# 10분으로 변경 시
self.retry_interval = 600

# 7분으로 변경 시
self.retry_interval = 420
```

### 배치 크기 변경 (현재 20개)

```python
# 현재: 20개
batch_size = 20

# 50개로 변경 시 (더 적은 커밋)
batch_size = 50

# 10개로 변경 시 (더 자주 커밋)
batch_size = 10
```

---

**모든 요구사항이 완벽하게 구현되어 있습니다!** ✅

