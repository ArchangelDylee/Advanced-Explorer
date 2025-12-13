# -*- coding: utf-8 -*-
"""
데이터베이스 모듈 - SQLite FTS5를 사용한 파일 인덱스 관리
"""

import sqlite3
import os
from typing import List, Tuple, Optional
from datetime import datetime
import logging
import sys
import io

# ========================================
# UTF-8 전역 설정 (최우선 실행)
# ========================================
# Windows 콘솔 코드 페이지를 UTF-8로 설정
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

# stdout/stderr를 UTF-8로 재설정 (안전하게)
try:
    if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

try:
    if hasattr(sys.stderr, 'buffer') and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

# 로그 디렉토리 생성
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 로깅 설정 (콘솔 + 파일, UTF-8 인코딩 강제)
log_file = os.path.join(LOG_DIR, 'database.log')
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8', mode='a')
    ]
)
# UTF-8 인코딩 재확인
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler) and hasattr(handler.stream, 'reconfigure'):
        try:
            handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
        
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
            
            # 트랜잭션 격리 수준 설정 (DEFERRED: 읽기는 즉시, 쓰기는 필요 시 락)
            self.conn.isolation_level = "DEFERRED"
            
            # WAL 모드 활성화 (Write-Ahead Logging: 읽기/쓰기 동시 처리)
            self.conn.execute("PRAGMA journal_mode=WAL")
            
            # 동기화 모드 설정 (NORMAL: 빠르면서도 안전)
            self.conn.execute("PRAGMA synchronous=NORMAL")
            
            # FTS5 가상 테이블 생성 (unicode61 토크나이저 사용 - 한글 지원)
            # path: 파일 절대 경로 (검색 제외)
            # content: 파일 텍스트 내용 (검색 대상)
            # mtime: 마지막 수정 시간 (검색 제외, 증분 색인용)
            # deleted: 삭제 여부 (0=존재, 1=삭제됨)
            # deleted_at: 삭제 시간 (UNIX timestamp)
            # tokenize='unicode61': 유니코드 문자(한글, 영문, 숫자 등) 지원
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts 
                USING fts5(
                    path UNINDEXED,
                    content,
                    mtime UNINDEXED,
                    deleted UNINDEXED,
                    deleted_at UNINDEXED,
                    tokenize='unicode61'
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
        파일 인덱스 추가 (트랜잭션 보장)
        
        Args:
            path: 파일 절대 경로
            content: 파일 텍스트 내용
            mtime: 마지막 수정 시간 (UNIX timestamp)
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")
            self.conn.execute(
                "INSERT INTO files_fts (path, content, mtime, deleted, deleted_at) VALUES (?, ?, ?, ?, ?)",
                (path, content, str(mtime), '0', None)
            )
            self.conn.commit()
            logger.debug(f"✓ 파일 인덱스 추가 (커밋됨): {path}")
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except:
                pass
            logger.error(f"파일 인덱스 추가 오류 [{path}]: {e}")
            raise
    
    def insert_files_batch(self, files: List[Tuple[str, str, float]]):
        """
        파일 인덱스 배치 추가 (성능 최적화 + 트랜잭션 보장)
        
        Args:
            files: [(path, content, mtime), ...] 형태의 리스트
        """
        if not files:
            return
            
        try:
            # 명시적 트랜잭션 시작
            self.conn.execute("BEGIN TRANSACTION")
            
            # 배치 삽입을 위한 데이터 변환 (deleted=0, deleted_at=None 추가)
            data = [(path, content, str(mtime), '0', None) for path, content, mtime in files]
            
            self.conn.executemany(
                "INSERT INTO files_fts (path, content, mtime, deleted, deleted_at) VALUES (?, ?, ?, ?, ?)",
                data
            )
            
            # 명시적 커밋
            self.conn.commit()
            logger.info(f"✓ 배치 인덱스 추가 완료 (커밋됨): {len(files)}개 파일")
            
        except sqlite3.Error as e:
            # 롤백 처리
            try:
                self.conn.rollback()
                logger.error(f"배치 인덱스 추가 실패 - 롤백됨: {e}")
            except:
                logger.error(f"롤백 실패: {e}")
            raise
    
    def update_file(self, path: str, content: str, mtime: float):
        """
        파일 인덱스 업데이트 (트랜잭션 보장)
        
        Args:
            path: 파일 절대 경로
            content: 파일 텍스트 내용
            mtime: 마지막 수정 시간 (UNIX timestamp)
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")
            # FTS5는 UPDATE를 지원하므로 직접 업데이트 (deleted=0으로 복원)
            cursor = self.conn.execute(
                "UPDATE files_fts SET content = ?, mtime = ?, deleted = ?, deleted_at = ? WHERE path = ?",
                (content, str(mtime), '0', None, path)
            )
            
            if cursor.rowcount == 0:
                # 업데이트할 행이 없으면 새로 삽입 (이미 트랜잭션 안)
                self.conn.execute(
                    "INSERT INTO files_fts (path, content, mtime, deleted, deleted_at) VALUES (?, ?, ?, ?, ?)",
                    (path, content, str(mtime), '0', None)
                )
            
            self.conn.commit()
            logger.debug(f"✓ 파일 인덱스 업데이트 (커밋됨): {path}")
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except:
                pass
            logger.error(f"파일 인덱스 업데이트 오류 [{path}]: {e}")
            raise
    
    def delete_file(self, path: str):
        """
        파일 인덱스 삭제 (물리적 삭제)

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
    
    def mark_as_deleted(self, path: str):
        """
        파일을 삭제된 것으로 마킹 (논리적 삭제)
        
        Args:
            path: 파일 절대 경로
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")
            deleted_at = datetime.now().timestamp()
            cursor = self.conn.execute(
                "UPDATE files_fts SET deleted = ?, deleted_at = ? WHERE path = ?",
                ('1', str(deleted_at), path)
            )
            
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"🗑️ 파일 삭제 마킹: {path}")
            else:
                self.conn.rollback()
                logger.warning(f"⚠️ 삭제 마킹 실패 (파일 없음): {path}")
                
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except:
                pass
            logger.error(f"파일 삭제 마킹 오류 [{path}]: {e}")
            raise
    
    def unmark_as_deleted(self, path: str):
        """
        파일의 삭제 마킹 제거 (복원)
        
        Args:
            path: 파일 절대 경로
        """
        try:
            self.conn.execute("BEGIN TRANSACTION")
            cursor = self.conn.execute(
                "UPDATE files_fts SET deleted = ?, deleted_at = ? WHERE path = ?",
                ('0', None, path)
            )
            
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"✅ 파일 복원 (삭제 마킹 제거): {path}")
            else:
                self.conn.rollback()
                logger.warning(f"⚠️ 복원 실패 (파일 없음): {path}")
                
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except:
                pass
            logger.error(f"파일 복원 오류 [{path}]: {e}")
            raise
    
    def is_file_indexed(self, path: str) -> bool:
        """
        파일이 인덱싱되어 있는지 확인 (삭제되지 않은 파일만)
        
        Args:
            path: 파일 절대 경로
            
        Returns:
            bool: 인덱싱 여부 (삭제되지 않은 경우만 True)
        """
        try:
            cursor = self.conn.execute(
                "SELECT COUNT(*) as cnt FROM files_fts WHERE path = ? AND deleted = '0'",
                (path,)
            )
            result = cursor.fetchone()
            return result['cnt'] > 0 if result else False
        except sqlite3.Error as e:
            logger.error(f"인덱싱 여부 확인 오류 [{path}]: {e}")
            return False
    
    def get_file_info(self, path: str) -> Optional[dict]:
        """
        파일 정보 조회 (삭제 여부 무관)
        
        Args:
            path: 파일 절대 경로
            
        Returns:
            파일 정보 dict 또는 None
            - mtime: 마지막 수정 시간
            - deleted: 삭제 여부 (True/False)
        """
        try:
            cursor = self.conn.execute(
                "SELECT mtime, deleted FROM files_fts WHERE path = ?",
                (path,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'mtime': float(row['mtime']),
                    'deleted': row['deleted'] == '1'
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"파일 정보 조회 오류 [{path}]: {e}")
            return None
    
    def cleanup_deleted_files(self, days_old: int = 30) -> int:
        """
        오래된 삭제 마킹 파일을 물리적으로 정리
        
        Args:
            days_old: 이 일수보다 오래된 삭제 파일만 정리 (기본: 30일)
            
        Returns:
            정리된 파일 개수
        """
        try:
            # 기준 시간 계산 (현재 시간 - days_old)
            threshold_time = datetime.now().timestamp() - (days_old * 24 * 3600)
            
            # 오래된 삭제 파일 조회
            cursor = self.conn.execute("""
                SELECT path, deleted_at 
                FROM files_fts 
                WHERE deleted = '1' AND deleted_at IS NOT NULL AND CAST(deleted_at AS REAL) < ?
            """, (str(threshold_time),))
            
            old_deleted_files = cursor.fetchall()
            
            if not old_deleted_files:
                logger.info("정리할 삭제 파일이 없습니다.")
                return 0
            
            # 물리적 삭제
            self.conn.execute("BEGIN TRANSACTION")
            for row in old_deleted_files:
                self.conn.execute("DELETE FROM files_fts WHERE path = ? AND deleted = '1'", (row['path'],))
            self.conn.commit()
            
            count = len(old_deleted_files)
            logger.info(f"✅ {count}개의 오래된 삭제 파일 정리 완료 ({days_old}일 이상)")
            return count
            
        except sqlite3.Error as e:
            try:
                self.conn.rollback()
            except:
                pass
            logger.error(f"삭제 파일 정리 오류: {e}")
            return 0
    
    def search(self, query: str, limit: int = 100) -> List[dict]:
        """
        전문 검색 (Full-Text Search)
        
        검색 타입:
        1. 단일 단어: "학교" → 학교를 포함
        2. 복합 단어: "학교 경찰" → 학교 AND 경찰 모두 포함
        3. 따옴표 문장: '"학교 경찰"' → 정확히 "학교 경찰" 포함 (특수문자 포함)
        
        Args:
            query: 검색 쿼리
            limit: 최대 결과 개수
        
        Returns:
            검색 결과 리스트 [{path, content, mtime, rank}, ...]
        """
        try:
            # 따옴표로 감싼 정확한 문장 검색은 LIKE 검색 사용
            # (FTS5는 "and", "or", "not" 같은 예약어를 정확하게 처리 못함)
            is_exact_phrase = query.startswith('"') and query.endswith('"')
            
            if is_exact_phrase:
                # 따옴표 제거
                exact_phrase = query[1:-1]
                
                # LIKE 검색 사용 (정확한 문장 검색, 삭제되지 않은 파일만)
                cursor = self.conn.execute("""
                    SELECT path, content, mtime, 0 as rank
                    FROM files_fts
                    WHERE content LIKE ? AND deleted = '0'
                    LIMIT ?
                """, (f'%{exact_phrase}%', limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'path': row['path'],
                        'content': row['content'][:500],  # 처음 500자만
                        'mtime': row['mtime'],
                        'rank': row['rank']
                    })
                
                logger.info(f"LIKE 정확한 문장 검색 완료: '{exact_phrase}' - {len(results)}개 결과")
                return results
            
            # 일반 FTS5 검색
            fts_query = self._convert_to_fts5_query(query)
            logger.info(f"🔍 FTS5 검색 시작: 원본='{query}', FTS쿼리='{fts_query}'")
            
            cursor = self.conn.execute("""
                SELECT path, content, mtime, rank
                FROM files_fts
                WHERE files_fts MATCH ? AND deleted = '0'
                ORDER BY rank
                LIMIT ?
            """, (fts_query, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'path': row['path'],
                    'content': row['content'][:500],  # 처음 500자만
                    'mtime': row['mtime'],
                    'rank': row['rank']
                })
            
            logger.info(f"✓ FTS5 검색 완료: '{query}' → {len(results)}개 결과")
            return results
            
        except sqlite3.Error as e:
            logger.error(f"검색 오류: {e}")
            return []
    
    def _convert_to_fts5_query(self, query: str) -> str:
        """
        사용자 검색어를 FTS5 쿼리로 변환
        
        Args:
            query: 원본 검색어
        
        Returns:
            FTS5 MATCH 쿼리
        """
        import re
        
        # 1. 따옴표 문장 검색: "학교 경찰" → "학교 경찰" (FTS5 정확 일치)
        # 특수문자가 포함된 경우는 search() 메서드에서 LIKE로 처리하므로 여기서는 FTS5용으로만 변환
        if query.startswith('"') and query.endswith('"'):
            # 이미 따옴표로 감싸져 있으면 그대로 사용
            return query
        
        # 2. 복합 단어 검색: "학교 경찰" → 학교 AND 경찰
        terms = query.split()
        
        if len(terms) == 1:
            # 3. 단일 단어: "학교" → 학교
            # FTS5 특수문자 이스케이프
            escaped = re.sub(r'([-\(\)\[\]"\*])', r'\\\1', terms[0])
            return escaped
        else:
            # 복합 단어 AND 조건
            escaped_terms = []
            for term in terms:
                # FTS5 특수문자 이스케이프
                escaped = re.sub(r'([-\(\)\[\]"\*])', r'\\\1', term)
                escaped_terms.append(escaped)
            
            # FTS5 AND 구문
            return ' AND '.join(escaped_terms)
    
    def get_file_mtime(self, path: str) -> Optional[float]:
        """
        파일의 마지막 수정 시간 조회 (삭제되지 않은 파일만)
        
        Args:
            path: 파일 절대 경로
        
        Returns:
            마지막 수정 시간 (UNIX timestamp) 또는 None
        """
        try:
            cursor = self.conn.execute(
                "SELECT mtime FROM files_fts WHERE path = ? AND deleted = '0'",
                (path,)
            )
            row = cursor.fetchone()
            return float(row['mtime']) if row else None
        except sqlite3.Error as e:
            logger.error(f"mtime 조회 오류 [{path}]: {e}")
            return None
    
    def get_all_indexed_file_paths(self) -> List[str]:
        """
        인덱싱된 모든 파일 경로 조회 (삭제되지 않은 파일만)
        
        Returns:
            파일 경로 리스트
        """
        try:
            cursor = self.conn.execute("SELECT path FROM files_fts WHERE deleted = '0'")
            return [row['path'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"인덱싱된 파일 경로 조회 오류: {e}")
            return []
    
    def get_indexed_files_count(self) -> int:
        """인덱스된 파일 개수 조회 (삭제되지 않은 파일만)"""
        try:
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM files_fts WHERE deleted = '0'")
            return cursor.fetchone()['count']
        except sqlite3.Error as e:
            logger.error(f"파일 개수 조회 오류: {e}")
            return 0
    
    def get_all_indexed_paths(self, limit: int = 10000) -> List[str]:
        """
        인덱스된 모든 파일 경로 조회 (디버깅용)
        
        Args:
            limit: 조회할 최대 개수
        
        Returns:
            파일 경로 리스트
        """
        try:
            cursor = self.conn.execute(f"SELECT path FROM files_fts LIMIT {limit}")
            return [row['path'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"파일 경로 조회 오류: {e}")
            return []
    
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
        인덱싱된 모든 파일 경로 조회 (삭제되지 않은 파일만)
        
        Returns:
            파일 경로 리스트
        """
        try:
            cursor = self.conn.execute("SELECT path FROM files_fts WHERE deleted = '0'")
            return [row['path'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"경로 조회 오류: {e}")
            return []
    
    def get_all_indexed_files(self, limit: int = 1000, offset: int = 0) -> List[dict]:
        """
        인덱싱된 모든 파일 정보 조회 (SELECT * FROM files_fts)
        
        Args:
            limit: 조회할 최대 개수
            offset: 시작 위치
        
        Returns:
            파일 정보 리스트 [{'path': ..., 'content_preview': ..., 'mtime': ..., 'size': ...}, ...]
        """
        try:
            cursor = self.conn.execute(
                """
                SELECT 
                    path, 
                    SUBSTR(content, 1, 200) as content_preview,
                    LENGTH(content) as content_length,
                    mtime
                FROM files_fts 
                ORDER BY mtime DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'path': row['path'],
                    'content_preview': row['content_preview'],
                    'content_length': row['content_length'],
                    'mtime': row['mtime'],
                    'mtime_formatted': datetime.fromtimestamp(float(row['mtime'])).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return results
        except sqlite3.Error as e:
            logger.error(f"전체 파일 조회 오류: {e}")
            return []
    
    def get_indexed_file_detail(self, path: str) -> Optional[dict]:
        """
        특정 파일의 상세 정보 조회
        
        Args:
            path: 파일 경로
        
        Returns:
            파일 상세 정보 또는 None
        """
        try:
            # 경로 정규화 (Windows 백슬래시 통일)
            import os
            normalized_path = os.path.normpath(path)
            logger.debug(f"DB 쿼리: SELECT * FROM files_fts WHERE path = '{normalized_path}'")
            
            cursor = self.conn.execute(
                "SELECT path, content, mtime, deleted, deleted_at FROM files_fts WHERE path = ?",
                (normalized_path,)
            )
            row = cursor.fetchone()
            
            if row:
                is_deleted = row['deleted'] == '1'
                result = {
                    'path': row['path'],
                    'content': row['content'],
                    'content_length': len(row['content']),
                    'mtime': row['mtime'],
                    'mtime_formatted': datetime.fromtimestamp(float(row['mtime'])).strftime('%Y-%m-%d %H:%M:%S'),
                    'deleted': is_deleted
                }
                
                if is_deleted and row['deleted_at']:
                    result['deleted_at'] = row['deleted_at']
                    result['deleted_at_formatted'] = datetime.fromtimestamp(float(row['deleted_at'])).strftime('%Y-%m-%d %H:%M:%S')
                    logger.info(f"⚠️ 삭제된 파일 발견: {normalized_path} (삭제 시간: {result['deleted_at_formatted']})")
                else:
                    logger.info(f"✓ 파일 발견: {normalized_path} (길이: {len(row['content'])}자)")
                
                return result
            else:
                logger.debug(f"✗ DB에 파일 없음 (정규화된 경로): {normalized_path}")
                
                # 대소문자 무시하고 검색
                cursor2 = self.conn.execute(
                    "SELECT path, content, mtime, deleted, deleted_at FROM files_fts WHERE LOWER(path) = LOWER(?)",
                    (normalized_path,)
                )
                row2 = cursor2.fetchone()
                if row2:
                    logger.warning(f"경로 대소문자 불일치: DB={row2['path']}, 요청={normalized_path}")
                    is_deleted = row2['deleted'] == '1'
                    result = {
                        'path': row2['path'],
                        'content': row2['content'],
                        'content_length': len(row2['content']),
                        'mtime': row2['mtime'],
                        'mtime_formatted': datetime.fromtimestamp(float(row2['mtime'])).strftime('%Y-%m-%d %H:%M:%S'),
                        'deleted': is_deleted
                    }
                    
                    if is_deleted and row2['deleted_at']:
                        result['deleted_at'] = row2['deleted_at']
                        result['deleted_at_formatted'] = datetime.fromtimestamp(float(row2['deleted_at'])).strftime('%Y-%m-%d %H:%M:%S')
                    
                    return result
                
                # 슬래시 방향 변경해서 다시 시도 (\ -> / or / -> \)
                alt_path = normalized_path.replace('\\', '/') if '\\' in normalized_path else normalized_path.replace('/', '\\')
                cursor3 = self.conn.execute(
                    "SELECT path, content, mtime FROM files_fts WHERE path = ? OR LOWER(path) = LOWER(?)",
                    (alt_path, alt_path)
                )
                row3 = cursor3.fetchone()
                if row3:
                    logger.warning(f"경로 슬래시 불일치: DB={row3['path']}, 요청={normalized_path}")
                    return {
                        'path': row3['path'],
                        'content': row3['content'],
                        'content_length': len(row3['content']),
                        'mtime': row3['mtime'],
                        'mtime_formatted': datetime.fromtimestamp(float(row3['mtime'])).strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                logger.warning(f"✗ 파일을 찾을 수 없음: {path} (정규화: {normalized_path}, 대체: {alt_path})")
                
            return None
        except sqlite3.Error as e:
            logger.error(f"파일 상세 조회 오류 [{path}]: {e}")
            return None
    
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
        """데이터베이스 연결 종료 및 Lock 해제"""
        if self.conn:
            try:
                # 보류 중인 모든 변경사항 커밋
                self.conn.commit()
                logger.info("✓ DB 변경사항 커밋 완료")
            except Exception as e:
                logger.warning(f"DB 커밋 오류 (무시됨): {e}")
            
            try:
                # 연결 종료
                self.conn.close()
                logger.info("✓ 데이터베이스 연결 종료 - Lock 해제됨")
            except Exception as e:
                logger.error(f"DB 연결 종료 오류: {e}")
            finally:
                self.conn = None


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

