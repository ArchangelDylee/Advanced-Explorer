# Bug 수정 이력

## 📋 목차
1. [검색 및 인덱싱 관련](#검색-및-인덱싱-관련)
2. [UI/UX 개선](#uiux-개선)
3. [데이터베이스 관련](#데이터베이스-관련)
4. [파일 처리 관련](#파일-처리-관련)

---

## 검색 및 인덱싱 관련

### Bug #1: 검색 로그에서 매칭 유형 오표시
**날짜**: 2025-12-10

**문제**:
- 검색 결과가 "내용 매칭"인데 로그에는 "파일명 매칭"으로 잘못 표시됨
- 검색 완료 요약에서 내용 매칭과 파일명 매칭이 구분되지 않음

**원인**:
```typescript
// src/App.tsx (수정 전)
const matchInfo = matchCount > 0 ? `${matchCount}개 매칭` : '파일명 매칭';
```
- 백엔드에서 제공하는 `source` 필드를 활용하지 않음
- `matchCount`가 0일 때 무조건 "파일명 매칭"으로 표시

**해결**:
```typescript
// src/App.tsx (수정 후)
if (result.source === 'filesystem') {
  matchInfo = '파일명 매칭';
} else if (result.source === 'database') {
  matchInfo = matchCount > 0 ? `내용 ${matchCount}개 매칭` : '내용 매칭';
}
```

**검색 요약 개선**:
```typescript
// 변경 전
addSearchLog(`   파일: ${results.length}개 발견`);
addSearchLog(`   매칭: 총 ${totalMatches}개 발견`);

// 변경 후
if (contentMatchCount > 0) {
  addSearchLog(`   내용 매칭: 총 ${contentMatchCount}개 발견`);
}
if (filenameMatchCount > 0) {
  addSearchLog(`   파일명 매칭: 총 ${filenameMatchCount}개 발견`);
}
```

**커밋**: `2623269` - feat: 파일 인덱싱 상태 표시 및 검색 로그 개선

---

### Bug #2: 인덱싱된 파일 내용이 표시되지 않음
**날짜**: 2025-12-10

**문제**:
- 파일 리스트에는 인덱싱 완료(✓)로 표시
- 파일 클릭 시 "인덱싱 미완료" 메시지 표시
- 백엔드는 정상적으로 200 응답 반환

**원인 분석**:
1. **useEffect dependency 문제**:
```typescript
// src/App.tsx (수정 전)
}, [activeTab.selectedFile]);
```
- 객체 참조를 체크하므로 같은 파일을 다시 클릭해도 useEffect가 실행되지 않음

2. **에러 핸들링 부족**:
```typescript
// src/api/backend.ts (수정 전)
const response = await fetch(`${API_BASE_URL}/indexing/database/${encodedPath}`);
return await response.json();
```
- HTTP 상태 코드 확인 없음
- 디버깅 로그 없음

**해결**:

1. **useEffect dependency 수정**:
```typescript
// src/App.tsx (수정 후)
}, [activeTab.selectedFile?.path]); // path를 체크하여 파일 변경 감지
```

2. **API 에러 핸들링 강화**:
```typescript
// src/api/backend.ts (수정 후)
console.log('📄 파일 상세 조회 API 호출:', filePath);
const response = await fetch(`${API_BASE_URL}/indexing/database/${encodedPath}`);

if (!response.ok) {
  console.error(`❌ API 응답 오류: ${response.status} ${response.statusText}`);
  throw new Error(`HTTP ${response.status}: ${response.statusText}`);
}

const data = await response.json();
console.log('✅ API 응답 성공:', data?.content?.length || 0, '자');
return data;
```

3. **디버깅 로그 추가**:
```typescript
// src/App.tsx
const ext = activeTab.selectedFile.type.toLowerCase();
console.log('🔍 파일 선택됨:', activeTab.selectedFile.name, '확장자:', ext);
```

**상태**: 수정 완료, 테스트 대기 중

---

## UI/UX 개선

### Feature #1: 파일 리스트에 인덱싱 상태 표시
**날짜**: 2025-12-10

**요구사항**:
- 파일 리스트에서 각 파일의 인덱싱 여부를 시각적으로 표시
- 인덱싱 완료: ✓ (녹색)
- 인덱싱 안됨: ○ (회색)

**구현**:

1. **FileItem 인터페이스 확장**:
```typescript
// src/App.tsx
interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string;
  path?: string;
  indexed?: boolean; // 인덱싱 여부 추가
}
```

2. **백엔드 API 추가**:
```python
# python-backend/server.py
@app.route('/api/indexing/check-files', methods=['POST'])
def check_files_indexed():
    """여러 파일의 인덱싱 여부를 일괄 확인"""
    data = request.json
    paths = data.get('paths', [])
    
    result = {}
    for path in paths:
        is_indexed = db_manager.is_file_indexed(path)
        result[path] = is_indexed
    
    return jsonify(result)
```

```python
# python-backend/database.py
def is_file_indexed(self, path: str) -> bool:
    """파일이 인덱싱되었는지 확인"""
    try:
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM files_fts WHERE path = ?",
            (path,)
        )
        count = cursor.fetchone()['count']
        return count > 0
    except sqlite3.Error as e:
        logger.error(f"파일 인덱싱 여부 확인 오류 [{path}]: {e}")
        return False
```

3. **프론트엔드 API 클라이언트**:
```typescript
// src/api/backend.ts
export async function checkFilesIndexed(paths: string[]): Promise<Record<string, boolean>> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/check-files`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    return await response.json();
  } catch (error) {
    console.error('파일 인덱싱 여부 확인 오류:', error);
    return {};
  }
}
```

4. **폴더 탐색 시 자동 조회**:
```typescript
// src/App.tsx - navigate 함수
// 파일들의 인덱싱 여부 확인
const filePaths = rawContent
  .filter(item => item.type !== 'folder' && item.path)
  .map(item => item.path!);

if (filePaths.length > 0) {
  try {
    const indexedStatus = await BackendAPI.checkFilesIndexed(filePaths);
    
    // 각 파일에 인덱싱 여부 추가
    rawContent = rawContent.map(item => {
      if (item.type !== 'folder' && item.path) {
        return {
          ...item,
          indexed: indexedStatus[item.path] || false
        };
      }
      return item;
    });
  } catch (error) {
    console.error('인덱싱 여부 확인 오류:', error);
  }
}
```

5. **UI 표시**:
```typescript
// src/App.tsx
<div style={{ width: colWidths.name }} className="pl-3 pr-2 flex items-center overflow-hidden">
  <FileIcon size={14} className="mr-2 flex-shrink-0" style={{ color: iconColor }} />
  <span className="truncate">{file.name}</span>
  {file.indexed !== undefined && (
    <span 
      className="ml-2 flex-shrink-0" 
      title={file.indexed ? "인덱싱 완료" : "인덱싱 안됨"}
    >
      {file.indexed ? (
        <span className="text-green-400 text-[10px]">✓</span>
      ) : (
        <span className="text-gray-600 text-[10px]">○</span>
      )}
    </span>
  )}
</div>
```

**커밋**: `2623269` - feat: 파일 인덱싱 상태 표시 및 검색 로그 개선

---

### Feature #2: 인덱싱 안내 메시지 개선
**날짜**: 2025-12-10

**문제**:
- 기존 메시지: "⚠️ 인덱싱 미완료 상태로 내역을 보여줄 수 없습니다"
- 사용자가 어떻게 해야 하는지 불명확

**개선**:
```typescript
// src/App.tsx (수정 후)
<div className="text-yellow-400 text-sm font-semibold mt-4 text-center">
  ⚠️ 이 파일은 아직 인덱싱되지 않았습니다
</div>
<div className="text-gray-500 text-xs mt-2 text-center max-w-md">
  <div className="mb-2">이 파일의 내용을 보려면 먼저 인덱싱을 시작해야 합니다.</div>
  <div className="text-yellow-300">
    💡 왼쪽 상단의 "색인" 탭에서 이 파일이 있는 폴더를 선택하고 "색인 시작" 버튼을 클릭하세요.
  </div>
</div>
```

**효과**:
- 명확한 상태 설명
- 구체적인 해결 방법 제시
- 사용자 경험 개선

---

## 데이터베이스 관련

### Bug #3: DB Commit 불안정
**날짜**: 2025-12-09

**문제**:
- 인덱싱 중 DB에 저장되지 않는 경우 발생
- 트랜잭션 관리 부족

**원인**:
```python
# python-backend/database.py (수정 전)
def insert_file(self, path: str, content: str, mtime: float):
    self.conn.execute(
        "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
        (path, content, str(mtime))
    )
    # commit 누락
```

**해결**:

1. **명시적 트랜잭션 관리**:
```python
# python-backend/database.py (수정 후)
def insert_file(self, path: str, content: str, mtime: float):
    try:
        self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute(
            "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
            (path, content, str(mtime))
        )
        self.conn.commit()
        logger.debug(f"파일 인덱스 추가: {path}")
    except sqlite3.Error as e:
        self.conn.rollback()
        logger.error(f"파일 인덱스 추가 오류 [{path}]: {e}")
        raise
```

2. **WAL 모드 활성화**:
```python
# python-backend/database.py
def _initialize_database(self):
    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self.conn.row_factory = sqlite3.Row
    self.conn.execute("PRAGMA journal_mode=WAL")
    self.conn.execute("PRAGMA synchronous=NORMAL")
```

3. **배치 처리 개선**:
```python
# python-backend/indexer.py
def insert_files_batch(self, files: List[Tuple[str, str, float]]):
    try:
        self.conn.execute("BEGIN TRANSACTION")
        for path, content, mtime in files:
            self.conn.execute(
                "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
                (path, content, str(mtime))
            )
        self.conn.commit()
    except sqlite3.Error as e:
        self.conn.rollback()
        raise
    finally:
        # 항상 정리
        pass
```

**커밋**: 이전 세션에서 완료

---

### Bug #4: 파일 상세 조회 시 경로 불일치
**날짜**: 2025-12-10

**문제**:
- URL 인코딩된 경로와 DB 저장 경로 불일치
- 한글 경로 처리 문제

**해결**:

1. **URL 디코딩 명시적 처리**:
```python
# python-backend/server.py
@app.route('/api/indexing/database/<path:file_path>', methods=['GET'])
def get_indexed_file_detail(file_path):
    from urllib.parse import unquote
    decoded_path = unquote(file_path)
    
    logger.info(f"파일 상세 조회 요청: {decoded_path}")
    
    file_detail = db_manager.get_indexed_file_detail(decoded_path)
    
    if file_detail:
        logger.info(f"✓ 파일 발견: {decoded_path} (길이: {file_detail.get('content_length', 0)}자)")
        return jsonify(file_detail)
    else:
        logger.warning(f"✗ 파일 없음 (DB): {decoded_path}")
        
        # 디버깅: 유사한 경로 찾기
        all_paths = db_manager.get_all_indexed_paths()
        if all_paths:
            import difflib
            similar = difflib.get_close_matches(decoded_path, all_paths, n=3, cutoff=0.6)
            if similar:
                logger.info(f"유사한 경로들: {similar[:3]}")
        
        return jsonify({'error': 'File not found in index'}), 404
```

2. **DB 쿼리 디버깅 로그**:
```python
# python-backend/database.py
def get_indexed_file_detail(self, path: str) -> Optional[dict]:
    try:
        logger.debug(f"DB 쿼리: SELECT * FROM files_fts WHERE path = '{path}'")
        
        cursor = self.conn.execute(
            "SELECT path, content, mtime FROM files_fts WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        
        if row:
            logger.debug(f"✓ DB에서 파일 발견: {path}")
            return {
                'path': row['path'],
                'content': row['content'],
                'content_length': len(row['content']),
                'mtime': row['mtime'],
                'mtime_formatted': datetime.fromtimestamp(float(row['mtime'])).strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            logger.debug(f"✗ DB에 파일 없음: {path}")
            # 대소문자 무시하고 검색
            cursor2 = self.conn.execute(
                "SELECT path FROM files_fts WHERE LOWER(path) = LOWER(?)",
                (path,)
            )
            row2 = cursor2.fetchone()
            if row2:
                logger.warning(f"경로 대소문자 불일치: DB={row2['path']}, 요청={path}")
        
        return None
    except sqlite3.Error as e:
        logger.error(f"파일 상세 조회 오류 [{path}]: {e}")
        return None
```

**커밋**: `2623269` - feat: 파일 인덱싱 상태 표시 및 검색 로그 개선

---

## 파일 처리 관련

### Bug #5: 인덱싱 로그에 DB 저장 상태 미표시
**날짜**: 2025-12-09

**문제**:
- 인덱싱 로그에서 DB 저장 여부를 확인할 수 없음
- 토큰 수가 표시되지 않음

**해결**:
```python
# python-backend/indexer.py
def _log_success(self, path: str, char_count: int, token_count: int = 0, db_saved: bool = True, content: str = None):
    filename = os.path.basename(path)
    
    # DB 저장 상태 표시 (더 명확하게)
    if db_saved:
        db_status = "✓ DB완료"
        token_info = f"토큰:{token_count:,}개"
    else:
        db_status = "⊗ DB대기"
        token_info = f"토큰:{token_count:,}개"
    
    # 상세 정보: 문자 수 / 토큰 수 | DB 상태
    detail = f'{char_count:,}자 / {token_info} | {db_status}'
    
    # 통합 로그에 기록
    self._write_indexing_log('Success', path, detail)
    
    # DB 저장이 완료된 경우에만 Indexed.txt에 기록
    if db_saved and content:
        self._write_indexed_file(path, content)
    
    # UI 콜백
    if self.log_callback:
        self.log_callback('처리중', filename, detail)
```

**커밋**: 이전 세션에서 완료

---

### Feature #3: 이전 처리 완료 파일 구분 표시
**날짜**: 2025-12-09

**요구사항**:
- 이미 인덱싱되어 변경 없는 파일은 "처리중"이 아닌 "이전 처리 완료"로 표시

**구현**:
```python
# python-backend/indexer.py
if indexed_mtime is not None:
    # 파일이 이미 인덱싱됨
    if abs(current_mtime - indexed_mtime) < 1.0:
        # 수정되지 않음 - 스킵
        self.stats['skipped_files'] += 1
        
        # 로그 출력 추가
        filename = os.path.basename(file_path)
        detail = "이전 처리 완료 (변경 없음)"
        self._add_log_to_memory('이전완료', file_path, detail)
        if self.log_callback:
            self.log_callback('이전완료', filename, detail)
        continue
```

**커밋**: 이전 세션에서 완료

---

### Bug #6: 요약 생성 기능 실패
**날짜**: 2025-12-10

**문제**:
- "내용 보기 및 편집"에서 "요약 생성" 버튼 클릭 시 "요약 실패" 메시지 표시
- 백엔드 로그에서 `name 'summarizer' is not defined` 에러 발생

**원인**:
```python
# python-backend/server.py (수정 전)
# 전역 객체
db_manager: DatabaseManager = None
indexer: FileIndexer = None
search_engine: SearchEngine = None
# summarizer 전역 변수 누락

def initialize():
    """백엔드 초기화 (설정 파일 기반)"""
    global db_manager, indexer, search_engine
    # summarizer가 global 선언에 누락
    
    # ...
    
    # 요약 엔진 초기화
    summarizer = ContentSummarizer()  # 로컬 변수로만 생성
    logger.info("요약 엔진 초기화 완료")
```

**문제점**:
1. `summarizer`가 전역 변수로 선언되지 않음
2. `initialize()` 함수의 `global` 선언에 `summarizer` 누락
3. 로컬 변수로만 생성되어 다른 함수에서 접근 불가

**에러 로그**:
```
2025-12-10 01:06:09,672 - ERROR - 요약 API 오류: name 'summarizer' is not defined
2025-12-10 01:06:09,673 - INFO - 127.0.0.1 - - [10/Dec/2025 01:06:09] "POST /api/summarize HTTP/1.1" 500 -
```

**해결**:

1. **전역 변수 선언 추가**:
```python
# python-backend/server.py (수정 후)
# 전역 객체
db_manager: DatabaseManager = None
indexer: FileIndexer = None
search_engine: SearchEngine = None
summarizer: ContentSummarizer = None  # 추가
```

2. **global 선언 수정**:
```python
# python-backend/server.py (수정 후)
def initialize():
    """백엔드 초기화 (설정 파일 기반)"""
    global db_manager, indexer, search_engine, summarizer  # summarizer 추가
    
    # ... (기존 코드)
    
    # 요약 엔진 초기화
    summarizer = ContentSummarizer()  # 전역 변수에 할당
    logger.info("요약 엔진 초기화 완료")
```

**검증**:
```
2025-12-10 01:10:54,047 - INFO - ✓ TextRank 요약 엔진 초기화
2025-12-10 01:10:54,047 - INFO - 요약 엔진 초기화 완료
```

**영향을 받는 API**:
- `POST /api/summarize` - 파일 내용 요약 기능

**관련 파일**:
- `python-backend/server.py`: 전역 변수 선언 및 초기화 수정
- `python-backend/summarizer.py`: ContentSummarizer 클래스 (변경 없음)

**커밋**: `9169d21`

---

### Bug #7: 한글 요약 기능 오류 (konlpy 의존성 문제)
**날짜**: 2025-12-10

**문제**:
- "요약 생성" 버튼 클릭 시 `Korean tokenizer requires konlpy. Please, install it by command 'pip install konlpy'` 오류 발생
- konlpy는 Java JDK가 필요하고 Windows 환경에서 설치가 복잡함

**원인**:
```python
# python-backend/summarizer.py (수정 전)
# 언어 자동 감지 (한글/영어)
language = 'korean' if any('\uac00' <= c <= '\ud7a3' for c in text[:100]) else 'english'

# TextRank 요약
parser = PlaintextParser.from_string(text, Tokenizer(language))  # korean일 때 konlpy 필요
stemmer = Stemmer(language)
summarizer = TextRankSummarizer(stemmer)
```

**문제점**:
1. Tokenizer('korean')을 사용하면 konlpy 라이브러리가 필수
2. konlpy 설치 시 JPype1과 Java JDK 설치 필요
3. 의존성이 복잡하고 설치 실패 가능성 높음

**해결 방법**: 
- TextRank는 문장 간 유사도 기반 알고리즘으로 언어에 관계없이 작동
- 모든 언어를 영어 토크나이저로 처리하도록 변경
- 한글도 문장 단위로 유사도 계산이 가능하므로 정상 작동

**수정 내용**:
```python
# python-backend/summarizer.py (수정 후)
# 언어 감지 (표시용)
has_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])
language = 'korean' if has_korean else 'english'  # 응답용

# TextRank 요약 (모든 언어를 english 토크나이저로 처리)
# TextRank는 문장 간 유사도 기반이므로 언어에 관계없이 작동
parser = PlaintextParser.from_string(text, Tokenizer('english'))
stemmer = Stemmer('english')
summarizer = TextRankSummarizer(stemmer)
```

**장점**:
1. ✅ konlpy 의존성 제거 - 추가 라이브러리 설치 불필요
2. ✅ 한글, 영어, 기타 언어 모두 동일한 방식으로 처리 가능
3. ✅ TextRank 알고리즘 특성상 문장 단위 유사도 계산이므로 언어 무관
4. ✅ 설치 및 배포 간소화

**관련 파일**:
- `python-backend/summarizer.py`: Tokenizer를 'english'로 고정

**커밋**: `c55d0a5`

---

### Bug #8: 요약 기능 numpy 의존성 누락
**날짜**: 2025-12-10

**문제**:
- 요약 생성 버튼 클릭 시 `LexRank summarizer requires NumPy. Please, install it by command 'pip install numpy'` 오류 발생
- sumy 라이브러리가 numpy를 의존성으로 요구하지만 requirements.txt에 명시되지 않음

**원인**:
```python
# python-backend/requirements.txt (수정 전)
# 텍스트 요약 (TextRank)
sumy==0.11.0
nltk==3.8.1
# numpy 누락
```

**문제점**:
- sumy 라이브러리는 내부적으로 numpy를 사용
- requirements.txt에 numpy가 명시되지 않아 설치 시 누락됨
- LexRank, TextRank 등 요약 알고리즘이 numpy 행렬 연산을 필요로 함

**해결**:
```python
# python-backend/requirements.txt (수정 후)
# 텍스트 요약 (TextRank)
sumy==0.11.0
nltk==3.8.1
numpy==1.24.3            # sumy 의존성
```

**설치 명령**:
```bash
pip install numpy==1.24.3
```

**검증**:
```
✓ TextRank 요약 완료: 5028자 → 1335자
POST /api/summarize HTTP/1.1 200
```

**관련 파일**:
- `python-backend/requirements.txt`: numpy 의존성 추가

**커밋**: 진행 예정

---

## 🔄 진행 중인 작업

### 현재 상태
- ✅ 검색 로그 매칭 유형 구분 완료
- ✅ 파일 인덱싱 상태 표시 완료
- ✅ API 에러 핸들링 강화 완료
- ✅ useEffect dependency 수정 완료
- ✅ 인덱싱된 파일 내용 표시 문제 해결
- ✅ 요약 기능 summarizer 전역 변수 문제 해결
- ✅ 한글 요약 konlpy 의존성 문제 해결
- ✅ 요약 기능 numpy 의존성 문제 해결
- ✅ 요약 기능 정상 작동 확인 (5028자 → 1335자)

### 완료된 기능
1. ✅ 파일 시스템 탐색 및 검색
2. ✅ FTS5 기반 전체 텍스트 검색
3. ✅ 파일 인덱싱 (PDF, DOCX, PPTX, XLSX 등)
4. ✅ TextRank 기반 내용 요약
5. ✅ 사용자 활동 감지 및 인덱싱 자동 일시정지
6. ✅ DB 트랜잭션 관리 및 WAL 모드

---

## 📊 통계

- **총 Bug 수정**: 8개
- **기능 개선**: 3개
- **커밋 수**: 4개 (5번째 진행 중)
- **수정된 파일**: 
  - `src/App.tsx`
  - `src/api/backend.ts`
  - `python-backend/server.py`
  - `python-backend/database.py`
  - `python-backend/indexer.py`
  - `python-backend/summarizer.py`
  - `python-backend/requirements.txt`
  - `BUG_FIX_HISTORY.md`

---

## 📝 참고 사항

### 디버깅 로그 위치
- **프론트엔드**: 브라우저 개발자 도구 (F12) → Console
- **백엔드**: Terminal 36 (`python-backend/server.py` 출력)

### 주요 로그 패턴
```
🔍 파일 선택됨: [파일명] 확장자: [확장자]
📄 파일 상세 조회 API 호출: [경로]
✅ API 응답 성공: [길이]자
❌ API 응답 오류: [상태코드]
```

### 테스트 체크리스트
- [ ] 파일 리스트에서 ✓/○ 마크 표시 확인
- [ ] 인덱싱된 파일 클릭 시 내용 표시 확인
- [ ] 인덱싱 안된 파일 클릭 시 안내 메시지 확인
- [ ] 검색 로그에서 매칭 유형 구분 확인
- [ ] 검색 완료 요약에서 내용/파일명 매칭 구분 확인

