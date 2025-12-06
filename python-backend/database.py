"""
데이터베이스 모듈 - SQLite FTS5를 사용한 파일 인덱스 관리
"""

import sqlite3
import os
from typing import List, Tuple, Optional
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite FTS5 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = "file_index.db"):
        """
        데이터베이스 매니저 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_database()
    
    def _initialize_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            # FTS5 가상 테이블 생성 (trigram 토크나이저 사용)
            # path: 파일 절대 경로 (검색 제외)
            # content: 파일 텍스트 내용 (검색 대상)
            # mtime: 마지막 수정 시간 (검색 제외, 증분 색인용)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts 
                USING fts5(
                    path UNINDEXED, 
                    content, 
                    mtime UNINDEXED, 
                    tokenize='trigram'
                )
            """)
            
            # 메타데이터 테이블 생성 (인덱싱 통계 및 설정)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS indexing_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 검색 히스토리 테이블 생성
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    keyword TEXT PRIMARY KEY,
                    last_used REAL NOT NULL
                )
            """)
            
            self.conn.commit()
            logger.info(f"데이터베이스 초기화 완료: {self.db_path}")
            
        except sqlite3.Error as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
            raise
    
    def insert_file(self, path: str, content: str, mtime: float):
        """
        파일 인덱스 추가
        
        Args:
            path: 파일 절대 경로
            content: 파일 텍스트 내용
            mtime: 마지막 수정 시간 (UNIX timestamp)
        """
        try:
            self.conn.execute(
                "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
                (path, content, str(mtime))
            )
            self.conn.commit()
            logger.debug(f"파일 인덱스 추가: {path}")
        except sqlite3.Error as e:
            logger.error(f"파일 인덱스 추가 오류 [{path}]: {e}")
            raise
    
    def insert_files_batch(self, files: List[Tuple[str, str, float]]):
        """
        파일 인덱스 배치 추가 (성능 최적화)
        
        Args:
            files: [(path, content, mtime), ...] 형태의 리스트
        """
        try:
            # 배치 삽입을 위한 데이터 변환
            data = [(path, content, str(mtime)) for path, content, mtime in files]
            
            self.conn.executemany(
                "INSERT INTO files_fts (path, content, mtime) VALUES (?, ?, ?)",
                data
            )
            self.conn.commit()
            logger.info(f"배치 인덱스 추가 완료: {len(files)}개 파일")
        except sqlite3.Error as e:
            logger.error(f"배치 인덱스 추가 오류: {e}")
            raise
    
    def update_file(self, path: str, content: str, mtime: float):
        """
        파일 인덱스 업데이트
        
        Args:
            path: 파일 절대 경로
            content: 파일 텍스트 내용
            mtime: 마지막 수정 시간 (UNIX timestamp)
        """
        try:
            # FTS5는 UPDATE를 지원하므로 직접 업데이트
            cursor = self.conn.execute(
                "UPDATE files_fts SET content = ?, mtime = ? WHERE path = ?",
                (content, str(mtime), path)
            )
            
            if cursor.rowcount == 0:
                # 업데이트할 행이 없으면 새로 삽입
                self.insert_file(path, content, mtime)
            else:
                self.conn.commit()
                logger.debug(f"파일 인덱스 업데이트: {path}")
        except sqlite3.Error as e:
            logger.error(f"파일 인덱스 업데이트 오류 [{path}]: {e}")
            raise
    
    def delete_file(self, path: str):
        """
        파일 인덱스 삭제
        
        Args:
            path: 파일 절대 경로
        """
        try:
            self.conn.execute("DELETE FROM files_fts WHERE path = ?", (path,))
            self.conn.commit()
            logger.debug(f"파일 인덱스 삭제: {path}")
        except sqlite3.Error as e:
            logger.error(f"파일 인덱스 삭제 오류 [{path}]: {e}")
            raise
    
    def search(self, query: str, limit: int = 100) -> List[dict]:
        """
        전문 검색 (Full-Text Search)
        
        Args:
            query: 검색 쿼리
            limit: 최대 결과 개수
        
        Returns:
            검색 결과 리스트 [{path, content, mtime, rank}, ...]
        """
        try:
            cursor = self.conn.execute("""
                SELECT path, content, mtime, rank
                FROM files_fts
                WHERE files_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'path': row['path'],
                    'content': row['content'][:500],  # 처음 500자만
                    'mtime': row['mtime'],
                    'rank': row['rank']
                })
            
            logger.info(f"검색 완료: '{query}' - {len(results)}개 결과")
            return results
            
        except sqlite3.Error as e:
            logger.error(f"검색 오류: {e}")
            return []
    
    def get_file_mtime(self, path: str) -> Optional[float]:
        """
        파일의 마지막 수정 시간 조회
        
        Args:
            path: 파일 절대 경로
        
        Returns:
            마지막 수정 시간 (UNIX timestamp) 또는 None
        """
        try:
            cursor = self.conn.execute(
                "SELECT mtime FROM files_fts WHERE path = ?", 
                (path,)
            )
            row = cursor.fetchone()
            return float(row['mtime']) if row else None
        except sqlite3.Error as e:
            logger.error(f"mtime 조회 오류 [{path}]: {e}")
            return None
    
    def get_indexed_files_count(self) -> int:
        """인덱스된 파일 개수 조회"""
        try:
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM files_fts")
            return cursor.fetchone()['count']
        except sqlite3.Error as e:
            logger.error(f"파일 개수 조회 오류: {e}")
            return 0
    
    def clear_index(self):
        """모든 인덱스 삭제"""
        try:
            self.conn.execute("DELETE FROM files_fts")
            self.conn.commit()
            logger.info("모든 인덱스 삭제 완료")
        except sqlite3.Error as e:
            logger.error(f"인덱스 삭제 오류: {e}")
            raise
    
    def optimize(self):
        """FTS5 인덱스 최적화"""
        try:
            self.conn.execute("INSERT INTO files_fts(files_fts) VALUES('optimize')")
            self.conn.commit()
            logger.info("인덱스 최적화 완료")
        except sqlite3.Error as e:
            logger.error(f"인덱스 최적화 오류: {e}")
    
    def vacuum(self):
        """
        데이터베이스 VACUUM (단편화 제거 및 용량 최적화)
        DELETE/INSERT로 인한 공간 낭비를 제거
        """
        try:
            self.conn.execute("VACUUM")
            self.conn.commit()
            logger.info("데이터베이스 VACUUM 완료")
        except sqlite3.Error as e:
            logger.error(f"VACUUM 오류: {e}")
    
    def get_all_indexed_paths(self) -> List[str]:
        """
        인덱싱된 모든 파일 경로 조회
        
        Returns:
            파일 경로 리스트
        """
        try:
            cursor = self.conn.execute("SELECT path FROM files_fts")
            return [row['path'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"경로 조회 오류: {e}")
            return []
    
    def add_search_history(self, keyword: str):
        """
        검색 히스토리 추가 또는 업데이트
        
        Args:
            keyword: 검색어
        """
        try:
            import time
            current_time = time.time()
            
            self.conn.execute("""
                INSERT INTO search_history (keyword, last_used) 
                VALUES (?, ?)
                ON CONFLICT(keyword) DO UPDATE SET last_used = ?
            """, (keyword, current_time, current_time))
            
            self.conn.commit()
            logger.debug(f"검색 히스토리 추가: {keyword}")
        except sqlite3.Error as e:
            logger.error(f"검색 히스토리 추가 오류: {e}")
    
    def get_search_history(self, limit: int = 10) -> List[dict]:
        """
        최근 검색어 조회
        
        Args:
            limit: 최대 개수
        
        Returns:
            검색어 리스트 [{keyword, last_used}, ...]
        """
        try:
            cursor = self.conn.execute("""
                SELECT keyword, last_used 
                FROM search_history 
                ORDER BY last_used DESC 
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'keyword': row['keyword'],
                    'last_used': row['last_used']
                })
            
            return results
        except sqlite3.Error as e:
            logger.error(f"검색 히스토리 조회 오류: {e}")
            return []
    
    def delete_search_history(self, keyword: str):
        """
        특정 검색어 삭제
        
        Args:
            keyword: 검색어
        """
        try:
            self.conn.execute("DELETE FROM search_history WHERE keyword = ?", (keyword,))
            self.conn.commit()
            logger.debug(f"검색 히스토리 삭제: {keyword}")
        except sqlite3.Error as e:
            logger.error(f"검색 히스토리 삭제 오류: {e}")
    
    def clear_search_history(self):
        """모든 검색 히스토리 삭제"""
        try:
            self.conn.execute("DELETE FROM search_history")
            self.conn.commit()
            logger.info("모든 검색 히스토리 삭제 완료")
        except sqlite3.Error as e:
            logger.error(f"검색 히스토리 삭제 오류: {e}")
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            logger.info("데이터베이스 연결 종료")


# 테스트 코드
if __name__ == "__main__":
    # 데이터베이스 테스트
    db = DatabaseManager("test_index.db")
    
    # 테스트 데이터 삽입
    db.insert_file("C:\\test\\file1.txt", "안녕하세요 테스트 파일입니다.", 1234567890.0)
    db.insert_file("C:\\test\\file2.txt", "Python 인덱싱 엔진 테스트", 1234567891.0)
    
    # 검색 테스트
    results = db.search("테스트")
    print(f"검색 결과: {len(results)}개")
    for result in results:
        print(f"  - {result['path']}: {result['content']}")
    
    # 통계
    print(f"총 인덱스된 파일: {db.get_indexed_files_count()}개")
    
    # 검색 히스토리 테스트
    print("\n=== 검색 히스토리 테스트 ===")
    db.add_search_history("테스트")
    db.add_search_history("Python")
    db.add_search_history("인덱싱")
    
    history = db.get_search_history(10)
    print(f"검색 히스토리: {len(history)}개")
    for item in history:
        print(f"  - {item['keyword']} (시간: {item['last_used']})")
    
    # 검색어 삭제 테스트
    db.delete_search_history("테스트")
    print(f"\n삭제 후 검색 히스토리: {len(db.get_search_history(10))}개")
    
    # 정리
    db.close()
    os.remove("test_index.db")
    print("\n테스트 완료")

