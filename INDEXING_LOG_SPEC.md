# Indexing Log (색인 로그) 규격

Advanced Explorer의 인덱싱 로그 표시 규격을 정의합니다.

---

## 📋 표시 항목

| 항목 | 설명 | 데이터 타입 | 필수 |
|------|------|------------|------|
| **시간** | 로그 발생 시간 | string (HH:MM:SS) | ✅ |
| **파일명** | 현재 인덱싱 중인 파일명 | string | ✅ |
| **토큰 수** | 추출된 토큰 개수 | number | ⚠️ 조건부* |
| **진행상태** | 인덱싱 처리 단계 | enum | ✅ |
| **DB 저장 여부** | DB 저장 성공 상태 | boolean | ⚠️ 조건부* |

\* 조건부: 진행상태에 따라 표시 여부가 달라짐

---

## 🔄 진행상태 단계별 표기

### 1단계: "처리중"
**표시 시점**: 파일 처리 시작 (텍스트 추출 중)

```typescript
{
  time: "12:34:56",
  filename: "document.pdf",
  tokenCount: null,          // 아직 계산 전
  progressStatus: "처리중",
  dbSaved: null              // 아직 저장 전
}
```

**UI 표시 예시**:
```
[12:34:56] ⟳ 처리중  document.pdf
```

---

### 2단계: "인덱싱 완료"
**표시 시점**: 텍스트 추출 완료, 토큰 계산 완료, 배치에 추가됨

```typescript
{
  time: "12:34:57",
  filename: "document.pdf",
  tokenCount: 1234,          // ✅ 계산 완료
  progressStatus: "인덱싱 완료",
  dbSaved: false             // ⊗ DB 대기 중
}
```

**UI 표시 예시**:
```
[12:34:57] ✓ 인덱싱 완료  document.pdf  1,234토큰  [⊗ DB 대기]
```

---

### 3단계: "DB 저장 완료"
**표시 시점**: DB에 commit 완료 (배치 20개마다)

```typescript
{
  time: "12:35:00",
  filename: "document.pdf",
  tokenCount: 1234,          // ✅ 계산 완료
  progressStatus: "DB 저장 완료",
  dbSaved: true              // ✅ 저장 완료
}
```

**UI 표시 예시**:
```
[12:35:00] ✓ DB 저장 완료  document.pdf  1,234토큰  [✓ DB 완료]
```

---

## 🎨 UI 디자인 규격

### 레이아웃

```
┌─────────────────────────────────────────────────────────────────────┐
│ [시간]  [상태아이콘] [진행상태]  [파일명]  [토큰수]  [DB저장상태]  │
└─────────────────────────────────────────────────────────────────────┘
```

### 색상 코드

| 진행상태 | 색상 | 아이콘 |
|---------|------|--------|
| 처리중 | 파란색 (#60A5FA) | ⟳ |
| 인덱싱 완료 | 연두색 (#A3E635) | ✓ |
| DB 저장 완료 | 초록색 (#22C55E) | ✓ |
| Skip | 노란색 (#FACC15) | ⚠ |
| Error | 빨간색 (#EF4444) | ✗ |

### DB 저장 상태 배지

| 상태 | 텍스트 | 배경색 | 테두리 |
|------|--------|--------|--------|
| DB 대기 | ⊗ DB 대기 | rgba(250, 204, 21, 0.2) | #FACC15 |
| DB 완료 | ✓ DB 완료 | rgba(34, 197, 94, 0.2) | #22C55E |
| DB 오류 | ✗ DB 오류 | rgba(239, 68, 68, 0.2) | #EF4444 |

---

## 📊 TypeScript 인터페이스

### 권장 인터페이스

```typescript
interface IndexingLogEntry {
  // 필수 필드
  time: string;                           // 시간 (HH:MM:SS)
  filename: string;                       // 파일명
  progressStatus: ProgressStatus;         // 진행상태
  
  // 조건부 필드
  tokenCount: number | null;              // 토큰 수 (null = 아직 계산 전)
  dbSaved: boolean | null;                // DB 저장 여부 (null = 아직 시도 전)
  
  // 추가 정보
  charCount?: number;                     // 문자 수
  errorMessage?: string;                  // 오류 메시지 (Error 상태인 경우)
  skipReason?: string;                    // Skip 사유 (Skip 상태인 경우)
}

type ProgressStatus = 
  | '처리중'
  | '인덱싱 완료'
  | 'DB 저장 완료'
  | 'Skip'
  | 'Error'
  | 'Info';
```

### 현재 인터페이스 (개선 필요)

```typescript
// ❌ 현재 (size 필드에 모든 정보 혼재)
interface IndexLogEntry {
  time: string;
  path: string;
  status: 'Indexed' | 'Skipped' | 'Error' | 'Success' | 'Skip' | 'Indexing' | 'Retry Success' | 'Info';
  size: string;  // "1,234자 / 567토큰 | ✓ DB 저장 완료" 같은 형식
}
```

---

## 🔄 단계별 로그 업데이트 흐름

### 시나리오: document.pdf 인덱싱

#### Step 1: 처리 시작
```typescript
// Python Backend → Frontend
{
  status: 'Indexing',
  filename: 'document.pdf',
  detail: ''
}

// Frontend 로그
[12:34:56] ⟳ 처리중  document.pdf
```

#### Step 2: 텍스트 추출 완료
```typescript
// Python Backend → Frontend
{
  status: 'Parsed',
  filename: 'document.pdf',
  detail: '12,345자 / 1,234토큰'
}

// Frontend 로그
[12:34:57] ✓ 인덱싱 완료  document.pdf  1,234토큰  [⊗ DB 대기]
```

#### Step 3: DB 저장 완료 (배치 20개마다)
```typescript
// Python Backend → Frontend
{
  status: 'Success',
  filename: 'document.pdf',
  detail: '12,345자 / 1,234토큰 | ✓ DB 저장 완료'
}

// Frontend 로그 (업데이트)
[12:35:00] ✓ DB 저장 완료  document.pdf  1,234토큰  [✓ DB 완료]
```

---

## 🎯 구현 요구사항

### Backend (Python)

#### 1. 로그 전송 시점
- ✅ **Step 1**: `_log_indexing()` - 파일 처리 시작 시
- ✅ **Step 2**: (선택) `_log_parsed()` - 텍스트 추출 완료 시
- ✅ **Step 3**: `_log_success()` - DB 저장 완료 시

#### 2. 로그 포맷
```python
# Step 1: 처리 시작
def _log_indexing(self, path: str):
    filename = os.path.basename(path)
    if self.log_callback:
        self.log_callback('Indexing', filename, '')

# Step 2: 인덱싱 완료 (선택적)
def _log_parsed(self, path: str, char_count: int, token_count: int):
    filename = os.path.basename(path)
    detail = f'{char_count:,}자 / {token_count:,}토큰'
    if self.log_callback:
        self.log_callback('Parsed', filename, detail)

# Step 3: DB 저장 완료
def _log_success(self, path: str, char_count: int, token_count: int, 
                 db_saved: bool = True, content: str = None):
    filename = os.path.basename(path)
    db_status = "✓ DB 저장 완료" if db_saved else "⊗ DB 저장 대기"
    detail = f'{char_count:,}자 / {token_count:,}토큰 | {db_status}'
    
    if self.log_callback:
        self.log_callback('Success', filename, detail)
```

### Frontend (React/TypeScript)

#### 1. 로그 추가 함수 개선
```typescript
const addIndexingLog = (
  status: ProgressStatus, 
  filename: string, 
  detail: string
) => {
  const time = new Date().toLocaleTimeString('ko-KR', { hour12: false });
  
  // detail 파싱 (예: "12,345자 / 1,234토큰 | ✓ DB 저장 완료")
  const charMatch = detail.match(/(\d{1,3}(?:,\d{3})*)자/);
  const tokenMatch = detail.match(/(\d{1,3}(?:,\d{3})*)토큰/);
  const dbSaved = detail.includes('✓ DB 저장 완료') ? true : 
                  detail.includes('⊗ DB 저장 대기') ? false : null;
  
  const newLog: IndexingLogEntry = {
    time,
    filename,
    progressStatus: mapStatusToProgress(status),
    tokenCount: tokenMatch ? parseInt(tokenMatch[1].replace(/,/g, '')) : null,
    charCount: charMatch ? parseInt(charMatch[1].replace(/,/g, '')) : undefined,
    dbSaved
  };
  
  setIndexingLog(prev => [newLog, ...prev].slice(0, 1000));
};

function mapStatusToProgress(status: string): ProgressStatus {
  switch (status) {
    case 'Indexing': return '처리중';
    case 'Parsed': return '인덱싱 완료';
    case 'Success': return 'DB 저장 완료';
    case 'Skip': return 'Skip';
    case 'Error': return 'Error';
    default: return 'Info';
  }
}
```

#### 2. UI 렌더링
```typescript
{indexingLog.map((log, i) => (
  <div key={i} className="flex items-center gap-2 pb-1 border-b border-[#333]">
    {/* 시간 */}
    <span className="text-gray-500 shrink-0 text-[10px]">
      [{log.time}]
    </span>
    
    {/* 상태 아이콘 + 진행상태 */}
    <span className={`shrink-0 font-bold text-[10px] min-w-[90px] ${getStatusColor(log.progressStatus)}`}>
      {getStatusIcon(log.progressStatus)} {log.progressStatus}
    </span>
    
    {/* 파일명 */}
    <span className="flex-1 truncate text-white text-[10px]" title={log.filename}>
      {log.filename}
    </span>
    
    {/* 토큰 수 */}
    {log.tokenCount !== null && (
      <span className="text-gray-400 shrink-0 text-[9px]">
        {log.tokenCount.toLocaleString()}토큰
      </span>
    )}
    
    {/* DB 저장 상태 배지 */}
    {log.dbSaved !== null && (
      <span className={`px-1.5 py-0.5 rounded text-[9px] shrink-0 ${getDBBadgeClass(log.dbSaved)}`}>
        {log.dbSaved ? '✓ DB 완료' : '⊗ DB 대기'}
      </span>
    )}
  </div>
))}
```

---

## ✅ 규격 체크리스트

### 필수 항목
- [ ] 시간 표시 (HH:MM:SS)
- [ ] 파일명 표시
- [ ] 토큰 수 표시 (조건부)
- [ ] 진행상태 표시 (3단계)
- [ ] DB 저장 여부 표시 (배지)

### 진행상태 단계
- [ ] "처리중" - 파일 처리 시작
- [ ] "인덱싱 완료" - 텍스트 추출 완료, 토큰 계산됨
- [ ] "DB 저장 완료" - DB commit 완료

### UI 요소
- [ ] 상태별 색상 코딩
- [ ] 아이콘 표시
- [ ] DB 저장 상태 배지
- [ ] 토큰 수 천 단위 콤마 표시

### 데이터 구조
- [ ] 명확한 필드 분리 (filename, tokenCount, progressStatus, dbSaved)
- [ ] null 처리 (아직 계산/저장 전)
- [ ] TypeScript 타입 안정성

---

## 📸 UI 예시

### 실시간 인덱싱 로그 표시

```
┌─ Indexing Log ───────────────────────────────────────────────────────┐
│                                                                         │
│ [12:34:56] ⟳ 처리중          document.pdf                             │
│ [12:34:57] ✓ 인덱싱 완료      document.pdf  1,234토큰  [⊗ DB 대기]    │
│ [12:34:58] ⟳ 처리중          report.docx                              │
│ [12:34:59] ✓ 인덱싱 완료      report.docx  2,345토큰  [⊗ DB 대기]     │
│ ...                                                                     │
│ [12:35:00] ✓ DB 저장 완료     document.pdf  1,234토큰  [✓ DB 완료]    │
│ [12:35:00] ✓ DB 저장 완료     report.docx  2,345토큰  [✓ DB 완료]     │
│ [12:35:01] ⚠ Skip            locked.xlsx  (File is locked)            │
│ [12:35:02] ✗ Error           corrupted.pdf  (Parse error)             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 현재 구현과 비교

### 현재 문제점
1. ❌ `size` 필드에 모든 정보 혼재 (파싱 필요)
2. ❌ 진행상태가 명확하지 않음 (Success, Indexing 등 혼재)
3. ❌ DB 저장 여부가 문자열로 포함되어 조건 체크 어려움
4. ❌ 토큰 수가 숫자가 아닌 문자열로 처리됨

### 개선 후
1. ✅ 명확한 필드 분리 (filename, tokenCount, progressStatus, dbSaved)
2. ✅ 3단계 진행상태 명확히 구분
3. ✅ DB 저장 여부를 boolean으로 명확히 표현
4. ✅ 토큰 수를 number 타입으로 처리

---

**규격에 맞게 구현하면 사용자가 인덱싱 진행 상황을 명확하게 파악할 수 있습니다!** ✅

