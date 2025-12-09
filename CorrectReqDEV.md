# Advanced Explorer - 개발자 Troubleshooting 가이드

> Developer Correction Requirements & Debugging Guide

**프로젝트**: Advanced Explorer  
**버전**: 2.0.0  
**최종 수정**: 2025-12-10  
**대상**: Developers, DevOps Engineers

---

## 📋 목차

1. [검색 엔진 오류](#1-검색-엔진-오류)
2. [UI 렌더링 문제](#2-ui-렌더링-문제)
3. [데이터베이스 트랜잭션 오류](#3-데이터베이스-트랜잭션-오류)
4. [파일 시스템 접근 오류](#4-파일-시스템-접근-오류)
5. [Python 의존성 문제](#5-python-의존성-문제)
6. [성능 및 메모리 이슈](#6-성능-및-메모리-이슈)
7. [빌드 및 배포 문제](#7-빌드-및-배포-문제)

---

## 1. 검색 엔진 오류

### Bug #1: 검색 결과 소스 필드 오표시

**증상:**
```
검색 결과가 데이터베이스(내용 매칭)에서 왔는데 
UI에서 "파일명 매칭"으로 잘못 표시됨
```

**재현 방법:**
```bash
# 1. 파일 인덱싱
# 2. 파일 내용으로 검색
# 3. 검색 로그 확인 → 잘못된 레이블 표시
```

**원인 분석:**
```typescript
// src/App.tsx - 기존 코드 (버그)
// 검색 결과의 source 필드를 무시하고 
// 항상 "파일명 매칭"으로 표시

const matchInfo = '파일명 매칭'; // 하드코딩된 값
```

**수정 명령:**
```typescript
// src/App.tsx
// Line: ~470-490 (handleSearch 함수 내)

// BEFORE:
let matchInfo = '';
if (result.source === 'filesystem') {
  matchInfo = '파일명 매칭';
}

// AFTER:
let matchInfo = '';
if (result.source === 'filesystem') {
  matchInfo = '파일명 매칭';
} else if (result.source === 'database') {
  const matchCount = result.match_count || 0;
  matchInfo = matchCount > 0 ? `내용 ${matchCount}개 매칭` : '내용 매칭';
}
```

**테스트 시나리오:**
```bash
# 1. 파일 내용에 "프로젝트"가 있는 파일 준비
# 2. "프로젝트" 검색
# 3. 검색 로그에 "내용 N개 매칭" 표시 확인
```

**관련 파일:**
- `src/App.tsx`
- `src/api/backend.ts`

---

### Bug #2: 특수문자 검색 실패

**증상:**
```
"microsoft & SKP" 검색 시 결과가 0개
파일에 해당 문자열이 존재하는데도 검색되지 않음
```

**재현 방법:**
```bash
# 1. 문서에 "microsoft & SKP" 텍스트 포함
# 2. 인덱싱 완료
# 3. "microsoft & SKP" 검색 → 결과 없음
```

**원인 분석:**
```python
# FTS5는 특수문자(&, @, #, $ 등)를 토큰 구분자로 처리
# "microsoft & SKP"는 "microsoft", "SKP" 두 개의 토큰으로 분리됨
# 정확한 문자열 매칭 불가능
```

**수정 명령:**
```python
# python-backend/database.py
# Line: ~242-285 (search 메서드)

# BEFORE:
def search(self, query: str, limit: int = 100) -> List[dict]:
    fts_query = self._convert_to_fts5_query(query)
    cursor = self.conn.execute("""
        SELECT path, content, mtime, rank
        FROM files_fts
        WHERE files_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (fts_query, limit))
    # ...

# AFTER:
def search(self, query: str, limit: int = 100) -> List[dict]:
    # 따옴표로 감싼 정확한 문장 검색이고 특수문자가 있는 경우 LIKE 검색 사용
    is_exact_phrase = query.startswith('"') and query.endswith('"')
    
    if is_exact_phrase:
        exact_phrase = query[1:-1]
        import re
        has_special_chars = bool(re.search(r'[&@#$%^+=<>~`|\\\/]', exact_phrase))
        
        if has_special_chars:
            # LIKE 검색 사용
            cursor = self.conn.execute("""
                SELECT path, content, mtime, 0 as rank
                FROM files_fts
                WHERE content LIKE ?
                LIMIT ?
            """, (f'%{exact_phrase}%', limit))
            # ...
    
    # 일반 FTS5 검색
    fts_query = self._convert_to_fts5_query(query)
    # ...
```

**테스트 시나리오:**
```python
# test_search_special_chars.py
import pytest
from database import DatabaseManager

def test_search_with_ampersand():
    db = DatabaseManager(':memory:')
    db.insert_file('test.txt', 'microsoft & SKP partnership', 1234567890.0)
    
    # 정확한 문장 검색
    results = db.search('"microsoft & SKP"', 10)
    assert len(results) == 1
    assert 'microsoft & SKP' in results[0]['content']
    
    # AND 검색
    results = db.search('microsoft SKP', 10)
    assert len(results) == 1
```

**관련 파일:**
- `python-backend/database.py`
- `python-backend/search.py`

**SQL 쿼리 비교:**
```sql
-- FTS5 검색 (특수문자 미지원)
SELECT * FROM files_fts WHERE files_fts MATCH 'microsoft AND SKP';

-- LIKE 검색 (특수문자 지원)
SELECT * FROM files_fts WHERE content LIKE '%microsoft & SKP%';
```

---

## 2. UI 렌더링 문제

### Bug #3: 파일 선택 시 내용이 업데이트되지 않음

**증상:**
```
1. 파일 A 선택 → 내용 표시됨
2. 파일 B 선택 → 내용 표시됨
3. 다시 파일 A 선택 → 내용이 업데이트되지 않음 (이전 B 내용 그대로)
```

**재현 방법:**
```bash
# 1. 인덱싱된 파일 2개 준비
# 2. 파일1 클릭 → 내용 확인
# 3. 파일2 클릭 → 내용 확인
# 4. 파일1 다시 클릭 → 버그 발생
```

**원인 분석:**
```typescript
// useEffect의 의존성 배열 문제
// selectedFile 객체 참조가 바뀌지 않으면 useEffect가 실행되지 않음

useEffect(() => {
  loadFileContent();
}, [activeTab.selectedFile]); // ❌ 객체 참조로 비교
```

**수정 명령:**
```typescript
// src/App.tsx
// Line: ~537-600 (파일 내용 로드 useEffect)

// BEFORE:
useEffect(() => {
  const loadFileContent = async () => {
    if (activeTab.selectedFile && activeTab.selectedFile.type !== 'folder') {
      // ...
    }
  };
  loadFileContent();
}, [activeTab.selectedFile]); // ❌ 객체 참조 비교

// AFTER:
useEffect(() => {
  const loadFileContent = async () => {
    if (activeTab.selectedFile && activeTab.selectedFile.type !== 'folder') {
      console.log('🔍 파일 선택됨:', activeTab.selectedFile.name);
      // ...
    }
  };
  loadFileContent();
}, [activeTab.selectedFile?.path]); // ✅ path 값으로 비교
```

**디버깅 로그 추가:**
```typescript
// 파일 선택 시
console.log('🔍 파일 선택됨:', file.name, '경로:', file.path);

// API 호출 시
console.log('📄 문서 파일 선택:', activeTab.selectedFile.path);

// API 응답 시
console.log('📦 API 응답:', detail);
```

**테스트 시나리오:**
```typescript
// React Testing Library
import { render, fireEvent, waitFor } from '@testing-library/react';

test('파일 재선택 시 내용 업데이트', async () => {
  const { getByText } = render(<App />);
  
  // 파일1 선택
  fireEvent.click(getByText('file1.txt'));
  await waitFor(() => expect(screen.getByText(/file1 content/)).toBeInTheDocument());
  
  // 파일2 선택
  fireEvent.click(getByText('file2.txt'));
  await waitFor(() => expect(screen.getByText(/file2 content/)).toBeInTheDocument());
  
  // 파일1 재선택
  fireEvent.click(getByText('file1.txt'));
  await waitFor(() => expect(screen.getByText(/file1 content/)).toBeInTheDocument());
});
```

**관련 파일:**
- `src/App.tsx`

---

### Bug #4: 인덱싱 상태 표시 불일치

**증상:**
```
파일 옆에 ✓ (인덱싱 완료) 표시되지만
파일 클릭 시 "인덱싱 안됨" 메시지 표시
```

**재현 방법:**
```bash
# 1. 폴더 인덱싱
# 2. 파일 목록에서 ✓ 표시 확인
# 3. 해당 파일 클릭
# 4. "인덱싱 안됨" 메시지 확인
```

**원인 분석:**
```typescript
// 1. 인덱싱 상태 체크 API 누락
// 2. FileItem 인터페이스에 indexed 필드 없음
// 3. navigate 함수에서 상태 확인 안 함
```

**수정 명령 1: 백엔드 API 추가**
```python
# python-backend/database.py
# 새 메서드 추가

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
    """여러 파일의 인덱싱 여부를 일괄 확인"""
    result = {}
    for path in file_paths:
        result[path] = self.is_file_indexed(path)
    return result
```

**수정 명령 2: Flask 엔드포인트 추가**
```python
# python-backend/server.py

@app.route('/api/indexing/check-files', methods=['POST'])
def check_files_indexed():
    """여러 파일의 인덱싱 여부를 일괄 확인"""
    try:
        data = request.json
        file_paths = data.get('file_paths', [])
        
        if not file_paths:
            return jsonify({'error': 'file_paths required'}), 400
        
        indexed_status = db_manager.check_files_indexed(file_paths)
        
        return jsonify({
            'indexed_status': indexed_status
        })
    except Exception as e:
        logger.error(f"파일 인덱싱 여부 확인 오류: {e}")
        return jsonify({'error': str(e)}), 500
```

**수정 명령 3: 프론트엔드 API 클라이언트**
```typescript
// src/api/backend.ts

export async function checkFilesIndexed(filePaths: string[]): Promise<Record<string, boolean>> {
  const response = await fetch(`${API_BASE_URL}/indexing/check-files`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_paths: filePaths })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.indexed_status;
}
```

**수정 명령 4: UI 통합**
```typescript
// src/App.tsx - FileItem 인터페이스

// BEFORE:
interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string;
  path?: string;
}

// AFTER:
interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string;
  path?: string;
  indexed?: boolean; // 추가
}

// navigate 함수에 인덱싱 체크 추가
const navigate = async (folderName: string, folderPath: string) => {
  // ... 파일 목록 로드 ...
  
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
  
  // ...
};
```

**테스트 시나리오:**
```bash
# 1. DB 직접 확인
sqlite3 python-backend/file_index.db
SELECT path FROM files_fts WHERE path LIKE '%filename%';

# 2. API 테스트
curl -X POST http://127.0.0.1:5000/api/indexing/check-files \
  -H "Content-Type: application/json" \
  -d '{"file_paths": ["C:\\Users\\test.pdf"]}'

# 3. UI 테스트
# - 파일 목록에서 ✓ 표시 확인
# - 파일 클릭하여 내용 표시 확인
```

**관련 파일:**
- `python-backend/database.py`
- `python-backend/server.py`
- `src/api/backend.ts`
- `src/App.tsx`

---

## 3. 데이터베이스 트랜잭션 오류

### Bug #5: 인덱싱 후 DB에 저장되지 않음

**증상:**
```
파일 인덱싱이 "성공"으로 로그에 표시되지만
나중에 검색하면 해당 파일이 DB에 없음
```

**재현 방법:**
```bash
# 1. 파일 인덱싱 시작
# 2. 인덱싱 로그에서 "성공" 확인
# 3. DB 직접 쿼리
sqlite3 file_index.db "SELECT COUNT(*) FROM files_fts;"
# 4. 예상보다 적은 수 확인
```

**원인 분석:**
```python
# 명시적 COMMIT 누락
# 트랜잭션이 자동 커밋되지 않음
# 프로세스 종료 시 변경사항 손실

def insert_file(self, path: str, content: str, mtime: float):
    self.conn.execute(
        "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
        (path, content, str(mtime))
    )
    # ❌ commit() 누락!
```

**수정 명령:**
```python
# python-backend/database.py
# _initialize_database 메서드

# BEFORE:
def _initialize_database(self):
    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self.conn.row_factory = sqlite3.Row
    # 테이블 생성...

# AFTER:
def _initialize_database(self):
    self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
    self.conn.row_factory = sqlite3.Row
    
    # WAL 모드 활성화 (동시성 향상)
    self.conn.execute("PRAGMA journal_mode=WAL")
    # 동기화 레벨 조정 (성능 향상)
    self.conn.execute("PRAGMA synchronous=NORMAL")
    
    # 테이블 생성...

# insert_file 메서드
# BEFORE:
def insert_file(self, path: str, content: str, mtime: float):
    self.conn.execute(
        "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
        (path, content, str(mtime))
    )

# AFTER:
def insert_file(self, path: str, content: str, mtime: float):
    try:
        self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute(
            "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
            (path, content, str(mtime))
        )
        self.conn.commit()  # ✅ 명시적 커밋
        logger.debug(f"✓ 파일 인덱스 추가 (커밋됨): {path}")
    except sqlite3.Error as e:
        try:
            self.conn.rollback()  # ✅ 오류 시 롤백
        except:
            pass
        logger.error(f"파일 인덱스 추가 오류 [{path}]: {e}")
        raise

# 배치 삽입도 동일하게 처리
def insert_files_batch(self, files: List[Tuple[str, str, float]]):
    try:
        self.conn.execute("BEGIN TRANSACTION")
        for path, content, mtime in files:
            self.conn.execute(
                "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
                (path, content, str(mtime))
            )
        self.conn.commit()
        logger.info(f"✓ 배치 인덱스 추가 완료 (커밋됨): {len(files)}개 파일")
    except sqlite3.Error as e:
        try:
            self.conn.rollback()
        except:
            pass
        logger.error(f"배치 인덱스 추가 오류: {e}")
        raise
```

**PRAGMA 설정 설명:**
```sql
-- WAL (Write-Ahead Logging) 모드
-- 읽기와 쓰기가 서로 블록하지 않음
PRAGMA journal_mode=WAL;

-- 동기화 레벨
-- FULL: 가장 안전, 느림
-- NORMAL: 균형 (권장)
-- OFF: 빠름, 위험
PRAGMA synchronous=NORMAL;

-- 캐시 크기 (성능 향상)
PRAGMA cache_size=-64000;  -- 64MB
```

**테스트 시나리오:**
```python
# test_transaction.py
import sqlite3
import pytest
from database import DatabaseManager

def test_commit_after_insert():
    db = DatabaseManager(':memory:')
    
    # 삽입
    db.insert_file('/test/file.txt', 'content', 1234567890.0)
    
    # 새 연결로 확인 (커밋 검증)
    new_conn = sqlite3.connect(':memory:')
    cursor = new_conn.execute("SELECT COUNT(*) FROM files_fts")
    count = cursor.fetchone()[0]
    
    assert count == 1, "커밋이 제대로 되지 않음"

def test_rollback_on_error():
    db = DatabaseManager(':memory:')
    
    # 정상 삽입
    db.insert_file('/test/file1.txt', 'content1', 1234567890.0)
    
    # 오류 발생 (중복 키 등)
    with pytest.raises(sqlite3.Error):
        db.conn.execute(
            "INSERT INTO files_fts VALUES (?, ?, ?)",
            (None, None, None)  # 유효하지 않은 데이터
        )
    
    # 첫 번째 삽입은 유지되어야 함
    cursor = db.conn.execute("SELECT COUNT(*) FROM files_fts")
    count = cursor.fetchone()[0]
    assert count == 1
```

**관련 파일:**
- `python-backend/database.py`

---

## 4. 파일 시스템 접근 오류

### Bug #6: 접근 권한 없는 파일/폴더 표시

**증상:**
```
시스템 폴더(C:\Windows\System32 등) 탐색 시
접근 권한이 없는 파일도 목록에 표시됨
클릭하면 EACCES 오류 발생
```

**재현 방법:**
```bash
# 1. C:\Windows\System32 폴더로 이동
# 2. 모든 파일이 목록에 표시됨
# 3. 시스템 파일 클릭 → 오류
```

**원인 분석:**
```javascript
// electron/main.cjs
// fs.readdir()는 권한 체크 없이 파일 목록만 반환
// 실제 접근 시에만 EACCES 오류 발생

ipcMain.handle('read-directory', async (event, dirPath) => {
  const fs = require('fs').promises;
  const files = await fs.readdir(dirPath, { withFileTypes: true });
  // ❌ 권한 체크 없음
  return files.map(file => ({
    name: file.name,
    isDirectory: file.isDirectory(),
    path: path.join(dirPath, file.name)
  }));
});
```

**수정 명령:**
```javascript
// electron/main.cjs

// BEFORE:
ipcMain.handle('read-directory', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    return files.map(file => ({
      name: file.name,
      isDirectory: file.isDirectory(),
      path: path.join(dirPath, file.name)
    }));
  } catch (error) {
    console.error('Error reading directory:', error);
    return [];
  }
});

// AFTER:
ipcMain.handle('read-directory', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    
    // 접근 권한 체크
    const accessibleFiles = [];
    for (const file of files) {
      const fullPath = path.join(dirPath, file.name);
      try {
        // 읽기 권한 확인
        await fs.access(fullPath, fs.constants.R_OK);
        accessibleFiles.push({
          name: file.name,
          isDirectory: file.isDirectory(),
          path: fullPath
        });
      } catch (accessError) {
        // 접근 권한이 없으면 목록에 포함하지 않음
        console.debug(`Access denied: ${fullPath}`);
      }
    }
    
    return accessibleFiles;
  } catch (error) {
    console.error('Error reading directory:', error);
    return [];
  }
});

// read-directories-only도 동일하게 수정
ipcMain.handle('read-directories-only', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    const directories = files.filter(file => file.isDirectory());
    
    const accessibleDirs = [];
    for (const dir of directories) {
      const fullPath = path.join(dirPath, dir.name);
      try {
        await fs.access(fullPath, fs.constants.R_OK);
        accessibleDirs.push({
          name: dir.name,
          path: fullPath
        });
      } catch (accessError) {
        console.debug(`Access denied: ${fullPath}`);
      }
    }
    
    return accessibleDirs;
  } catch (error) {
    console.error('Error reading directories:', error);
    return [];
  }
});

// get-file-stats도 권한 체크 추가
ipcMain.handle('get-file-stats', async (event, filePath) => {
  const fs = require('fs').promises;
  try {
    // 먼저 접근 권한 확인
    await fs.access(filePath, fs.constants.R_OK);
    
    const stats = await fs.stat(filePath);
    return {
      size: stats.size,
      modified: stats.mtime,
      created: stats.birthtime,
      isDirectory: stats.isDirectory()
    };
  } catch (error) {
    if (error.code === 'EACCES' || error.code === 'EPERM') {
      console.debug(`Access denied: ${filePath}`);
    } else {
      console.error('Error getting file stats:', error);
    }
    return null;
  }
});
```

**권한 상수 설명:**
```javascript
// Node.js fs.constants
fs.constants.R_OK  // 읽기 권한
fs.constants.W_OK  // 쓰기 권한
fs.constants.X_OK  // 실행 권한
fs.constants.F_OK  // 파일 존재 여부
```

**테스트 시나리오:**
```javascript
// test/electron-ipc.test.js
const { app } = require('electron');
const fs = require('fs').promises;

describe('File Access Control', () => {
  test('접근 권한 없는 파일 필터링', async () => {
    const systemPath = 'C:\\Windows\\System32';
    const files = await electronAPI.readDirectory(systemPath);
    
    // 모든 반환된 파일은 읽기 가능해야 함
    for (const file of files) {
      await expect(fs.access(file.path, fs.constants.R_OK))
        .resolves.not.toThrow();
    }
  });
  
  test('EACCES 오류 처리', async () => {
    const restrictedPath = 'C:\\Windows\\System32\\config\\SAM';
    const stats = await electronAPI.getFileStats(restrictedPath);
    
    // 권한 없으면 null 반환
    expect(stats).toBeNull();
  });
});
```

**관련 파일:**
- `electron/main.cjs`

---

## 5. Python 의존성 문제

### Bug #7: konlpy 설치 실패 (한글 처리)

**증상:**
```
요약 기능 사용 시 오류:
"Korean tokenizer requires konlpy. Please, install it by command 'pip install konlpy'"

konlpy 설치 시 Java JDK 필요
설치 과정이 복잡하여 사용자 경험 저하
```

**재현 방법:**
```bash
# 1. Python 요약 엔진 초기화
# 2. 한글 문서 요약 시도
# 3. konlpy 오류 발생
```

**원인 분석:**
```python
# python-backend/summarizer.py
# 언어 자동 감지 후 토크나이저 선택

has_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])
language = 'korean' if has_korean else 'english'

# 한글인 경우 konlpy 토크나이저 사용 시도
parser = PlaintextParser.from_string(text, Tokenizer(language))  # ❌
stemmer = Stemmer(language)  # ❌

# konlpy가 없으면 오류 발생
# Java JDK도 필요
```

**수정 명령:**
```python
# python-backend/summarizer.py

# BEFORE:
def summarize(self, text: str, sentences_count: int = 5) -> Dict:
    # 언어 감지
    has_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])
    language = 'korean' if has_korean else 'english'
    
    # 토크나이저 생성 (konlpy 필요)
    parser = PlaintextParser.from_string(text, Tokenizer(language))
    stemmer = Stemmer(language)
    
    # ...

# AFTER:
def summarize(self, text: str, sentences_count: int = 5) -> Dict:
    # 언어 감지 (표시용)
    has_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])
    language = 'korean' if has_korean else 'english'
    
    # TextRank 요약 (모든 언어를 english 토크나이저로 처리)
    # TextRank는 문장 간 유사도 기반이므로 언어에 관계없이 작동
    parser = PlaintextParser.from_string(text, Tokenizer('english'))
    stemmer = Stemmer('english')
    
    summarizer = TextRankSummarizer(stemmer)
    summary_sentences = summarizer(parser.document, sentences_count)
    
    # 문단별 줄바꿈 추가
    summary = '\n\n'.join([str(sentence) for sentence in summary_sentences])
    
    # ...
```

**장점:**
```
✅ konlpy 의존성 제거 (Java JDK 불필요)
✅ 설치 과정 간소화
✅ 한글, 영어, 기타 언어 동일한 방식으로 처리
✅ TextRank는 문장 유사도 기반이므로 언어 무관
```

**테스트 시나리오:**
```python
# test_summarizer.py
from summarizer import ContentSummarizer

def test_korean_text_summary():
    summarizer = ContentSummarizer()
    
    korean_text = """
    인공지능은 현대 기술의 핵심입니다.
    많은 기업들이 AI를 활용하고 있습니다.
    자연어 처리 기술이 발전하고 있습니다.
    """
    
    result = summarizer.summarize(korean_text, 2)
    
    assert result['success'] is True
    assert result['language'] == 'korean'
    assert len(result['summary']) > 0
    
def test_english_text_summary():
    summarizer = ContentSummarizer()
    
    english_text = """
    Artificial intelligence is the future.
    Many companies are adopting AI.
    Natural language processing is advancing.
    """
    
    result = summarizer.summarize(english_text, 2)
    
    assert result['success'] is True
    assert result['language'] == 'english'
```

**관련 파일:**
- `python-backend/summarizer.py`
- `python-backend/requirements.txt`

---

### Bug #8: numpy 의존성 누락

**증상:**
```
요약 기능 사용 시 오류:
"LexRank summarizer requires NumPy. Please, install it by command 'pip install numpy'"
```

**원인 분석:**
```python
# sumy 라이브러리가 numpy를 필요로 함
# requirements.txt에 명시되지 않음
```

**수정 명령:**
```python
# python-backend/requirements.txt

# BEFORE:
sumy==0.11.0
nltk==3.8.1

# AFTER:
sumy==0.11.0
nltk==3.8.1
numpy==1.24.3  # sumy 의존성
```

**설치:**
```bash
pip install numpy==1.24.3
```

**관련 파일:**
- `python-backend/requirements.txt`

---

## 6. 성능 및 메모리 이슈

### Issue #1: 대용량 폴더 인덱싱 시 메모리 부족

**증상:**
```
수천 개의 파일이 있는 폴더 인덱싱 시
Python 프로세스 메모리 사용량 급증
Out of Memory 오류 발생 가능
```

**원인 분석:**
```python
# 모든 파일을 메모리에 올린 후 배치 삽입
files_batch = []
for file in all_files:  # 수천 개
    content = parse_file(file)  # 각 파일 수MB
    files_batch.append((file, content, mtime))

# 메모리에 전체 파일 내용이 축적됨
db.insert_files_batch(files_batch)
```

**해결 방안:**
```python
# python-backend/indexer.py

# 작은 배치 크기 사용
BATCH_SIZE = 2  # 또는 5, 10

files_batch = []
for file_path in files_to_process:
    try:
        content = self._parse_file(file_path)
        mtime = os.path.getmtime(file_path)
        
        files_batch.append((file_path, content, mtime))
        
        # 배치가 찼으면 즉시 저장하고 메모리 해제
        if len(files_batch) >= BATCH_SIZE:
            self.db.insert_files_batch(files_batch)
            files_batch = []  # 메모리 해제
            
    except Exception as e:
        logger.error(f"파일 처리 오류: {e}")

# 남은 파일 처리
if files_batch:
    self.db.insert_files_batch(files_batch)
```

**모니터링:**
```python
import psutil
import os

def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024  # MB

# 주기적으로 로그
logger.info(f"메모리 사용량: {get_memory_usage():.2f} MB")
```

---

### Issue #2: FTS5 인덱스 조각화

**증상:**
```
장기간 사용 후 검색 속도 저하
DB 파일 크기 비정상적으로 증가
```

**해결 방안:**
```python
# python-backend/database.py

def optimize(self):
    """FTS5 인덱스 최적화"""
    try:
        self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("INSERT INTO files_fts(files_fts) VALUES('optimize')")
        self.conn.commit()
        logger.info("✓ FTS5 인덱스 최적화 완료")
    except sqlite3.Error as e:
        self.conn.rollback()
        logger.error(f"인덱스 최적화 오류: {e}")

def vacuum(self):
    """데이터베이스 VACUUM (조각화 제거)"""
    try:
        # VACUUM은 트랜잭션 밖에서 실행
        self.conn.execute("VACUUM")
        logger.info("✓ 데이터베이스 VACUUM 완료")
    except sqlite3.Error as e:
        logger.error(f"VACUUM 오류: {e}")

# 주기적으로 실행 (예: 1000개 파일 삭제 후)
if deleted_files_count % 1000 == 0:
    db.optimize()
    db.vacuum()
```

---

## 7. 빌드 및 배포 문제

### Issue #1: Python 번들링

**문제:**
```
Electron 앱 빌드 시 Python 런타임 포함 필요
PyInstaller 사용 시 크기 증가
```

**해결 방안:**
```bash
# PyInstaller로 단일 실행 파일 생성
pyinstaller --onefile \
  --add-data "database.py:." \
  --add-data "indexer.py:." \
  --add-data "search.py:." \
  --add-data "summarizer.py:." \
  python-backend/server.py

# electron-builder config
{
  "extraResources": [
    {
      "from": "python-backend/dist/server.exe",
      "to": "python/server.exe"
    }
  ]
}
```

---

## 8. 디버깅 체크리스트

### 검색 문제 디버깅
```bash
# 1. DB 직접 확인
sqlite3 python-backend/file_index.db
SELECT COUNT(*) FROM files_fts;
SELECT * FROM files_fts WHERE path LIKE '%파일명%';

# 2. FTS5 쿼리 테스트
SELECT * FROM files_fts WHERE files_fts MATCH '검색어';

# 3. LIKE 검색 테스트
SELECT * FROM files_fts WHERE content LIKE '%특수문자 포함%';
```

### API 디버깅
```bash
# Flask 서버 로그 확인
cat python-backend/logs/server.log | grep ERROR

# API 직접 호출
curl http://127.0.0.1:5000/api/statistics
curl -X POST http://127.0.0.1:5000/api/search/combined \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### 프론트엔드 디버깅
```typescript
// React DevTools
// Chrome DevTools → React 탭

// Network 탭에서 API 호출 확인
// Console에서 로그 확인
console.log('🔍 상태:', state);
console.error('❌ 오류:', error);
```

---

## 9. 성능 벤치마크

### 인덱싱 성능
```python
# 목표: 파일당 평균 500ms 이내
# 측정 방법:
import time

start = time.time()
indexer.process_file(file_path)
elapsed = time.time() - start

logger.info(f"처리 시간: {elapsed:.3f}초 - {file_path}")
```

### 검색 성능
```python
# 목표: 100ms 이내
# 측정 방법:
start = time.time()
results = search_engine.search_combined(query, path)
elapsed = time.time() - start

logger.info(f"검색 시간: {elapsed:.3f}초 - {len(results)}개 결과")
```

---

**문서 버전**: 2.0.0  
**최종 검토**: 2025-12-10  
**다음 업데이트**: 새 버그 발견 시

**기여자**: Development Team  
**문의**: dev@advanced-explorer.com

