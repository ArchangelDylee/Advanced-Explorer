# -*- coding: utf-8 -*-
"""
검색 엔진 - 고속 전문 검색 및 결과 포맷팅
"""

import os
from typing import List, Dict, Optional
import logging
from database import DatabaseManager
import sys
import io
from datetime import datetime

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
log_file = os.path.join(LOG_DIR, 'search.log')
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


class SearchEngine:
    """검색 엔진 클래스"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        검색 엔진 초기화
        
        Args:
            db_manager: 데이터베이스 매니저 인스턴스
        """
        self.db = db_manager
    
    def search_combined(self, query: str, search_path: str = None, 
                       max_results: int = 100, include_content: bool = True) -> List[Dict]:
        """
        통합 검색: 파일명 + 내용 검색
        
        1. 파일 시스템에서 파일명 검색 (재귀적)
        2. DB에서 내용 검색 (include_content=True인 경우만)
        3. 결과 통합 (중복 제거, DB 우선)
        
        Args:
            query: 검색 쿼리
            search_path: 검색할 경로 (None이면 전체)
            max_results: 최대 결과 개수
            include_content: 내용 검색 포함 여부 (기본값: True)
        
        Returns:
            통합 검색 결과
        """
        if not query or not query.strip():
            return []
        
        try:
            results = {}
            
            # 1. 파일명 검색 (파일 시스템)
            if search_path:
                filename_results = self._search_filesystem(query, search_path)
                for result in filename_results:
                    file_path = result['path']
                    
                    # DB에 해당 파일이 있는지 확인 (경로 정규화)
                    is_indexed = self.db.is_file_indexed(file_path)
                    
                    results[file_path] = {
                        **result,
                        'source': 'filesystem',
                        'indexed': is_indexed
                    }
            
            # 2. 내용 검색 (DB) - include_content=True인 경우만
            if include_content:
                content_results = self.search(query, max_results, include_content=True)
            else:
                content_results = []
            
            for result in content_results:
                path = result['path']
                
                # search_path가 지정된 경우 해당 경로의 파일만 포함
                if search_path and not path.lower().startswith(search_path.lower()):
                    continue
                
                if path in results:
                    # 중복: 파일명과 내용 모두에 매칭 (both)
                    results[path] = {
                        **result,
                        'source': 'both',  # 파일명 + 내용 모두 매칭
                        'indexed': True
                    }
                else:
                    # 내용만 매칭
                    results[path] = {
                        **result,
                        'source': 'database',  # 내용만 매칭
                        'indexed': True
                    }
            
            # 3. 결과 정렬 (DB 우선, rank 순)
            # FTS5 rank: 낮을수록 관련도 높음 (음수 값)
            # 파일시스템 rank: 높을수록 우선순위 높음 (1.0=파일, 0.5=폴더)
            sorted_results = sorted(
                results.values(),
                key=lambda x: (
                    0 if x['indexed'] else 1,  # indexed 우선 (DB 결과 먼저)
                    x.get('rank', 999),  # rank 오름차순 (낮을수록 우선)
                    x.get('name', '').lower()  # 이름순 (동일 rank인 경우)
                )
            )
            
            return sorted_results[:max_results]
        
        except Exception as e:
            logger.error(f"통합 검색 오류: {e}")
            return []
    
    def _search_filesystem(self, query: str, root_path: str) -> List[Dict]:
        """
        파일 시스템에서 파일명 검색 (재귀적)
        
        검색 타입:
        1. 단일 단어: "학교" → 학교를 포함하는 파일/폴더
        2. 복합 단어: "학교 경찰" → 학교 AND 경찰 모두 포함
        3. 따옴표 문장: '"학교 경찰"' → 정확히 "학교 경찰" 포함
        
        Args:
            query: 검색 쿼리
            root_path: 검색 루트 경로
        
        Returns:
            파일명 검색 결과
        """
        results = []
        
        # 검색 타입 파악
        is_exact_match = query.startswith('"') and query.endswith('"')
        
        if is_exact_match:
            # 따옴표 제거
            search_term = query.strip('"').lower()
            match_type = "정확한 문장"
        else:
            # 공백으로 분리 (AND 조건)
            search_terms = [term.lower() for term in query.split() if term.strip()]
            match_type = "단어 일치" if len(search_terms) == 1 else f"복합 검색 ({len(search_terms)}개 단어 모두 포함)"
        
        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # 특수 문자로 시작하는 디렉토리 제외
                dirnames[:] = [d for d in dirnames if d[0].isalnum() or ord(d[0]) >= 0xAC00]
                
                # 폴더명도 검색 대상에 포함
                for dirname in dirnames:
                    name_lower = dirname.lower()
                    matched = False
                    
                    if is_exact_match:
                        # 정확한 문장 일치
                        matched = search_term in name_lower
                    else:
                        # 적어도 하나의 검색어 포함 (OR 조건)
                        matched = any(term in name_lower for term in search_terms)
                    
                    if matched:
                        dir_path = os.path.join(dirpath, dirname)
                        try:
                            stat = os.stat(dir_path)
                            mtime_iso = datetime.fromtimestamp(stat.st_mtime).isoformat()
                            results.append({
                                'path': dir_path,
                                'name': dirname,
                                'directory': dirpath,
                                'extension': 'folder',
                                'size': 0,
                                'mtime': mtime_iso,
                                'rank': 0.5,  # 폴더는 약간 낮은 우선순위
                                'preview': f'폴더명 {match_type}: {dirname}'
                            })
                        except Exception:
                            pass
                
                # 파일명 검색
                for filename in filenames:
                    name_lower = filename.lower()
                    matched = False
                    
                    if is_exact_match:
                        # 정확한 문장 일치
                        matched = search_term in name_lower
                    else:
                        # 적어도 하나의 검색어 포함 (OR 조건)
                        matched = any(term in name_lower for term in search_terms)
                    
                    if matched:
                        file_path = os.path.join(dirpath, filename)
                        
                        try:
                            stat = os.stat(file_path)
                            mtime_iso = datetime.fromtimestamp(stat.st_mtime).isoformat()
                            results.append({
                                'path': file_path,
                                'name': filename,
                                'directory': dirpath,
                                'extension': os.path.splitext(filename)[1],
                                'size': stat.st_size,
                                'mtime': mtime_iso,
                                'rank': 1.0,  # 파일이 폴더보다 높은 우선순위
                                'preview': f'파일명 {match_type}: {filename}'
                            })
                        except Exception:
                            pass
                
                # 최대 1000개까지만
                if len(results) >= 1000:
                    break
        
        except Exception as e:
            logger.error(f"파일 시스템 검색 오류 [{root_path}]: {e}")
        
        return results
    
    def parse_search_query(self, query: str) -> Dict:
        """
        검색어 파싱

        규칙:
        - "문자열" → 정확 일치
        - 단어1 단어2 → OR 조건 (적어도 하나 포함)
        - 특수문자 이스케이프

        Args:
            query: 원본 검색어

        Returns:
            파싱된 검색 정보
        """
        import re

        parsed = {
            'original': query,
            'exact_match': False,
            'terms': [],
            'escaped_query': ''
        }

        # 정확 일치 검색 ("문자열")
        if query.startswith('"') and query.endswith('"'):
            parsed['exact_match'] = True
            parsed['terms'] = [query.strip('"')]
            parsed['escaped_query'] = query.strip('"')
        else:
            # OR 조건 (공백으로 분리)
            terms = query.split()
            parsed['terms'] = terms

            # FTS5 특수문자 이스케이프
            escaped_terms = []
            for term in terms:
                # FTS5 특수문자: - ( ) [ ] " *
                escaped = re.sub(r'([-\(\)\[\]"\*])', r'\\\1', term)
                escaped_terms.append(escaped)

            # OR 조건으로 연결
            parsed['escaped_query'] = ' OR '.join(escaped_terms)

        return parsed
    
    def search(self, query: str, max_results: int = 100, 
               include_content: bool = True) -> List[Dict]:
        """
        전문 검색 실행
        
        Args:
            query: 검색 쿼리
            max_results: 최대 결과 개수
            include_content: 내용 미리보기 포함 여부
        
        Returns:
            검색 결과 리스트
        """
        if not query or not query.strip():
            return []
        
        try:
            # 검색 히스토리에 추가
            self.db.add_search_history(query.strip())
            
            # DB 검색
            results = self.db.search(query, limit=max_results)
            
            # 결과 포맷팅
            formatted_results = []
            for result in results:
                formatted = self._format_result(result, query, include_content)
                if formatted:
                    formatted_results.append(formatted)
            
            logger.info(f"검색 완료: '{query}' - {len(formatted_results)}개 결과")
            return formatted_results
        
        except Exception as e:
            logger.error(f"검색 오류: {e}")
            return []
    
    def _format_result(self, result: Dict, query: str, 
                       include_content: bool) -> Optional[Dict]:
        """
        검색 결과 포맷팅
        
        Args:
            result: DB 검색 결과
            query: 검색 쿼리
            include_content: 내용 포함 여부
        
        Returns:
            포맷팅된 결과
        """
        try:
            path = result['path']
            
            # 파일 존재 여부 확인
            if not os.path.exists(path):
                return None
            
            # 기본 정보
            # mtime을 ISO 8601 형식으로 변환
            mtime_raw = result.get('mtime', '')
            mtime_iso = ''
            if mtime_raw:
                try:
                    mtime_iso = datetime.fromtimestamp(float(mtime_raw)).isoformat()
                except (ValueError, TypeError):
                    mtime_iso = ''
            
            formatted = {
                'path': path,
                'name': os.path.basename(path),
                'directory': os.path.dirname(path),
                'extension': os.path.splitext(path)[1],
                'size': os.path.getsize(path),
                'mtime': mtime_iso,
                'rank': result.get('rank', 0)
            }
            
            # 내용 미리보기
            if include_content:
                content = result.get('content', '')
                formatted['preview'] = self._create_preview(content, query)
                formatted['highlight'] = self._highlight_query(content, query)
            
            return formatted
        
        except Exception as e:
            logger.error(f"결과 포맷팅 오류: {e}")
            return None
    
    def _create_preview(self, content: str, query: str, 
                        max_length: int = 200) -> str:
        """
        검색어 주변 텍스트 미리보기 생성
        
        Args:
            content: 전체 내용
            query: 검색 쿼리
            max_length: 최대 길이
        
        Returns:
            미리보기 텍스트
        """
        if not content:
            return ""
        
        # 검색어 위치 찾기
        query_lower = query.lower()
        content_lower = content.lower()
        pos = content_lower.find(query_lower)
        
        if pos == -1:
            # 검색어가 없으면 앞부분 반환
            return content[:max_length] + ("..." if len(content) > max_length else "")
        
        # 검색어 주변 텍스트 추출
        start = max(0, pos - max_length // 2)
        end = min(len(content), pos + len(query) + max_length // 2)
        
        preview = content[start:end]
        
        # 앞뒤 생략 표시
        if start > 0:
            preview = "..." + preview
        if end < len(content):
            preview = preview + "..."
        
        return preview
    
    def _highlight_query(self, content: str, query: str, 
                         max_highlights: int = 3) -> List[Dict]:
        """
        검색어 하이라이트 위치 정보
        
        Args:
            content: 전체 내용
            query: 검색 쿼리
            max_highlights: 최대 하이라이트 개수
        
        Returns:
            하이라이트 정보 리스트 [{'start': int, 'end': int, 'text': str}, ...]
        """
        highlights = []
        query_lower = query.lower()
        content_lower = content.lower()
        
        start = 0
        for _ in range(max_highlights):
            pos = content_lower.find(query_lower, start)
            if pos == -1:
                break
            
            highlights.append({
                'start': pos,
                'end': pos + len(query),
                'text': content[pos:pos + len(query)]
            })
            start = pos + len(query)
        
        return highlights
    
    def search_by_extension(self, extension: str, 
                           max_results: int = 100) -> List[Dict]:
        """
        파일 확장자로 검색
        
        Args:
            extension: 파일 확장자 (예: '.txt', '.pdf')
            max_results: 최대 결과 개수
        
        Returns:
            검색 결과 리스트
        """
        # FTS5에서 path를 검색할 수 없으므로 전체 검색 후 필터링
        # 실제 구현에서는 별도 테이블이나 메타데이터 사용 권장
        logger.warning("확장자 검색은 현재 구현되지 않았습니다.")
        return []
    
    def get_statistics(self) -> Dict:
        """
        검색 엔진 통계
        
        Returns:
            통계 정보
        """
        return {
            'total_indexed_files': self.db.get_indexed_files_count(),
            'database_size': os.path.getsize(self.db.db_path) if os.path.exists(self.db.db_path) else 0
        }


# 테스트 코드
if __name__ == "__main__":
    # 데이터베이스 초기화
    db = DatabaseManager("test_index.db")
    
    # 테스트 데이터
    db.insert_file(
        "C:\\test\\document.txt",
        "이것은 Python 인덱싱 엔진 테스트 문서입니다. 전문 검색 기능을 테스트합니다.",
        1234567890.0
    )
    db.insert_file(
        "C:\\test\\code.py",
        "def main():\n    print('Hello World')\n    # Python 코드 예제",
        1234567891.0
    )
    
    # 검색 엔진 생성
    search_engine = SearchEngine(db)
    
    # 검색 테스트
    print("=== 검색 테스트: 'Python' ===")
    results = search_engine.search("Python")
    for i, result in enumerate(results, 1):
        print(f"\n결과 {i}:")
        print(f"  파일: {result['name']}")
        print(f"  경로: {result['path']}")
        print(f"  미리보기: {result['preview']}")
        print(f"  하이라이트: {result['highlight']}")
    
    # 통계
    print("\n=== 통계 ===")
    stats = search_engine.get_statistics()
    print(f"인덱스된 파일: {stats['total_indexed_files']}")
    print(f"DB 크기: {stats['database_size']} bytes")
    
    # 정리
    db.close()
    os.remove("test_index.db")
    print("\n테스트 완료")

