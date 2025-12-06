/**
 * Python 백엔드 API 클라이언트
 */

const API_BASE_URL = 'http://127.0.0.1:5000/api';

// 타입 정의
export interface IndexingStats {
  total_files: number;
  indexed_files: number;
  skipped_files: number;
  error_files: number;
  start_time: number | null;
  end_time: number | null;
}

export interface RetryWorkerInfo {
  is_running: boolean;
  pending_files: number;
  interval_seconds: number;
}

export interface IndexingStatus {
  is_running: boolean;
  stats: IndexingStats;
  retry_worker?: RetryWorkerInfo;
}

export interface IndexingLogEntry {
  time: string;
  status: string;
  filename: string;
  detail: string;
}

export interface IndexingLogsResponse {
  count: number;
  logs: IndexingLogEntry[];
}

export interface IndexedFileInfo {
  path: string;
  content_preview: string;
  content_length: number;
  mtime: string;
  mtime_formatted: string;
}

export interface IndexedDatabaseResponse {
  total_count: number;
  count: number;
  limit: number;
  offset: number;
  files: IndexedFileInfo[];
}

export interface IndexedFileDetail {
  path: string;
  content: string;
  content_length: number;
  mtime: string;
  mtime_formatted: string;
}

export interface SearchResult {
  path: string;
  name: string;
  directory: string;
  extension: string;
  size: number;
  mtime: string;
  rank: number;
  preview?: string;
  highlight?: Array<{
    start: number;
    end: number;
    text: string;
  }>;
}

export interface SearchResponse {
  query: string;
  count: number;
  results: SearchResult[];
}

export interface Statistics {
  total_indexed_files: number;
  database_size: number;
}

export interface SearchHistoryItem {
  keyword: string;
  last_used: number;
}

export interface SearchHistoryResponse {
  count: number;
  history: SearchHistoryItem[];
}

// API 함수들

/**
 * 서버 상태 확인
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    const data = await response.json();
    return data.status === 'ok';
  } catch (error) {
    console.error('백엔드 연결 실패:', error);
    return false;
  }
}

/**
 * 인덱싱 시작
 */
export async function startIndexing(paths: string[]): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths })
    });
    return await response.json();
  } catch (error) {
    console.error('인덱싱 시작 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱 중지
 */
export async function stopIndexing(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/stop`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('인덱싱 중지 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱 상태 조회
 */
export async function getIndexingStatus(): Promise<IndexingStatus> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/status`);
    return await response.json();
  } catch (error) {
    console.error('상태 조회 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱 로그 조회
 */
export async function getIndexingLogs(count: number = 100): Promise<IndexingLogsResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/logs?count=${count}`);
    return await response.json();
  } catch (error) {
    console.error('로그 조회 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱 로그 초기화
 */
export async function clearIndexingLogs(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/logs/clear`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('로그 초기화 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱 DB 전체 조회 (SELECT * FROM files_fts)
 */
export async function getIndexedDatabase(limit: number = 1000, offset: number = 0): Promise<IndexedDatabaseResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/database?limit=${limit}&offset=${offset}`);
    return await response.json();
  } catch (error) {
    console.error('DB 조회 오류:', error);
    throw error;
  }
}

/**
 * 특정 파일의 상세 정보 조회
 */
export async function getIndexedFileDetail(filePath: string): Promise<IndexedFileDetail> {
  try {
    const encodedPath = encodeURIComponent(filePath);
    const response = await fetch(`${API_BASE_URL}/indexing/database/${encodedPath}`);
    return await response.json();
  } catch (error) {
    console.error('파일 상세 조회 오류:', error);
    throw error;
  }
}

/**
 * 파일 검색 (내용만)
 */
export async function searchFiles(
  query: string,
  maxResults: number = 100,
  includeContent: boolean = true
): Promise<SearchResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        max_results: maxResults,
        include_content: includeContent
      })
    });
    return await response.json();
  } catch (error) {
    console.error('검색 오류:', error);
    throw error;
  }
}

/**
 * 통합 검색 (파일명 + 내용)
 */
export async function searchCombined(
  query: string,
  searchPath?: string,
  maxResults: number = 100
): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/search/combined`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        search_path: searchPath,
        max_results: maxResults
      })
    });
    return await response.json();
  } catch (error) {
    console.error('통합 검색 오류:', error);
    throw error;
  }
}

/**
 * 인덱싱된 파일 내용 조회
 */
export async function getIndexedContent(filePath: string): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/indexing/indexed-content`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: filePath })
    });
    return await response.json();
  } catch (error) {
    console.error('인덱싱 내용 조회 오류:', error);
    throw error;
  }
}

/**
 * 통계 조회
 */
export async function getStatistics(): Promise<Statistics> {
  try {
    const response = await fetch(`${API_BASE_URL}/statistics`);
    return await response.json();
  } catch (error) {
    console.error('통계 조회 오류:', error);
    throw error;
  }
}

/**
 * 데이터베이스 초기화
 */
export async function clearDatabase(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/database/clear`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('데이터베이스 초기화 오류:', error);
    throw error;
  }
}

/**
 * 데이터베이스 최적화
 */
export async function optimizeDatabase(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/database/optimize`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('데이터베이스 최적화 오류:', error);
    throw error;
  }
}

/**
 * 데이터베이스 VACUUM (단편화 제거)
 */
export async function vacuumDatabase(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/database/vacuum`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('데이터베이스 VACUUM 오류:', error);
    throw error;
  }
}

/**
 * 검색 히스토리 조회
 */
export async function getSearchHistory(limit: number = 10): Promise<SearchHistoryResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/search-history?limit=${limit}`);
    return await response.json();
  } catch (error) {
    console.error('검색 히스토리 조회 오류:', error);
    throw error;
  }
}

/**
 * 특정 검색어 삭제
 */
export async function deleteSearchHistoryItem(keyword: string): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/search-history`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword })
    });
    return await response.json();
  } catch (error) {
    console.error('검색 히스토리 삭제 오류:', error);
    throw error;
  }
}

/**
 * 모든 검색 히스토리 삭제
 */
export async function clearSearchHistory(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/search-history/clear`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('검색 히스토리 초기화 오류:', error);
    throw error;
  }
}

/**
 * 사용자 정의 제외 패턴 조회
 */
export async function getExclusionPatterns(): Promise<{ count: number; patterns: string[] }> {
  try {
    const response = await fetch(`${API_BASE_URL}/exclusion-patterns`);
    return await response.json();
  } catch (error) {
    console.error('제외 패턴 조회 오류:', error);
    throw error;
  }
}

/**
 * 사용자 정의 제외 패턴 추가
 */
export async function addExclusionPattern(pattern: string): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/exclusion-patterns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern })
    });
    return await response.json();
  } catch (error) {
    console.error('제외 패턴 추가 오류:', error);
    throw error;
  }
}

/**
 * 사용자 정의 제외 패턴 제거
 */
export async function removeExclusionPattern(pattern: string): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/exclusion-patterns`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern })
    });
    return await response.json();
  } catch (error) {
    console.error('제외 패턴 제거 오류:', error);
    throw error;
  }
}

/**
 * 모든 사용자 정의 제외 패턴 삭제
 */
export async function clearExclusionPatterns(): Promise<any> {
  try {
    const response = await fetch(`${API_BASE_URL}/exclusion-patterns/clear`, {
      method: 'POST'
    });
    return await response.json();
  } catch (error) {
    console.error('제외 패턴 초기화 오류:', error);
    throw error;
  }
}

