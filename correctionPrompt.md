# Advanced Explorer Troubleshooting & 수정 명령어

## 📋 목차
1. [검색 기능 오류](#1-검색-기능-오류)
2. [인덱싱 관련 오류](#2-인덱싱-관련-오류)
3. [데이터베이스 오류](#3-데이터베이스-오류)
4. [요약 기능 오류](#4-요약-기능-오류)
5. [UI/UX 개선](#5-uiux-개선)
6. [프로세스 관리](#6-프로세스-관리)

---

## 1. 검색 기능 오류

### Bug #1: 검색 로그에서 매칭 유형 오표시

**문제 상황**:
```
검색 결과가 "내용 매칭"인데 로그에는 "파일명 매칭"으로 잘못 표시됨
검색 완료 요약에서 내용 매칭과 파일명 매칭이 구분되지 않음
```

**사용자 명령**:
```
검색 로그에 파일명 매칭으로 "미흡함"이 나오는데 파일명에는 그런거 없음. 
검토해서 오류 수정해줘
```

**원인 파악 명령**:
```
src/App.tsx의 검색 결과 처리 로직을 확인해줘.
백엔드에서 보내는 source 필드를 제대로 활용하고 있는지 체크해줘.
```

**해결 명령**:
```
src/App.tsx에서 검색 로그 표시 로직을 다음과 같이 수정해줘:

백엔드의 source 필드를 사용하여:
- source === 'filesystem': '파일명 매칭'
- source === 'database': '내용 N개 매칭'

검색 완료 요약도 개선:
- 내용 매칭과 파일명 매칭을 별도로 집계
- 각각의 수를 따로 표시
```

**수정 코드**:
```typescript
// src/App.tsx (수정 후)
let matchInfo = '';
if (result.source === 'filesystem') {
  matchInfo = '파일명 매칭';
} else if (result.source === 'database') {
  const matchCount = result.match_count || 0;
  matchInfo = matchCount > 0 ? `내용 ${matchCount}개 매칭` : '내용 매칭';
}

// 요약 개선
const contentMatchCount = searchResults.filter(r => r.source === 'database').length;
const filenameMatchCount = searchResults.filter(r => r.source === 'filesystem').length;

if (contentMatchCount > 0) {
  addSearchLog(`   내용 매칭: 총 ${contentMatchCount}개 발견`);
}
if (filenameMatchCount > 0) {
  addSearchLog(`   파일명 매칭: 총 ${filenameMatchCount}개 발견`);
}
```

---

### Bug #2: 인덱싱된 파일 내용이 표시되지 않음

**문제 상황**:
```
파일 리스트에는 인덱싱 완료(✓)로 표시
파일 클릭 시 "인덱싱 미완료" 메시지 표시
백엔드는 정상적으로 200 응답 반환
```

**사용자 명령**:
```
첨부 스샷처럼 인덱싱 완료 됐다고 하는데 내용 보기 및 편집에는 
인덱싱 안됐다고 나와, 검토하고 수정해줘
```

**원인 파악 명령**:
```
src/App.tsx의 파일 선택 로직을 확인해줘.
useEffect의 의존성 배열을 체크해줘.
activeTab.selectedFile이 객체 참조로 비교되고 있는지 확인해줘.
```

**해결 명령**:
```
1. useEffect dependency를 수정해줘:
   [activeTab.selectedFile] → [activeTab.selectedFile?.path]
   
2. src/api/backend.ts에 에러 핸들링 강화:
   - response.ok 체크
   - 상태 코드 확인
   - 디버깅 로그 추가

3. API 호출 디버깅 로그 추가:
   - 파일 선택 시 로그
   - API 호출 시 로그
   - 응답 성공/실패 로그
```

**수정 코드**:
```typescript
// src/App.tsx (useEffect 수정)
useEffect(() => {
  loadFileContent();
}, [activeTab.selectedFile?.path]); // path를 직접 체크

// src/api/backend.ts (에러 핸들링)
export async function getIndexedFileDetail(filePath: string) {
  console.log('📄 파일 상세 조회 API 호출:', filePath);
  const encodedPath = encodeURIComponent(filePath);
  const response = await fetch(`${API_BASE_URL}/indexing/database/${encodedPath}`);
  
  if (!response.ok) {
    console.error(`❌ API 응답 오류: ${response.status}`);
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  const data = await response.json();
  console.log('✅ API 응답 성공:', data?.content?.length || 0, '자');
  return data;
}
```

---

## 2. 인덱싱 관련 오류

### Bug #5: 인덱싱 로그에 DB 저장 상태 미표시

**문제 상황**:
```
인덱싱 로그에서 DB 저장 여부를 확인할 수 없음
토큰 수가 표시되지 않음
DB 저장 완료 로그가 나타나지 않음
```

**사용자 명령**:
```
indexing log에 DB 저장여부 및 저장되는 Token수 표시 해줘
정말 indexing log 창에 DB 저장 완료 로그는 안나와.. 다시 좀 봐줘
```

**원인 파악 명령**:
```
python-backend/indexer.py의 _log_success 메서드를 확인해줘.
db_saved 파라미터가 제대로 전달되고 있는지 체크해줘.
log_callback이 올바르게 호출되는지 확인해줘.
```

**해결 명령**:
```
python-backend/indexer.py의 _log_success 메서드를 다음과 같이 수정해줘:

1. DB 저장 상태를 명확하게 표시:
   - db_saved=True: "✓ DB완료"
   - db_saved=False: "⊗ DB대기"

2. 토큰 수를 명확하게 표시:
   - "토큰:N개" 형식으로 표시

3. 상세 정보 포맷:
   - "문자수 / 토큰:N개 | DB상태" 형식
```

**수정 코드**:
```python
# python-backend/indexer.py
def _log_success(self, path: str, char_count: int, token_count: int = 0, 
                 db_saved: bool = True, content: str = None):
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
    
    # UI 콜백
    if self.log_callback:
        self.log_callback('처리중', filename, detail)
```

---

### Feature #3: 이전 처리 완료 파일 구분 표시

**문제 상황**:
```
이미 인덱싱되어 변경 없는 파일이 "처리중"으로 표시됨
이전에 처리된 파일과 새로 처리하는 파일을 구분할 수 없음
```

**사용자 명령**:
```
이전에 처리 됐고 변경 없는 파일은 "처리중" 이 아니라, 
이전 처리 완료 라고 표시해줘
```

**해결 명령**:
```
python-backend/indexer.py에서 mtime 비교 로직을 수정해줘:

1. 파일이 이미 인덱싱되고 변경되지 않은 경우:
   - 로그 상태: "이전완료"
   - 상세 정보: "이전 처리 완료 (변경 없음)"

2. _add_log_to_memory에 새 로그 추가

3. log_callback 호출하여 UI에 표시
```

**수정 코드**:
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

---

## 3. 데이터베이스 오류

### Bug #3: DB Commit 불안정

**문제 상황**:
```
인덱싱 중 DB에 저장되지 않는 경우 발생
트랜잭션 관리 부족
commit이 누락되어 데이터가 유실됨
```

**사용자 명령**:
```
DB Commit은 안되는거 같은데.. 점검해줘
파일 2개 마다 DB에 insert해주고 Commit해
```

**원인 파악 명령**:
```
python-backend/database.py의 insert 메서드들을 확인해줘.
commit()이 호출되는지 체크해줘.
트랜잭션이 명시적으로 관리되는지 확인해줘.
```

**해결 명령**:
```
1. python-backend/database.py를 다음과 같이 수정해줘:
   - WAL 모드 활성화
   - PRAGMA synchronous=NORMAL 설정
   - 명시적 트랜잭션 사용 (BEGIN, COMMIT, ROLLBACK)
   
2. 모든 insert, update, delete 메서드에 트랜잭션 추가

3. python-backend/indexer.py에서:
   - 배치 크기를 2로 설정
   - insert_files_batch 사용
```

**수정 코드**:
```python
# python-backend/database.py
def _initialize_database(self):
    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self.conn.row_factory = sqlite3.Row
    # WAL 모드 활성화
    self.conn.execute("PRAGMA journal_mode=WAL")
    self.conn.execute("PRAGMA synchronous=NORMAL")
    # ... 테이블 생성 ...

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
```

---

### Bug #4: 파일 상세 조회 시 경로 불일치

**문제 상황**:
```
URL 인코딩된 경로와 DB 저장 경로 불일치
한글 경로 처리 문제
파일을 찾을 수 없다는 오류
```

**원인 파악 명령**:
```
python-backend/server.py의 get_indexed_file_detail 함수를 확인해줘.
URL 디코딩이 제대로 되는지 체크해줘.
경로 비교 로직을 확인해줘.
```

**해결 명령**:
```
python-backend/server.py의 get_indexed_file_detail을 다음과 같이 수정해줘:

1. URL 디코딩 명시적 처리:
   from urllib.parse import unquote
   decoded_path = unquote(file_path)

2. 디버깅 로그 추가:
   - 요청 경로 로그
   - DB 조회 결과 로그
   - 유사 경로 검색 (파일 없을 시)

3. python-backend/database.py에도 디버깅 로그 추가
```

**수정 코드**:
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

---

## 4. 요약 기능 오류

### Bug #6: 요약 기능 summarizer 전역 변수 문제

**문제 상황**:
```
요약 생성 버튼 클릭 시 "요약 실패" 메시지
백엔드 로그: "name 'summarizer' is not defined"
summarizer가 전역 변수로 선언되지 않음
```

**사용자 명령**:
```
내용 보기 및 편집에서 요약 버튼 누르면 요약 실패 나와, 
로직 체크하고 오류 수정해줘
```

**원인 파악 명령**:
```
python-backend/server.py를 확인해줘.
summarizer가 전역 변수로 선언되어 있는지 체크해줘.
initialize() 함수의 global 선언을 확인해줘.
```

**해결 명령**:
```
python-backend/server.py를 다음과 같이 수정해줘:

1. 전역 변수 선언 추가:
   summarizer: ContentSummarizer = None

2. initialize() 함수의 global 선언 수정:
   global db_manager, indexer, search_engine, summarizer

3. summarizer 초기화:
   summarizer = ContentSummarizer()
```

**수정 코드**:
```python
# python-backend/server.py (수정 후)

# 전역 객체
db_manager: DatabaseManager = None
indexer: FileIndexer = None
search_engine: SearchEngine = None
summarizer: ContentSummarizer = None  # 추가

def initialize():
    """백엔드 초기화 (설정 파일 기반)"""
    global db_manager, indexer, search_engine, summarizer  # summarizer 추가
    
    # ... (기존 코드)
    
    # 요약 엔진 초기화
    summarizer = ContentSummarizer()  # 전역 변수에 할당
    logger.info("요약 엔진 초기화 완료")
```

---

### Bug #7: 한글 요약 기능 konlpy 의존성 문제

**문제 상황**:
```
요약 생성 버튼 클릭 시 오류
"Korean tokenizer requires konlpy. Please, install it by command 'pip install konlpy'"
konlpy는 Java JDK가 필요하고 설치가 복잡함
```

**사용자 명령**:
```
요약 생성하니 첨부처럼 오류나, 한글 및 다른 언어 처리가 안되는 거 같아
```

**원인 파악 명령**:
```
python-backend/summarizer.py를 확인해줘.
Tokenizer(language)가 'korean'을 사용하는지 체크해줘.
konlpy 의존성이 필요한지 확인해줘.
```

**해결 명령**:
```
python-backend/summarizer.py를 다음과 같이 수정해줘:

1. 모든 언어를 english 토크나이저로 처리:
   parser = PlaintextParser.from_string(text, Tokenizer('english'))
   stemmer = Stemmer('english')

2. language 변수는 응답용으로만 사용

이유: TextRank는 문장 간 유사도 기반이므로 언어에 관계없이 작동
```

**수정 코드**:
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
- ✅ konlpy 의존성 제거 (Java JDK 불필요)
- ✅ 한글, 영어, 기타 언어 모두 동일한 방식으로 처리
- ✅ 설치 및 배포 간소화

---

### Bug #8: 요약 기능 numpy 의존성 누락

**문제 상황**:
```
요약 생성 버튼 클릭 시 오류
"LexRank summarizer requires NumPy. Please, install it by command 'pip install numpy'"
sumy가 numpy를 필요로 하지만 requirements.txt에 없음
```

**사용자 명령**:
```
이 오류나 프로그램 설치해줘
```

**해결 명령**:
```
1. python-backend/requirements.txt에 numpy 추가:
   numpy==1.24.3

2. numpy 설치:
   pip install numpy==1.24.3

3. Python 백엔드 재시작
```

**수정 코드**:
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

---

## 5. UI/UX 개선

### Feature #1: 파일 리스트에 인덱싱 상태 표시

**사용자 명령**:
```
그래 파일리스트에 인덱싱 여부 마킹하는 것도 좋네. 그렇게 해줘
```

**구현 명령**:
```
1. src/App.tsx의 FileItem 인터페이스에 indexed 필드 추가:
   indexed?: boolean;

2. python-backend/database.py에 메서드 추가:
   - is_file_indexed(path: str) -> bool
   - check_files_indexed(paths: List[str]) -> Dict[str, bool]

3. python-backend/server.py에 API 엔드포인트 추가:
   POST /api/indexing/check-files

4. src/api/backend.ts에 API 클라이언트 추가:
   checkFilesIndexed(paths: string[]): Promise<Record<string, boolean>>

5. src/App.tsx의 navigate 함수에서:
   - 폴더 탐색 시 checkFilesIndexed 호출
   - 각 파일의 indexed 상태 업데이트

6. 파일 리스트에 상태 아이콘 표시:
   - ✓ (녹색): 인덱싱 완료
   - ○ (회색): 인덱싱 안됨
```

**수정 코드**:
```typescript
// src/App.tsx - FileItem 인터페이스
interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string;
  path?: string;
  indexed?: boolean; // 추가
}

// 파일 리스트 렌더링
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
```

```python
# python-backend/database.py - 메서드 추가
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

def check_files_indexed(self, file_paths: List[str]) -> Dict[str, bool]:
    """여러 파일의 인덱싱 여부를 확인"""
    result = {}
    for path in file_paths:
        result[path] = self.is_file_indexed(path)
    return result
```

---

### Feature #2: 요약 결과 문단별 줄바꿈

**사용자 명령**:
```
요약 생성시 문단별 Line Break 넣어줘
```

**해결 명령**:
```
1. python-backend/summarizer.py에서:
   - 요약 문장 사이에 빈 줄 추가
   - '\n'.join() → '\n\n'.join()

2. src/App.tsx에서:
   - 요약 결과 표시 줄 간격 개선
   - line-height: 1.8 추가
```

**수정 코드**:
```python
# python-backend/summarizer.py
# 요약 문장 추출 (문단별 구분을 위해 빈 줄 추가)
summary_sentences = summarizer(parser.document, sentences_count)
summary = '\n\n'.join([str(sentence) for sentence in summary_sentences])
```

```typescript
// src/App.tsx
<pre 
  className="text-xs text-green-200 whitespace-pre-wrap font-mono leading-relaxed" 
  style={{ lineHeight: '1.8' }}
>
  {fileSummary}
</pre>
```

---

### Feature #3: 초기 디렉토리를 문서 폴더로 설정

**사용자 명령**:
```
초기 디렉토리는 즐겨찾기의 문서로 셋팅 해줘
```

**해결 명령**:
```
src/App.tsx에 다음 useEffect를 추가해줘:

컴포넌트 마운트 시 한 번만 실행되는 useEffect로:
1. documentsPath 계산
2. navigate('문서', documentsPath) 호출
3. 빈 의존성 배열 사용
```

**수정 코드**:
```typescript
// src/App.tsx - 초기 디렉토리 설정
useEffect(() => {
  const documentsPath = `${userHome}\\Documents`;
  // 초기 로드 시 문서 폴더로 이동
  navigate('문서', documentsPath);
}, []); // 빈 의존성 배열로 컴포넌트 마운트 시 한 번만 실행
```

---

## 6. 프로세스 관리

### 프로세스 종료 및 재시작

**사용자 명령**:
```
프로그램 다 죽이고 다시 시작해줘
프로세스 다 종료하고 다시 시작해줘
```

**실행 명령**:
```powershell
# 1단계: 모든 프로세스 종료
Get-Process python,node,electron -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2단계: Python 백엔드 시작 (백그라운드)
cd "C:\Users\dylee\Desktop\Advanced Explorer\python-backend"
python server.py

# 3단계: Vite 개발 서버 시작 (백그라운드, 새 터미널)
cd "C:\Users\dylee\Desktop\Advanced Explorer"
npm run dev

# 4단계: Electron 앱 시작 (백그라운드, 새 터미널)
Start-Sleep -Seconds 5
cd "C:\Users\dylee\Desktop\Advanced Explorer"
npm run electron
```

---

### 백엔드만 재시작

**사용자 명령**:
```
백엔드만 재시작해줘
Python 서버만 다시 시작해줘
```

**실행 명령**:
```powershell
# Python 프로세스 종료
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Python 백엔드 재시작
cd "C:\Users\dylee\Desktop\Advanced Explorer\python-backend"
python server.py
```

---

### 코드 변경 후 재시작 순서

**패턴**:
```
1. 파일 수정 완료
2. 프로세스 종료
3. 백엔드 시작
4. 프론트엔드 시작
5. Electron 시작
6. 상태 확인
```

**명령어 시퀀스**:
```powershell
# 종료
Get-Process python,node,electron -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 백엔드 (Terminal 1)
cd "python-backend"; python server.py &

# 프론트엔드 (Terminal 2)
npm run dev &

# Electron (Terminal 3)
Start-Sleep -Seconds 5; npm run electron &

# 확인
Start-Sleep -Seconds 8
Write-Host "✅ 재시작 완료"
```

---

## 7. Git 작업

### Commit & Push

**사용자 명령**:
```
현재까지 Commit 및 GitHub에 Push
Commit하고 Push해줘
수정 완료되면 Commit & github push 해줘
```

**실행 명령**:
```bash
# 1단계: 상태 확인
git status

# 2단계: 변경 파일 추가
git add [파일명]

# 3단계: 커밋
git commit -m "커밋 메시지"

# 4단계: Push
git push origin main
```

**커밋 메시지 템플릿**:
```
[타입]: [간단한 설명]

- [상세 변경사항 1]
- [상세 변경사항 2]
- [상세 변경사항 3]

[Bug/Feature] #[번호]: [문제/기능 설명]
- [해결 방법/구현 내용]

[수정 파일]:
- [파일1]: [변경 내용]
- [파일2]: [변경 내용]
```

**커밋 타입**:
- `fix`: 버그 수정
- `feat`: 새로운 기능
- `refactor`: 코드 리팩토링
- `style`: 코드 스타일 변경
- `docs`: 문서 변경
- `chore`: 빌드, 설정 변경

---

## 8. 디버깅 팁

### 백엔드 로그 확인

**명령**:
```
python-backend 터미널의 로그를 확인해줘
Terminal N의 출력을 읽어줘
```

**확인 사항**:
- Flask 서버 시작: "Running on http://127.0.0.1:5000"
- 요약 엔진 초기화: "✓ TextRank 요약 엔진 초기화"
- API 호출 로그: GET/POST 요청 및 응답
- 에러 로그: ERROR 레벨 메시지

---

### 프론트엔드 디버깅

**명령**:
```
브라우저 개발자 도구(F12)를 열고 Console 탭을 확인해줘
Network 탭에서 API 호출을 확인해줘
```

**확인 사항**:
- API 호출 로그: 📄, ✅, ❌ 아이콘
- 네트워크 요청: Status 200, 400, 404, 500
- 에러 메시지: console.error 출력

---

### 데이터베이스 확인

**명령**:
```
python-backend/file_index.db를 확인해줘
DB에 저장된 파일 수를 확인해줘
```

**SQL 쿼리**:
```sql
-- 전체 파일 수
SELECT COUNT(*) FROM files_fts;

-- 특정 파일 확인
SELECT * FROM files_fts WHERE path LIKE '%파일명%';

-- 최근 인덱싱된 파일
SELECT path, mtime FROM files_fts ORDER BY mtime DESC LIMIT 10;
```

---

## 9. 일반적인 해결 패턴

### 패턴 1: "기능이 작동하지 않음"

1. 터미널 로그 확인
2. 브라우저 콘솔 확인
3. 네트워크 탭에서 API 호출 확인
4. 백엔드 재시작
5. 브라우저 새로고침

---

### 패턴 2: "오류 메시지 표시"

1. 오류 메시지 전체 복사
2. 스택 트레이스 확인
3. 해당 파일 및 라인 확인
4. 로직 수정
5. 프로세스 재시작

---

### 패턴 3: "의존성 오류"

1. requirements.txt 확인
2. package.json 확인
3. 누락된 패키지 설치
4. 버전 충돌 확인
5. 캐시 삭제 후 재설치

---

### 패턴 4: "데이터가 표시되지 않음"

1. API 호출 확인
2. 응답 데이터 구조 확인
3. 상태 업데이트 로직 확인
4. useEffect 의존성 확인
5. 디버깅 로그 추가

---

## 📝 요약

### 주요 수정 사항

| Bug # | 문제 | 해결 |
|-------|------|------|
| #1 | 검색 로그 매칭 유형 오표시 | source 필드 활용 |
| #2 | 인덱싱된 파일 내용 미표시 | useEffect dependency 수정 |
| #3 | DB Commit 불안정 | 명시적 트랜잭션, WAL 모드 |
| #4 | 파일 상세 조회 경로 불일치 | URL 디코딩, 디버깅 로그 |
| #5 | 인덱싱 로그 DB 상태 미표시 | 로그 포맷 개선 |
| #6 | summarizer 전역 변수 누락 | 전역 변수 선언 추가 |
| #7 | 한글 요약 konlpy 의존성 | english 토크나이저 사용 |
| #8 | numpy 의존성 누락 | requirements.txt 추가 |

### 주요 기능 추가

| Feature # | 기능 | 구현 |
|-----------|------|------|
| #1 | 파일 인덱싱 상태 표시 | ✓/○ 아이콘 |
| #2 | 인덱싱 안내 메시지 개선 | 구체적 가이드 제공 |
| #3 | 이전 처리 완료 구분 | "이전완료" 상태 추가 |
| #4 | 요약 결과 줄바꿈 | \n\n, line-height: 1.8 |
| #5 | 초기 디렉토리 설정 | 문서 폴더로 시작 |

---

**작성일**: 2025-12-10  
**버전**: 1.0.0  
**프로젝트**: Advanced Explorer

