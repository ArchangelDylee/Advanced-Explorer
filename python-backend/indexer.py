"""
파일 인덱싱 엔진 - 비동기 파일 시스템 크롤링 및 텍스트 추출
"""

import os
import threading
from pathlib import Path
from typing import List, Callable, Optional, Dict
import logging
import time
from queue import Queue
from datetime import datetime
import traceback
import signal
from functools import wraps

# 텍스트 추출 라이브러리
import chardet  # 인코딩 자동 감지

# 문서 파일 파싱
try:
    import docx  # python-docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx not installed. .docx support disabled.")

try:
    from pptx import Presentation  # python-pptx
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False
    logging.warning("python-pptx not installed. .pptx support disabled.")

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PyMuPDF not installed. .pdf support disabled.")

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False
    logging.warning("openpyxl not installed. .xlsx support disabled.")

try:
    import win32com.client
    import pythoncom
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    logging.warning("pywin32 not installed. .doc, .ppt, .xls, .hwp support disabled.")

try:
    import olefile
    OLEFILE_AVAILABLE = True
except ImportError:
    OLEFILE_AVAILABLE = False
    logging.warning("olefile not installed. Alternative .hwp support disabled.")

from database import DatabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 상수 정의
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
PARSE_TIMEOUT = 60  # 60초


class TimeoutError(Exception):
    """타임아웃 예외"""
    pass


def timeout_handler(signum, frame):
    """타임아웃 시그널 핸들러"""
    raise TimeoutError("Parsing timeout")


def with_timeout(seconds):
    """타임아웃 데코레이터 (Windows에서는 제한적)"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Windows에서는 signal.alarm이 작동하지 않으므로 threading 사용
            result = [TimeoutError("Timeout")]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e
            
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=seconds)
            
            if thread.is_alive():
                # 타임아웃 발생
                raise TimeoutError(f"Function execution exceeded {seconds} seconds")
            
            if isinstance(result[0], Exception):
                raise result[0]
            
            return result[0]
        return wrapper
    return decorator


class FileIndexer:
    """파일 인덱싱 엔진 - Worker Thread에서 실행"""
    
    # 지원하는 파일 확장자
    SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.log', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', 
                                  '.java', '.cpp', '.c', '.h', '.cs', '.json', '.xml', '.html', 
                                  '.css', '.sql', '.sh', '.bat', '.ps1', '.yaml', '.yml'}
    
    SUPPORTED_DOC_EXTENSIONS = {'.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.pdf', '.hwp'}
    
    # 제외할 폴더 패턴
    EXCLUDED_DIRS = {
        '.git', 'node_modules', 'venv', 'env', '__pycache__', 
        '.vscode', '.idea', 'dist', 'build', 'out', 'target',
        '.next', '.nuxt', '.cache', '.temp', '.tmp',
        'vendor', 'packages', 'bower_components'
    }
    
    # 제외할 파일 패턴 (정확한 이름 매칭)
    EXCLUDED_FILES = {
        'desktop.ini', 'thumbs.db', 'Thumbs.db', 'ehthumbs.db',
        '.DS_Store', 'Icon\r', '.gitignore', '.gitattributes'
    }
    
    # Office 임시 파일 패턴 (접두사)
    OFFICE_TEMP_PREFIXES = ('~$', '~WRL')
    
    # 제외할 확장자 (실행파일 및 바이너리)
    EXCLUDED_EXTENSIONS = {
        '.exe', '.dll', '.sys', '.bin', '.so', '.dylib', '.a', '.lib',
        '.o', '.obj', '.class', '.pyc', '.pyo', '.pyd',
        '.iso', '.img', '.dmg', '.vhd', '.vmdk',
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
        '.mp3', '.mp4', '.avi', '.mkv', '.mov', '.flv',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
        '.ttf', '.otf', '.woff', '.woff2', '.eot'
    }
    
    # 제외할 경로 접두사 (대소문자 구분 없음)
    EXCLUDED_PATH_PREFIXES = [
        'C:\\Windows',
        'C:\\Program Files',
        'C:\\Program Files (x86)',
        'C:\\ProgramData',
        'C:\\$Recycle.Bin',
        'C:\\System Volume Information',
        'C:\\Recovery',
        'C:\\pagefile.sys',
        'C:\\hiberfil.sys',
        'C:\\swapfile.sys'
    ]
    
    def __init__(self, db_manager: DatabaseManager, log_dir: str = None):
        """
        파일 인덱서 초기화
        
        Args:
            db_manager: 데이터베이스 매니저 인스턴스
            log_dir: 로그 파일 디렉토리 (기본: python-backend/logs)
        """
        self.db = db_manager
        self.is_running = False
        self.current_thread: Optional[threading.Thread] = None
        self.progress_callback: Optional[Callable] = None
        self.log_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        self.stop_flag = threading.Event()
        
        # 로그 디렉토리 설정
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 로그 파일 경로
        self.skipcheck_file = os.path.join(self.log_dir, 'skipcheck.txt')
        self.error_file = os.path.join(self.log_dir, 'error.txt')
        
        # 사용자 정의 제외 패턴
        self.custom_excluded_patterns: List[str] = []
        
        # Skip된 파일 목록 (재시도용)
        self.skipped_files: Dict[str, Dict[str, any]] = {}  # {path: {reason, time, retry_count}}
        self.skipped_files_lock = threading.Lock()
        
        # 재시도 스레드
        self.retry_thread: Optional[threading.Thread] = None
        self.retry_stop_flag = threading.Event()
        self.retry_interval = 300  # 5분 (초 단위)
        
        # 인덱싱 로그 (메모리, 최근 500개)
        self.indexing_logs: List[Dict[str, str]] = []
        self.indexing_logs_lock = threading.Lock()
        self.max_logs = 500
        
        # 통계
        self.stats = {
            'total_files': 0,
            'indexed_files': 0,
            'skipped_files': 0,
            'error_files': 0,
            'new_files': 0,
            'modified_files': 0,
            'deleted_files': 0,
            'start_time': None,
            'end_time': None
        }
    
    def add_exclusion_pattern(self, pattern: str):
        """
        사용자 정의 제외 패턴 추가
        
        Args:
            pattern: 제외할 경로 패턴 (예: "C:\\SecureFolder", "*/private/*")
        """
        if pattern and pattern not in self.custom_excluded_patterns:
            self.custom_excluded_patterns.append(pattern)
            logger.info(f"제외 패턴 추가: {pattern}")
    
    def remove_exclusion_pattern(self, pattern: str):
        """사용자 정의 제외 패턴 제거"""
        if pattern in self.custom_excluded_patterns:
            self.custom_excluded_patterns.remove(pattern)
            logger.info(f"제외 패턴 제거: {pattern}")
    
    def clear_exclusion_patterns(self):
        """모든 사용자 정의 제외 패턴 제거"""
        self.custom_excluded_patterns = []
        logger.info("모든 사용자 정의 제외 패턴 제거")
    
    def get_exclusion_patterns(self) -> List[str]:
        """사용자 정의 제외 패턴 조회"""
        return self.custom_excluded_patterns.copy()
    
    def start_indexing(self, root_paths: List[str], 
                      progress_callback: Optional[Callable] = None,
                      log_callback: Optional[Callable] = None,
                      status_callback: Optional[Callable] = None):
        """
        비동기 인덱싱 시작
        
        Args:
            root_paths: 인덱싱할 루트 디렉토리 리스트
            progress_callback: 진행 상황 콜백 (current, total, path)
            log_callback: 로그 콜백 (status, filename, detail)
            status_callback: 상태 콜백 (status_text)
        """
        if self.is_running:
            logger.warning("인덱싱이 이미 실행 중입니다.")
            return False
        
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.stop_flag.clear()
        
        # Worker 쓰레드에서 실행
        self.current_thread = threading.Thread(
            target=self._indexing_worker,
            args=(root_paths,),
            daemon=True
        )
        self.current_thread.start()
        return True
    
    def _log_skip(self, path: str, reason: str):
        """
        Skip 로그 기록 (skipcheck.txt 및 재시도 목록)
        
        Format: [Timestamp] Path : Reason
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f"[{timestamp}] {path} : {reason}\n"
            
            with open(self.skipcheck_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
            
            # 재시도 가능한 오류인 경우 목록에 추가
            retryable_reasons = [
                'File locked', 'Permission denied', 'Parsing timeout',
                'Password protected'  # 사용자가 암호 해제할 수 있음
            ]
            
            if any(retryable in reason for retryable in retryable_reasons):
                with self.skipped_files_lock:
                    if path not in self.skipped_files:
                        self.skipped_files[path] = {
                            'reason': reason,
                            'time': time.time(),
                            'retry_count': 0
                        }
            
            # 메모리에 로그 추가
            filename = os.path.basename(path)
            self._add_log_to_memory('Skip', filename, reason)
            
            # UI 로그 콜백
            if self.log_callback:
                self.log_callback('Skip', filename, reason)
        
        except Exception as e:
            logger.error(f"Skip 로그 기록 오류: {e}")
    
    def _log_error(self, path: str, error: Exception):
        """
        에러 로그 기록 (error.txt)
        
        트레이스백 포함
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_msg = f"\n[{timestamp}] {path}\n"
            error_msg += f"Error: {str(error)}\n"
            error_msg += f"Traceback:\n{traceback.format_exc()}\n"
            error_msg += "=" * 80 + "\n"
            
            with open(self.error_file, 'a', encoding='utf-8') as f:
                f.write(error_msg)
            
            # 메모리에 로그 추가
            filename = os.path.basename(path)
            self._add_log_to_memory('Error', filename, str(error))
            
            # UI 로그 콜백
            if self.log_callback:
                self.log_callback('Error', filename, str(error))
        
        except Exception as e:
            logger.error(f"에러 로그 기록 오류: {e}")
    
    def _add_log_to_memory(self, status: str, filename: str, detail: str):
        """
        메모리에 로그 추가 (API 조회용)
        
        Args:
            status: 상태 ('Success', 'Skip', 'Error', 'Indexing', 'Retry Success')
            filename: 파일명
            detail: 상세 정보
        """
        with self.indexing_logs_lock:
            log_entry = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'status': status,
                'filename': filename,
                'detail': detail
            }
            self.indexing_logs.insert(0, log_entry)  # 최신 로그를 앞에
            # 최대 개수 유지
            if len(self.indexing_logs) > self.max_logs:
                self.indexing_logs = self.indexing_logs[:self.max_logs]
    
    def get_recent_logs(self, count: int = 100) -> List[Dict[str, str]]:
        """
        최근 로그 조회
        
        Args:
            count: 조회할 로그 수
        
        Returns:
            로그 리스트
        """
        with self.indexing_logs_lock:
            return self.indexing_logs[:count]
    
    def clear_logs(self):
        """로그 초기화"""
        with self.indexing_logs_lock:
            self.indexing_logs = []
    
    def _count_tokens(self, text: str) -> int:
        """
        텍스트의 토큰(단어) 수 계산
        
        Args:
            text: 텍스트 문자열
        
        Returns:
            토큰 수
        """
        if not text:
            return 0
        # 공백, 줄바꿈 등으로 분리하여 토큰 수 계산
        tokens = text.split()
        return len(tokens)
    
    def _log_success(self, path: str, char_count: int, token_count: int = 0, db_saved: bool = True):
        """
        성공 로그 (UI만)
        
        Args:
            path: 파일 경로
            char_count: 추출된 문자 수
            token_count: 토큰(단어) 수
            db_saved: DB 저장 성공 여부
        """
        filename = os.path.basename(path)
        db_status = "✓ DB 저장 완료" if db_saved else "⊗ DB 저장 대기"
        detail = f'{char_count:,}자 / {token_count:,}토큰 | {db_status}'
        
        # 메모리에 로그 추가
        self._add_log_to_memory('Success', filename, detail)
        
        # UI 콜백
        if self.log_callback:
            self.log_callback('Success', filename, detail)
    
    def _log_indexing(self, path: str):
        """
        인덱싱 시작 로그 (현재 처리 중인 파일 표시)
        
        Args:
            path: 파일 경로
        """
        filename = os.path.basename(path)
        detail = '처리 중...'
        
        # 메모리에 로그 추가
        self._add_log_to_memory('Indexing', filename, detail)
        
        # UI 콜백
        if self.log_callback:
            self.log_callback('Indexing', filename, detail)
    
    def _update_status(self, status: str):
        """상태 업데이트"""
        if self.status_callback:
            self.status_callback(status)
    
    def stop_indexing(self):
        """인덱싱 중지"""
        if self.is_running:
            logger.info("인덱싱 중지 요청...")
            self.stop_flag.set()
    
    def stop_retry_worker(self):
        """재시도 워커 중지"""
        if self.retry_thread and self.retry_thread.is_alive():
            logger.info("재시도 워커 중지 요청...")
            self.retry_stop_flag.set()
            self.retry_thread.join(timeout=2)
            logger.info("재시도 워커 중지됨")
    
    def _indexing_worker(self, root_paths: List[str]):
        """인덱싱 워커 (백그라운드 쓰레드) - 증분 색인"""
        self.is_running = True
        self.stats = {
            'total_files': 0,
            'indexed_files': 0,
            'skipped_files': 0,
            'error_files': 0,
            'new_files': 0,
            'modified_files': 0,
            'deleted_files': 0,
            'start_time': time.time(),
            'end_time': None
        }
        
        logger.info(f"인덱싱 시작: {root_paths}")
        self._update_status("파일 수집 중...")
        
        try:
            # 1단계: 파일 목록 수집
            all_files = []
            for root_path in root_paths:
                if self.stop_flag.is_set():
                    break
                all_files.extend(self._collect_files(root_path))
            
            self.stats['total_files'] = len(all_files)
            logger.info(f"수집된 파일: {len(all_files)}개")
            self._update_status(f"총 {len(all_files)}개 파일 발견")
            
            # 2단계: 증분 인덱싱 (New/Modified 파일만)
            self._update_status("증분 인덱싱 중...")
            self._process_files_incremental(all_files)
            
            # 3단계: 삭제된 파일 정리
            self._update_status("삭제된 파일 정리 중...")
            self._cleanup_deleted_files(all_files)
            
            # 4단계: DB 최적화 (VACUUM)
            self._update_status("데이터베이스 최적화 중...")
            self.db.vacuum()
            
            # 인덱스 최적화
            self.db.optimize()
            
        except Exception as e:
            logger.error(f"인덱싱 워커 오류: {e}")
            self._log_error("IndexingWorker", e)
        
        finally:
            self.stats['end_time'] = time.time()
            elapsed = self.stats['end_time'] - self.stats['start_time']
            summary = f"완료: {self.stats['indexed_files']}개 인덱싱 ({elapsed:.2f}초)"
            logger.info(summary)
            self._update_status(summary)
            self.is_running = False
            
            # 재시도 워커 시작 (Skip된 파일이 있는 경우)
            with self.skipped_files_lock:
                if self.skipped_files:
                    logger.info(f"재시도 워커 시작: Skip된 파일 {len(self.skipped_files)}개")
                    self.start_retry_worker()
    
    def _process_files_incremental(self, all_files: List[str]):
        """증분 파일 처리 (New/Modified만)"""
        batch_size = 100
        batch = []
        
        for i, file_path in enumerate(all_files):
            if self.stop_flag.is_set():
                logger.info("인덱싱 중지됨")
                break
            
            try:
                # 진행 상황 콜백
                if self.progress_callback:
                    self.progress_callback(i + 1, len(all_files), file_path)
                
                # 파일 크기 체크 (100MB 초과 시 스킵)
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_FILE_SIZE:
                        self._log_skip(file_path, f"Size exceeded ({file_size / 1024 / 1024:.1f}MB)")
                        self.stats['skipped_files'] += 1
                        continue
                except Exception:
                    pass
                
                # 증분 인덱싱: New or Modified?
                current_mtime = os.path.getmtime(file_path)
                indexed_mtime = self.db.get_file_mtime(file_path)
                
                if indexed_mtime is not None:
                    # 파일이 이미 인덱싱됨
                    if abs(current_mtime - indexed_mtime) < 1.0:
                        # 수정되지 않음 - 스킵
                        self.stats['skipped_files'] += 1
                        continue
                    else:
                        # 수정됨 - 재인덱싱
                        is_new = False
                        self.stats['modified_files'] += 1
                else:
                    # 새 파일
                    is_new = True
                    self.stats['new_files'] += 1
                
                # 현재 처리 중인 파일 로그
                self._log_indexing(file_path)
                
                # 텍스트 추출 (타임아웃 체크)
                content = self._extract_text_safe(file_path)
                
                if content:
                    # 토큰 수 계산
                    token_count = self._count_tokens(content)
                    
                    if is_new:
                        # 새 파일은 배치에 추가
                        batch.append((file_path, content, current_mtime))
                        self.stats['indexed_files'] += 1
                        # DB 저장 대기 상태로 로그
                        self._log_success(file_path, len(content), token_count, db_saved=False)
                    else:
                        # 수정된 파일은 즉시 업데이트
                        try:
                            self.db.update_file(file_path, content, current_mtime)
                            self.stats['indexed_files'] += 1
                            # DB 저장 완료 상태로 로그
                            self._log_success(file_path, len(content), token_count, db_saved=True)
                        except Exception as e:
                            logger.error(f"DB 업데이트 오류 [{file_path}]: {e}")
                            self._log_error(file_path, e)
                            self.stats['error_files'] += 1
                            continue
                    
                    # 배치가 가득 찼으면 DB에 저장
                    if len(batch) >= batch_size:
                        try:
                            self.db.insert_files_batch(batch)
                            # 배치 저장 후 로그 업데이트
                            for saved_path, saved_content, _ in batch:
                                saved_token_count = self._count_tokens(saved_content)
                                self._log_success(saved_path, len(saved_content), saved_token_count, db_saved=True)
                            batch = []
                        except Exception as e:
                            logger.error(f"DB 배치 저장 오류: {e}")
                            batch = []
                else:
                    self.stats['skipped_files'] += 1
            
            except PermissionError as e:
                # 파일 잠금
                self._log_skip(file_path, "File locked or Permission denied")
                self.stats['skipped_files'] += 1
            
            except Exception as e:
                logger.error(f"파일 처리 오류 [{file_path}]: {e}")
                self._log_error(file_path, e)
                self.stats['error_files'] += 1
        
        # 남은 배치 저장
        if batch:
            try:
                self.db.insert_files_batch(batch)
                # 배치 저장 후 로그 업데이트
                for saved_path, saved_content, _ in batch:
                    saved_token_count = self._count_tokens(saved_content)
                    self._log_success(saved_path, len(saved_content), saved_token_count, db_saved=True)
            except Exception as e:
                logger.error(f"DB 최종 배치 저장 오류: {e}")
    
    def _cleanup_deleted_files(self, current_files: List[str]):
        """삭제된 파일을 DB에서 제거"""
        try:
            # 현재 파일 세트
            current_file_set = set(current_files)
            
            # DB의 모든 파일 경로 조회
            indexed_files = self.db.get_all_indexed_paths()
            
            # 삭제된 파일 찾기
            deleted_files = [f for f in indexed_files if f not in current_file_set]
            
            # 삭제
            for file_path in deleted_files:
                self.db.delete_file(file_path)
                self.stats['deleted_files'] += 1
            
            if deleted_files:
                logger.info(f"삭제된 파일 {len(deleted_files)}개 정리 완료")
        
        except Exception as e:
            logger.error(f"삭제된 파일 정리 오류: {e}")
    
    def _extract_text_safe(self, file_path: str) -> Optional[str]:
        """
        안전한 텍스트 추출 (타임아웃, 예외 처리)
        
        Returns:
            추출된 텍스트 또는 None
        """
        try:
            # 타임아웃 적용 (60초)
            @with_timeout(PARSE_TIMEOUT)
            def extract():
                return self._extract_text(file_path)
            
            return extract()
        
        except TimeoutError:
            self._log_skip(file_path, f"Parsing timeout (>{PARSE_TIMEOUT}s)")
            return None
        
        except PermissionError:
            self._log_skip(file_path, "File locked or Permission denied")
            return None
        
        except Exception as e:
            # 암호화된 파일, 손상된 파일 등
            error_msg = str(e).lower()
            if 'password' in error_msg or 'encrypted' in error_msg:
                self._log_skip(file_path, "Password protected")
            elif 'corrupt' in error_msg or 'damaged' in error_msg:
                self._log_skip(file_path, "File corrupted")
            else:
                self._log_skip(file_path, f"Parse error: {str(e)[:100]}")
            return None
    
    def _collect_files(self, root_path: str) -> List[str]:
        """
        파일 시스템 크롤링 (제외 규칙 적용)
        
        Args:
            root_path: 루트 디렉토리
        
        Returns:
            파일 경로 리스트
        """
        files = []
        
        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # 제외할 디렉토리 필터링
                dirnames[:] = [d for d in dirnames if self._should_include_dir(d, dirpath)]
                
                if self.stop_flag.is_set():
                    break
                
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    
                    # 파일 포함 여부 확인
                    if not self._should_include_file(filename, file_path):
                        continue
                    
                    files.append(file_path)
        
        except Exception as e:
            logger.error(f"파일 수집 오류 [{root_path}]: {e}")
        
        return files
    
    def _should_include_dir(self, dirname: str, dirpath: str) -> bool:
        """
        디렉토리 포함 여부 확인
        
        Args:
            dirname: 디렉토리 이름
            dirpath: 디렉토리 전체 경로
        
        Returns:
            True면 포함, False면 제외
        """
        # 특수 문자로 시작하는 디렉토리 제외
        if not self._is_valid_name(dirname):
            return False
        
        # 제외 디렉토리 목록에 있으면 제외
        if dirname.lower() in self.EXCLUDED_DIRS:
            return False
        
        # 전체 경로가 제외 경로 접두사에 해당하면 제외
        full_path = os.path.join(dirpath, dirname)
        for excluded_prefix in self.EXCLUDED_PATH_PREFIXES:
            if full_path.lower().startswith(excluded_prefix.lower()):
                return False
        
        return True
    
    def _should_include_file(self, filename: str, filepath: str) -> bool:
        """
        파일 포함 여부 확인
        
        Args:
            filename: 파일 이름
            filepath: 파일 전체 경로
        
        Returns:
            True면 포함, False면 제외
        """
        # 특수 문자로 시작하는 파일 제외
        if not self._is_valid_name(filename):
            return False
        
        # Office 임시 파일 제외 (~$, ~WRL)
        for prefix in self.OFFICE_TEMP_PREFIXES:
            if filename.startswith(prefix):
                return False
        
        # 제외 파일 목록에 있으면 제외
        if filename in self.EXCLUDED_FILES:
            return False
        
        # 확장자 확인
        ext = Path(filepath).suffix.lower()
        
        # 제외 확장자면 제외
        if ext in self.EXCLUDED_EXTENSIONS:
            return False
        
        # 지원하는 확장자가 아니면 제외
        if ext not in self.SUPPORTED_TEXT_EXTENSIONS and ext not in self.SUPPORTED_DOC_EXTENSIONS:
            return False
        
        # 전체 경로가 제외 경로 접두사에 해당하면 제외
        for excluded_prefix in self.EXCLUDED_PATH_PREFIXES:
            if filepath.lower().startswith(excluded_prefix.lower()):
                return False
        
        # 사용자 정의 제외 패턴 체크
        for pattern in self.custom_excluded_patterns:
            # 간단한 패턴 매칭 (와일드카드 지원)
            if self._match_pattern(filepath, pattern):
                return False
        
        return True
    
    def _match_pattern(self, filepath: str, pattern: str) -> bool:
        """
        경로가 패턴과 매칭되는지 확인
        
        Args:
            filepath: 파일 경로
            pattern: 패턴 (와일드카드 * 지원)
        
        Returns:
            True면 매칭됨
        """
        import fnmatch
        
        # 대소문자 구분 없이 매칭
        return fnmatch.fnmatch(filepath.lower(), pattern.lower())
    
    def _is_valid_name(self, name: str) -> bool:
        """특수 문자로 시작하는 파일/폴더 필터링"""
        if not name:
            return False
        return name[0].isalnum() or ord(name[0]) >= 0xAC00  # 영문, 숫자, 한글
    
    
    def _extract_text(self, file_path: str) -> Optional[str]:
        """
        파일에서 텍스트 추출
        
        Args:
            file_path: 파일 경로
        
        Returns:
            추출된 텍스트 또는 None
        """
        ext = Path(file_path).suffix.lower()
        
        try:
            # 텍스트 파일
            if ext in self.SUPPORTED_TEXT_EXTENSIONS:
                return self._extract_text_file(file_path)
            
            # Word 문서
            elif ext == '.docx' and DOCX_AVAILABLE:
                return self._extract_docx(file_path)
            elif ext == '.doc' and WIN32COM_AVAILABLE:
                return self._extract_doc(file_path)
            
            # PowerPoint
            elif ext == '.pptx' and PPTX_AVAILABLE:
                return self._extract_pptx(file_path)
            elif ext == '.ppt' and WIN32COM_AVAILABLE:
                return self._extract_ppt(file_path)
            
            # Excel
            elif ext == '.xlsx' and XLSX_AVAILABLE:
                return self._extract_xlsx(file_path)
            elif ext == '.xls' and WIN32COM_AVAILABLE:
                return self._extract_xls(file_path)
            
            # PDF
            elif ext == '.pdf' and PDF_AVAILABLE:
                return self._extract_pdf(file_path)
            
            # HWP
            elif ext == '.hwp':
                return self._extract_hwp(file_path)
        
        except Exception as e:
            logger.error(f"텍스트 추출 오류 [{file_path}]: {e}")
        
        return None
    
    def _extract_text_file(self, file_path: str) -> Optional[str]:
        """
        텍스트 파일 읽기 (인코딩 자동 감지)
        UTF-8 → CP949 → chardet 순서로 시도
        """
        try:
            # 1차 시도: UTF-8
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content[:100000]  # 최대 100KB
            except (UnicodeDecodeError, UnicodeError):
                pass
            
            # 2차 시도: CP949 (한글 Windows 기본 인코딩)
            try:
                with open(file_path, 'r', encoding='cp949') as f:
                    content = f.read()
                    return content[:100000]
            except (UnicodeDecodeError, UnicodeError):
                pass
            
            # 3차 시도: chardet 자동 감지
            with open(file_path, 'rb') as f:
                raw_data = f.read(1000000)  # 최대 1MB 읽기
                result = chardet.detect(raw_data)
                encoding = result['encoding']
                
                if encoding:
                    try:
                        content = raw_data.decode(encoding, errors='ignore')
                        return content[:100000]
                    except Exception:
                        pass
            
            # 최종: ignore 모드로 UTF-8 시도
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return content[:100000]
        
        except Exception as e:
            logger.debug(f"텍스트 파일 읽기 오류 [{file_path}]: {e}")
            return None
    
    def _extract_docx(self, file_path: str) -> Optional[str]:
        """Word 문서에서 텍스트 추출"""
        try:
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            return text[:100000]
        except Exception as e:
            logger.debug(f"DOCX 추출 오류 [{file_path}]: {e}")
            return None
    
    def _extract_pptx(self, file_path: str) -> Optional[str]:
        """PowerPoint에서 텍스트 추출"""
        try:
            prs = Presentation(file_path)
            text_parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_parts.append(shape.text)
            return '\n'.join(text_parts)[:100000]
        except Exception as e:
            logger.debug(f"PPTX 추출 오류 [{file_path}]: {e}")
            return None
    
    def _extract_doc(self, file_path: str) -> Optional[str]:
        """
        구버전 Word 문서(.doc)에서 텍스트 추출
        pywin32 COM 객체 사용 (Windows 전용)
        """
        try:
            # COM 초기화 (백그라운드 스레드에서 필수)
            pythoncom.CoInitialize()
            
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = False
            
            doc = word.Documents.Open(file_path)
            text = doc.Content.Text
            doc.Close(False)
            word.Quit()
            
            pythoncom.CoUninitialize()
            
            return text[:100000]
        except Exception as e:
            logger.debug(f"DOC 추출 오류 [{file_path}]: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return None
    
    def _extract_ppt(self, file_path: str) -> Optional[str]:
        """
        구버전 PowerPoint(.ppt)에서 텍스트 추출
        pywin32 COM 객체 사용 (Windows 전용)
        """
        try:
            # COM 초기화
            pythoncom.CoInitialize()
            
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            ppt.Visible = False
            ppt.DisplayAlerts = False
            
            presentation = ppt.Presentations.Open(file_path, WithWindow=False)
            text_parts = []
            
            for slide in presentation.Slides:
                for shape in slide.Shapes:
                    if hasattr(shape, "TextFrame"):
                        if hasattr(shape.TextFrame, "TextRange"):
                            text_parts.append(shape.TextFrame.TextRange.Text)
            
            presentation.Close()
            ppt.Quit()
            
            pythoncom.CoUninitialize()
            
            return '\n'.join(text_parts)[:100000]
        except Exception as e:
            logger.debug(f"PPT 추출 오류 [{file_path}]: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return None
    
    def _extract_xlsx(self, file_path: str) -> Optional[str]:
        """
        Excel 문서(.xlsx)에서 텍스트 추출
        openpyxl 사용, data_only=True로 수식 제외 값만 추출
        """
        try:
            workbook = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            text_parts = []
            
            # 모든 시트 순회
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                
                # 모든 행 순회
                for row in sheet.iter_rows(values_only=True):
                    for cell_value in row:
                        if cell_value is not None:
                            text_parts.append(str(cell_value))
            
            workbook.close()
            return ' '.join(text_parts)[:100000]
        except Exception as e:
            logger.debug(f"XLSX 추출 오류 [{file_path}]: {e}")
            return None
    
    def _extract_xls(self, file_path: str) -> Optional[str]:
        """
        레거시 Excel(.xls)에서 텍스트 추출
        pywin32 COM 객체 사용 (Windows 전용)
        """
        try:
            # COM 초기화
            pythoncom.CoInitialize()
            
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            
            workbook = excel.Workbooks.Open(file_path)
            text_parts = []
            
            # 모든 시트 순회
            for sheet in workbook.Sheets:
                used_range = sheet.UsedRange
                for row in used_range.Rows:
                    for cell in row.Cells:
                        if cell.Value is not None:
                            text_parts.append(str(cell.Value))
            
            workbook.Close(False)
            excel.Quit()
            
            pythoncom.CoUninitialize()
            
            return ' '.join(text_parts)[:100000]
        except Exception as e:
            logger.debug(f"XLS 추출 오류 [{file_path}]: {e}")
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            return None
    
    def _extract_pdf(self, file_path: str) -> Optional[str]:
        """
        PDF에서 텍스트 추출
        PyMuPDF (fitz) 사용 - 속도가 월등히 빠름
        """
        try:
            doc = fitz.open(file_path)
            text_parts = []
            
            # 최대 100페이지까지만
            for page_num in range(min(len(doc), 100)):
                page = doc[page_num]
                text_parts.append(page.get_text())
            
            doc.close()
            return '\n'.join(text_parts)[:100000]
        except Exception as e:
            logger.debug(f"PDF 추출 오류 [{file_path}]: {e}")
            return None
    
    def _extract_hwp(self, file_path: str) -> Optional[str]:
        """
        HWP 파일에서 텍스트 추출
        1차: pywin32 COM 객체 시도
        2차: olefile 라이브러리 시도
        """
        # 1차 시도: COM 객체 (가장 정확)
        if WIN32COM_AVAILABLE:
            try:
                pythoncom.CoInitialize()
                
                hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
                hwp.RegisterModule("FilePathCheckDLL", "SecurityModule")
                hwp.Open(file_path)
                
                hwp.InitScan()
                text_parts = []
                
                while True:
                    text = hwp.GetText()
                    if not text:
                        break
                    text_parts.append(text)
                
                hwp.ReleaseScan()
                hwp.Quit()
                
                pythoncom.CoUninitialize()
                
                return ''.join(text_parts)[:100000]
            except Exception as e:
                logger.debug(f"HWP COM 추출 오류 [{file_path}]: {e}")
                try:
                    pythoncom.CoUninitialize()
                except:
                    pass
        
        # 2차 시도: olefile (제한적)
        if OLEFILE_AVAILABLE:
            try:
                ole = olefile.OleFileIO(file_path)
                if ole.exists('PrvText'):
                    stream = ole.openstream('PrvText')
                    data = stream.read()
                    # HWP 텍스트는 UTF-16LE 인코딩
                    text = data.decode('utf-16le', errors='ignore')
                    ole.close()
                    return text[:100000]
                ole.close()
            except Exception as e:
                logger.debug(f"HWP olefile 추출 오류 [{file_path}]: {e}")
        
        logger.debug(f"HWP 파일 추출 실패 [{file_path}]: 지원 라이브러리 없음")
        return None
    
    def get_stats(self) -> dict:
        """인덱싱 통계 반환"""
        return self.stats.copy()
    
    def start_retry_worker(self):
        """
        재시도 워커 시작 (백그라운드 스레드)
        
        5-10분마다 Skip된 파일을 재시도하여 인덱싱
        """
        if self.retry_thread and self.retry_thread.is_alive():
            logger.warning("재시도 워커가 이미 실행 중입니다.")
            return
        
        self.retry_stop_flag.clear()
        self.retry_thread = threading.Thread(
            target=self._retry_worker,
            name="RetryWorker",
            daemon=True
        )
        self.retry_thread.start()
        logger.info(f"재시도 워커 시작됨 (간격: {self.retry_interval}초)")
    
    def _retry_worker(self):
        """
        재시도 워커 스레드
        
        주기적으로 Skip된 파일을 재시도하여 인덱싱
        """
        logger.info("재시도 워커 동작 시작")
        
        while not self.retry_stop_flag.is_set():
            # 대기 (5분 = 300초, 인터럽트 가능하도록 1초씩 체크)
            for _ in range(self.retry_interval):
                if self.retry_stop_flag.is_set():
                    break
                time.sleep(1)
            
            if self.retry_stop_flag.is_set():
                break
            
            # Skip된 파일 재시도
            with self.skipped_files_lock:
                if not self.skipped_files:
                    logger.info("재시도할 파일이 없습니다. 워커 종료.")
                    break
                
                files_to_retry = list(self.skipped_files.keys())
            
            logger.info(f"Skip된 파일 재시도 시작: {len(files_to_retry)}개")
            
            retry_success = 0
            retry_failed = 0
            
            for file_path in files_to_retry:
                if self.retry_stop_flag.is_set():
                    break
                
                try:
                    # 파일이 존재하는지 확인
                    if not os.path.exists(file_path):
                        with self.skipped_files_lock:
                            if file_path in self.skipped_files:
                                del self.skipped_files[file_path]
                        logger.debug(f"파일 삭제됨, 재시도 목록에서 제거: {file_path}")
                        continue
                    
                    # 파일 크기 재확인
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > MAX_FILE_SIZE:
                            with self.skipped_files_lock:
                                if file_path in self.skipped_files:
                                    del self.skipped_files[file_path]
                            logger.debug(f"파일 크기 초과, 재시도 중단: {file_path}")
                            continue
                    except Exception:
                        pass
                    
                    # 텍스트 추출 재시도
                    content = self._extract_text_safe(file_path)
                    
                    if content:
                        # 성공! DB에 저장
                        current_mtime = os.path.getmtime(file_path)
                        token_count = self._count_tokens(content)
                        
                        # 이미 DB에 있는지 확인
                        indexed_mtime = self.db.get_file_mtime(file_path)
                        
                        try:
                            if indexed_mtime is not None:
                                # 업데이트
                                self.db.update_file(file_path, content, current_mtime)
                            else:
                                # 새로 삽입
                                self.db.insert_file(file_path, content, current_mtime)
                            
                            # 재시도 목록에서 제거
                            with self.skipped_files_lock:
                                if file_path in self.skipped_files:
                                    retry_info = self.skipped_files[file_path]
                                    del self.skipped_files[file_path]
                                    logger.info(f"재시도 성공 [{file_path}] - 이전 사유: {retry_info['reason']}")
                            
                            retry_success += 1
                            
                            # UI 로그 콜백 및 메모리에 로그 추가 - DB 저장 완료 상태
                            filename = os.path.basename(file_path)
                            db_status = "✓ DB 저장 완료 (재시도)"
                            detail = f'{len(content):,}자 / {token_count:,}토큰 | {db_status}'
                            
                            self._add_log_to_memory('Retry Success', filename, detail)
                            
                            if self.log_callback:
                                self.log_callback('Retry Success', filename, detail)
                        
                        except Exception as e:
                            logger.error(f"재시도 DB 저장 오류 [{file_path}]: {e}")
                            retry_failed += 1
                    
                    else:
                        # 여전히 실패
                        with self.skipped_files_lock:
                            if file_path in self.skipped_files:
                                self.skipped_files[file_path]['retry_count'] += 1
                                retry_count = self.skipped_files[file_path]['retry_count']
                                
                                # 5회 재시도 실패 시 포기
                                if retry_count >= 5:
                                    reason = self.skipped_files[file_path]['reason']
                                    del self.skipped_files[file_path]
                                    logger.warning(f"재시도 5회 실패, 포기: {file_path} - {reason}")
                                else:
                                    logger.debug(f"재시도 실패 ({retry_count}/5): {file_path}")
                        
                        retry_failed += 1
                
                except Exception as e:
                    logger.error(f"재시도 중 오류 [{file_path}]: {e}")
                    retry_failed += 1
            
            logger.info(f"재시도 완료: 성공 {retry_success}개, 실패 {retry_failed}개")
        
        logger.info("재시도 워커 종료")
    
    def get_skipped_files_count(self) -> int:
        """현재 재시도 대기 중인 파일 수 반환"""
        with self.skipped_files_lock:
            return len(self.skipped_files)


# 테스트 코드
if __name__ == "__main__":
    # 데이터베이스 초기화
    db = DatabaseManager("test_index.db")
    
    # 인덱서 생성
    indexer = FileIndexer(db)
    
    # 진행 상황 콜백
    def progress(current, total, path):
        print(f"[{current}/{total}] {path}")
    
    # 인덱싱 시작
    test_path = os.path.expanduser("~\\Desktop")
    print(f"테스트 인덱싱: {test_path}")
    indexer.start_indexing([test_path], progress)
    
    # 완료 대기
    while indexer.is_running:
        time.sleep(1)
    
    # 통계 출력
    stats = indexer.get_stats()
    print(f"\n=== 인덱싱 통계 ===")
    print(f"총 파일: {stats['total_files']}")
    print(f"인덱싱됨: {stats['indexed_files']}")
    print(f"스킵됨: {stats['skipped_files']}")
    print(f"오류: {stats['error_files']}")
    
    # 검색 테스트
    results = db.search("test")
    print(f"\n검색 결과: {len(results)}개")
    
    # 정리
    db.close()
    os.remove("test_index.db")
    print("\n테스트 완료")

