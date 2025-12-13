# -*- coding: utf-8 -*-
"""
API 서버 - Electron과 Python 백엔드 통신
Flask 기반 REST API
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import threading
import sys
import os
import atexit
import io
import json

# ========================================
# UTF-8 전역 설정 (최우선 실행)
# ========================================
# Windows 콘솔 코드 페이지를 UTF-8로 설정 (Python 실행 전 필수)
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)  # UTF-8 입력
        kernel32.SetConsoleOutputCP(65001)  # UTF-8 출력
    except Exception:
        pass

# Python 표준 출력/에러 스트림을 UTF-8로 강제 설정
# Windows에서 chcp 65001 효과
import locale
try:
    locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

# stdout/stderr를 UTF-8로 재설정 (기존 버퍼 저장)
_original_stdout = sys.stdout
_original_stderr = sys.stderr

try:
    if hasattr(sys.stdout, 'buffer') and sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    sys.stdout = _original_stdout

try:
    if hasattr(sys.stderr, 'buffer') and sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    sys.stderr = _original_stderr

from database import DatabaseManager
from indexer import FileIndexer
from search import SearchEngine
from summarizer import ContentSummarizer
from file_watcher import FileSystemWatcher

# 로그 디렉토리 생성
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 로깅 설정 (콘솔 + 파일, UTF-8 인코딩 강제)
log_file = os.path.join(LOG_DIR, 'server.log')
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 콘솔 출력 (UTF-8)
        logging.FileHandler(log_file, encoding='utf-8', mode='a')  # 파일 출력 (UTF-8)
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

# Flask 앱 생성
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # UTF-8 인코딩 강제 (한글 등 유니코드 문자 정상 표시)
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
CORS(app)  # CORS 허용

# 전역 객체
db_manager: DatabaseManager = None
indexer: FileIndexer = None
search_engine: SearchEngine = None
summarizer: ContentSummarizer = None
file_watcher: FileSystemWatcher = None


def initialize():
    """백엔드 초기화 (설정 파일 기반)"""
    global db_manager, indexer, search_engine, summarizer, file_watcher
    
    logger.info("========================================")
    logger.info("Python 백엔드 초기화 (가상환경)")
    logger.info("========================================")
    logger.info(f"Python 실행 파일: {sys.executable}")
    logger.info(f"Python 버전: {sys.version}")
    logger.info(f"작업 디렉토리: {os.getcwd()}")
    
    # config.json 읽기 (환경 변수가 없을 때)
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"config.json 읽기 실패: {e}")
    
    # 환경 변수에서 설정 읽기 (config.json에서 전달된 값, 없으면 config.json에서 직접 읽기)
    enable_activity_monitor = os.getenv('ENABLE_ACTIVITY_MONITOR', 
                                       str(config.get('indexing', {}).get('enableActivityMonitor', True))).lower() == 'true'
    logger.info(f"  - 사용자 활동 모니터링: {enable_activity_monitor}")
    
    idle_threshold = 2.0
    if enable_activity_monitor:
        idle_threshold = float(os.getenv('IDLE_THRESHOLD', 
                                        str(config.get('indexing', {}).get('idleThreshold', 2.0))))
        logger.info(f"  - 유휴 대기 시간: {idle_threshold}초")
    
    logger.info("========================================")
    
    # 데이터베이스 경로
    db_path = os.path.join(os.path.dirname(__file__), "file_index.db")
    
    # 데이터베이스 초기화
    db_manager = DatabaseManager(db_path)
    logger.info(f"데이터베이스 초기화: {db_path}")
    
    # 인덱서 초기화 (설정 기반)
    indexer = FileIndexer(db_manager, enable_activity_monitor=enable_activity_monitor)
    logger.info(f"파일 인덱서 초기화 완료 (활동 모니터: {enable_activity_monitor})")
    
    # 검색 엔진 초기화
    search_engine = SearchEngine(db_manager)
    logger.info("검색 엔진 초기화 완료")
    
    # 요약 엔진 초기화
    summarizer = ContentSummarizer()
    logger.info("요약 엔진 초기화 완료")
    
    # 파일 시스템 감시 초기화 및 시작
    file_watcher = FileSystemWatcher(db_manager, indexer)
    file_watcher.start()
    logger.info("파일 시스템 감시 시작 완료")
    
    # 종료 시 정리 함수 등록
    atexit.register(cleanup)


def cleanup():
    """백엔드 종료 시 정리 - 쓰레드 안전 종료 및 파일 Lock 해제"""
    global indexer, db_manager, file_watcher
    
    logger.info("=" * 60)
    logger.info("백엔드 종료 프로세스 시작...")
    logger.info("=" * 60)
    
    try:
        # 1. 파일 시스템 감시 중지
        if file_watcher:
            logger.info("파일 시스템 감시 중지 중...")
            file_watcher.stop()
            logger.info("✓ 파일 시스템 감시 중지 완료")
        
        # 2. 인덱서 리소스 정리
        if indexer:
            logger.info("인덱서 정리 중...")
            indexer.cleanup()
            logger.info("✓ 인덱서 정리 완료")
        
        # 3. 데이터베이스 연결 종료 및 Lock 해제
        if db_manager:
            logger.info("데이터베이스 연결 종료 중...")
            try:
                # DB에 보류 중인 변경사항 커밋
                if db_manager.conn:
                    db_manager.conn.commit()
                    logger.info("✓ DB 커밋 완료")
            except Exception as e:
                logger.warning(f"DB 커밋 오류 (무시됨): {e}")
            
            db_manager.close()
            logger.info("✓ 데이터베이스 연결 종료됨")
        
        # 4. 로깅 핸들러 종료 및 Lock 해제
        logger.info("로그 파일 핸들러 종료 중...")
        try:
            # 모든 로깅 핸들러 flush 및 close
            for handler in logging.root.handlers[:]:  # 복사본으로 순회
                try:
                    handler.flush()
                    handler.close()
                    logging.root.removeHandler(handler)
                except Exception as e:
                    print(f"핸들러 종료 오류: {e}", file=sys.stderr)
            logger.info("✓ 로그 파일 핸들러 종료됨")
        except Exception as e:
            print(f"로그 핸들러 종료 중 오류: {e}", file=sys.stderr)
        
        print("=" * 60)
        print("✓ 백엔드 정리 완료 - 모든 파일 Lock 해제됨")
        print("=" * 60)
    
    except Exception as e:
        print(f"정리 중 오류 발생: {e}", file=sys.stderr)
        import traceback
        print(traceback.format_exc(), file=sys.stderr)


# ============== API 엔드포인트 ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    서버 상태 확인 (절전 모드 복귀 시 사용)
    - Python 백엔드 상태
    - 데이터베이스 연결 상태
    - 인덱서 상태
    - 검색 엔진 상태
    """
    health_status = {
        'status': 'ok',
        'message': 'Python backend is running',
        'components': {}
    }
    
    try:
        # 1. 데이터베이스 연결 확인
        try:
            if db_manager and db_manager.conn:
                # 간단한 쿼리로 DB 연결 확인
                cursor = db_manager.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM files_fts WHERE deleted = '0'")
                total_files = cursor.fetchone()[0]
                health_status['components']['database'] = {
                    'status': 'ok',
                    'connected': True,
                    'total_files': total_files
                }
            else:
                health_status['components']['database'] = {
                    'status': 'error',
                    'connected': False,
                    'message': 'Database manager not initialized'
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['components']['database'] = {
                'status': 'error',
                'connected': False,
                'message': str(e)
            }
            health_status['status'] = 'degraded'
        
        # 2. 인덱서 상태 확인
        try:
            if indexer:
                health_status['components']['indexer'] = {
                    'status': 'ok',
                    'is_running': indexer.is_running,
                    'initialized': True
                }
            else:
                health_status['components']['indexer'] = {
                    'status': 'error',
                    'initialized': False
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['components']['indexer'] = {
                'status': 'error',
                'message': str(e)
            }
            health_status['status'] = 'degraded'
        
        # 3. 검색 엔진 상태 확인
        try:
            if search_engine:
                health_status['components']['search_engine'] = {
                    'status': 'ok',
                    'initialized': True
                }
            else:
                health_status['components']['search_engine'] = {
                    'status': 'error',
                    'initialized': False
                }
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['components']['search_engine'] = {
                'status': 'error',
                'message': str(e)
            }
            health_status['status'] = 'degraded'
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Health check failed: {str(e)}'
        }), 500


@app.route('/api/indexing/start', methods=['POST'])
def start_indexing():
    """인덱싱 시작"""
    try:
        data = request.json
        paths = data.get('paths', [])
        
        if not paths:
            return jsonify({'error': 'No paths provided'}), 400
        
        # 진행 상황 콜백 (실제로는 WebSocket이나 SSE 사용 권장)
        def progress_callback(current, total, path):
            logger.info(f"인덱싱 진행: [{current}/{total}] {path}")
        
        success = indexer.start_indexing(paths, progress_callback)

        if success:
            # 인덱싱 시작 시 자동으로 파일 감시 추가
            for path in paths:
                if os.path.isdir(path):
                    file_watcher.add_watch_path(path)
                    logger.info(f"📡 파일 감시 추가: {path}")
            
            return jsonify({
                'status': 'started',
                'message': '인덱싱이 시작되었습니다.'
            })
        else:
            return jsonify({
                'status': 'already_running',
                'message': '인덱싱이 이미 실행 중입니다.'
            })
    
    except Exception as e:
        logger.error(f"인덱싱 시작 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/stop', methods=['POST'])
def stop_indexing():
    """인덱싱 중지"""
    try:
        indexer.stop_indexing()
        return jsonify({
            'status': 'stopped',
            'message': '인덱싱 중지 요청이 전송되었습니다.'
        })
    except Exception as e:
        logger.error(f"인덱싱 중지 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/single-file', methods=['POST'])
def index_single_file():
    """
    단일 파일 인덱싱 (우클릭 메뉴용)
    
    Request Body:
        {
            "file_path": "C:\\path\\to\\file.txt"
        }
    
    Returns:
        {
            "success": true,
            "message": "인덱싱 완료 (1234자, 567토큰)",
            "indexed": true,
            "char_count": 1234,
            "token_count": 567
        }
    """
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                'success': False,
                'message': '파일 경로가 필요합니다'
            }), 400
        
        # 단일 파일 인덱싱 실행
        result = indexer.index_single_file(file_path)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"단일 파일 인덱싱 API 오류: {e}")
        return jsonify({
            'success': False,
            'message': f'서버 오류: {str(e)}'
        }), 500


@app.route('/api/indexing/status', methods=['GET'])
def indexing_status():
    """인덱싱 상태 조회"""
    try:
        stats = indexer.get_stats()
        skipped_count = indexer.get_skipped_files_count()
        retry_running = indexer.retry_thread and indexer.retry_thread.is_alive()
        
        return jsonify({
            'is_running': indexer.is_running,
            'stats': stats,
            'retry_worker': {
                'is_running': retry_running,
                'pending_files': skipped_count,
                'interval_seconds': indexer.retry_interval
            }
        })
    except Exception as e:
        logger.error(f"상태 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/logs', methods=['GET'])
def indexing_logs():
    """
    인덱싱 로그 조회
    
    Query Parameters:
        count: 조회할 로그 수 (기본: 100)
    """
    try:
        count = request.args.get('count', 100, type=int)
        logs = indexer.get_recent_logs(count)
        
        return jsonify({
            'count': len(logs),
            'logs': logs
        })
    except Exception as e:
        logger.error(f"로그 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/logs/clear', methods=['POST'])
def clear_indexing_logs():
    """인덱싱 로그 초기화"""
    try:
        indexer.clear_logs()
        return jsonify({
            'status': 'success',
            'message': '로그가 초기화되었습니다.'
        })
    except Exception as e:
        logger.error(f"로그 초기화 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/database', methods=['GET'])
def get_indexed_database():
    """
    인덱싱 DB 전체 조회 (SELECT * FROM files_fts)
    
    Query Parameters:
        limit: 조회할 최대 개수 (기본: 1000)
        offset: 시작 위치 (기본: 0)
    """
    try:
        limit = request.args.get('limit', 1000, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # DB에서 전체 인덱싱 데이터 조회
        files = db_manager.get_all_indexed_files(limit, offset)
        total_count = db_manager.get_indexed_files_count()
        
        return jsonify({
            'total_count': total_count,
            'count': len(files),
            'limit': limit,
            'offset': offset,
            'files': files
        })
    except Exception as e:
        logger.error(f"DB 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/database/<path:file_path>', methods=['GET'])
def get_indexed_file_detail(file_path):
    """
    특정 파일의 상세 정보 조회
    
    Args:
        file_path: 파일 경로 (URL 디코딩됨)
    """
    try:
        # URL 디코딩 (Flask가 자동으로 하지만 한글 경로를 위해 명시적 처리)
        from urllib.parse import unquote
        decoded_path = unquote(file_path)
        
        logger.info(f"파일 상세 조회 요청: {decoded_path}")
        
        file_detail = db_manager.get_indexed_file_detail(decoded_path)
        
        if file_detail:
            logger.info(f"✓ 파일 발견: {decoded_path} (길이: {file_detail.get('content_length', 0)}자)")
            return jsonify(file_detail)
        else:
            logger.warning(f"✗ 파일 없음 (DB): {decoded_path}")
            
            # 디버깅: DB에 저장된 경로 샘플 확인
            all_paths = db_manager.get_all_indexed_paths()
            if all_paths:
                # 비슷한 경로 찾기
                import difflib
                similar = difflib.get_close_matches(decoded_path, all_paths, n=3, cutoff=0.6)
                if similar:
                    logger.info(f"유사한 경로들: {similar[:3]}")
            
            return jsonify({'error': 'File not found in index'}), 404
    except Exception as e:
        logger.error(f"파일 상세 조회 오류: {e}")
        logger.error(f"요청 경로: {file_path}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/check-files', methods=['POST'])
def check_files_indexed():
    """
    여러 파일의 인덱싱 여부 및 Skip 상태를 일괄 확인
    
    Request Body:
        {
            "paths": ["C:\\path\\to\\file1.txt", "C:\\path\\to\\file2.docx", ...]
        }
    
    Response:
        {
            "indexed": {
                "C:\\path\\to\\file1.txt": true,
                "C:\\path\\to\\file2.docx": false,
                ...
            },
            "skipped": {
                "C:\\path\\to\\file3.txt": "파일 손상 또는 암호화됨",
                ...
            }
        }
    """
    try:
        data = request.json
        paths = data.get('paths', [])
        
        if not paths:
            return jsonify({'indexed': {}, 'skipped': {}})
        
        # 각 파일의 인덱싱 여부 확인
        indexed_result = {}
        skipped_result = {}
        
        for path in paths:
            is_indexed = db_manager.is_file_indexed(path)
            indexed_result[path] = is_indexed
            
            # Skip 여부 확인
            with indexer.skipped_files_lock:
                if path in indexer.skipped_files:
                    skipped_result[path] = indexer.skipped_files[path].get('reason', 'Unknown')
        
        return jsonify({'indexed': indexed_result, 'skipped': skipped_result})
    except Exception as e:
        logger.error(f"파일 인덱싱 여부 확인 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search', methods=['POST'])
def search():
    """파일 검색 (내용만)"""
    try:
        data = request.json
        query = data.get('query', '')
        max_results = data.get('max_results', 100)
        include_content = data.get('include_content', True)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        results = search_engine.search(query, max_results, include_content)
        
        return jsonify({
            'query': query,
            'count': len(results),
            'results': results
        })
    
    except Exception as e:
        logger.error(f"검색 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/combined', methods=['POST'])
def search_combined():
    """통합 검색 (파일명 + 내용)"""
    try:
        import time as time_module
        start_time = time_module.time()
        
        data = request.json
        query = data.get('query', '')
        search_path = data.get('search_path', None)
        max_results = data.get('max_results', 100)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # 검색어 파싱
        parsed = search_engine.parse_search_query(query)
        
        # 통합 검색 실행
        results = search_engine.search_combined(
            parsed['escaped_query'], 
            search_path, 
            max_results
        )
        
        # 검색 시간 계산
        search_time = time_module.time() - start_time
        
        return jsonify({
            'query': query,
            'parsed': parsed,
            'count': len(results),
            'results': results,
            'search_time': round(search_time, 3)
        })
    
    except Exception as e:
        logger.error(f"통합 검색 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indexing/indexed-content', methods=['POST'])
def get_indexed_content():
    """인덱싱된 파일의 내용 조회"""
    try:
        data = request.json
        file_path = data.get('path', '')
        
        if not file_path:
            return jsonify({'error': 'Path is required'}), 400
        
        # DB에서 내용 조회
        results = db_manager.conn.execute(
            "SELECT content, mtime FROM files_fts WHERE path = ?",
            (file_path,)
        ).fetchone()
        
        if results:
            return jsonify({
                'indexed': True,
                'path': file_path,
                'content': results['content'],
                'mtime': results['mtime']
            })
        else:
            return jsonify({
                'indexed': False,
                'path': file_path,
                'message': '인덱싱되지 않은 파일입니다.'
            })
    
    except Exception as e:
        logger.error(f"인덱싱 내용 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def statistics():
    """통계 정보"""
    try:
        stats = search_engine.get_statistics()
        if stats is None:
            stats = {
                'total_files': 0,
                'total_size': 0,
                'file_types': {}
            }
        return jsonify(stats)
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        return jsonify({
            'total_files': 0,
            'total_size': 0,
            'file_types': {}
        }), 200  # 500 대신 200으로 반환하되 빈 통계


@app.route('/api/cleanup/deleted-files', methods=['POST'])
def cleanup_deleted_files():
    """
    오래된 삭제 마킹 파일 정리
    Body: {
        "days_old": 30  (선택, 기본: 30일)
    }
    """
    try:
        data = request.get_json() or {}
        days_old = data.get('days_old', 30)
        
        count = db_manager.cleanup_deleted_files(days_old)
        
        return jsonify({
            'status': 'success',
            'cleaned_count': count,
            'message': f'{count}개의 오래된 삭제 파일이 정리되었습니다.'
        })
    except Exception as e:
        logger.error(f"삭제 파일 정리 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/clear', methods=['POST'])
def clear_database():
    """데이터베이스 초기화"""
    try:
        db_manager.clear_index()
        return jsonify({
            'status': 'cleared',
            'message': '모든 인덱스가 삭제되었습니다.'
        })
    except Exception as e:
        logger.error(f"데이터베이스 초기화 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/optimize', methods=['POST'])
def optimize_database():
    """데이터베이스 최적화"""
    try:
        db_manager.optimize()
        return jsonify({
            'status': 'optimized',
            'message': '데이터베이스가 최적화되었습니다.'
        })
    except Exception as e:
        logger.error(f"데이터베이스 최적화 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/database/vacuum', methods=['POST'])
def vacuum_database():
    """데이터베이스 VACUUM (단편화 제거)"""
    try:
        db_manager.vacuum()
        return jsonify({
            'status': 'vacuumed',
            'message': '데이터베이스 단편화가 제거되었습니다.'
        })
    except Exception as e:
        logger.error(f"VACUUM 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-history', methods=['GET'])
def get_search_history():
    """검색 히스토리 조회"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = db_manager.get_search_history(limit)
        return jsonify({
            'count': len(history),
            'history': history
        })
    except Exception as e:
        logger.error(f"검색 히스토리 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-history', methods=['DELETE'])
def delete_search_history_item():
    """특정 검색어 삭제"""
    try:
        data = request.json
        keyword = data.get('keyword', '')
        
        if not keyword:
            return jsonify({'error': 'Keyword is required'}), 400
        
        db_manager.delete_search_history(keyword)
        return jsonify({
            'status': 'deleted',
            'message': f'검색어 "{keyword}"가 삭제되었습니다.'
        })
    except Exception as e:
        logger.error(f"검색 히스토리 삭제 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/search-history/clear', methods=['POST'])
def clear_search_history():
    """모든 검색 히스토리 삭제"""
    try:
        db_manager.clear_search_history()
        return jsonify({
            'status': 'cleared',
            'message': '모든 검색 히스토리가 삭제되었습니다.'
        })
    except Exception as e:
        logger.error(f"검색 히스토리 초기화 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/exclusion-patterns', methods=['GET'])
def get_exclusion_patterns():
    """사용자 정의 제외 패턴 조회"""
    try:
        patterns = indexer.get_exclusion_patterns()
        return jsonify({
            'count': len(patterns),
            'patterns': patterns
        })
    except Exception as e:
        logger.error(f"제외 패턴 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/exclusion-patterns', methods=['POST'])
def add_exclusion_pattern():
    """사용자 정의 제외 패턴 추가"""
    try:
        data = request.json
        pattern = data.get('pattern', '')
        
        if not pattern:
            return jsonify({'error': 'Pattern is required'}), 400
        
        indexer.add_exclusion_pattern(pattern)
        return jsonify({
            'status': 'added',
            'message': f'제외 패턴 "{pattern}"이 추가되었습니다.'
        })
    except Exception as e:
        logger.error(f"제외 패턴 추가 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/exclusion-patterns', methods=['DELETE'])
def remove_exclusion_pattern():
    """사용자 정의 제외 패턴 제거"""
    try:
        data = request.json
        pattern = data.get('pattern', '')
        
        if not pattern:
            return jsonify({'error': 'Pattern is required'}), 400
        
        indexer.remove_exclusion_pattern(pattern)
        return jsonify({
            'status': 'removed',
            'message': f'제외 패턴 "{pattern}"이 제거되었습니다.'
        })
    except Exception as e:
        logger.error(f"제외 패턴 제거 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/exclusion-patterns/clear', methods=['POST'])
def clear_exclusion_patterns():
    """모든 사용자 정의 제외 패턴 제거"""
    try:
        indexer.clear_exclusion_patterns()
        return jsonify({
            'status': 'cleared',
            'message': '모든 제외 패턴이 제거되었습니다.'
        })
    except Exception as e:
        logger.error(f"제외 패턴 초기화 오류: {e}")
        return jsonify({'error': str(e)}), 500


# ============== 자동 인덱싱 ==============

@app.route('/api/auto-indexing/start', methods=['POST'])
def start_auto_indexing():
    """
    자동 인덱싱 시작
    Body: {
        "paths": ["C:\\Users\\..."],
        "interval_minutes": 30  (선택, 기본: 30분)
    }
    """
    try:
        data = request.get_json()
        paths = data.get('paths', [])
        interval_minutes = data.get('interval_minutes', 30)
        
        if not paths:
            return jsonify({'error': '인덱싱할 경로를 지정해주세요.'}), 400
        
        indexer.start_auto_indexing(paths, interval_minutes)
        
        return jsonify({
            'status': 'started',
            'message': f'자동 인덱싱 시작 (주기: {interval_minutes}분)',
            'paths': paths
        })
    
    except Exception as e:
        logger.error(f"자동 인덱싱 시작 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auto-indexing/stop', methods=['POST'])
def stop_auto_indexing():
    """자동 인덱싱 중지"""
    try:
        indexer.stop_auto_indexing()
        
        return jsonify({
            'status': 'stopped',
            'message': '자동 인덱싱이 중지되었습니다.'
        })
    
    except Exception as e:
        logger.error(f"자동 인덱싱 중지 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auto-indexing/status', methods=['GET'])
def get_auto_indexing_status():
    """자동 인덱싱 상태 조회"""
    try:
        return jsonify({
            'is_enabled': indexer.is_auto_indexing_enabled,
            'interval_minutes': indexer.auto_indexing_interval / 60,
            'paths': indexer.auto_indexing_paths
        })
    
    except Exception as e:
        logger.error(f"자동 인덱싱 상태 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """
    서버 종료 엔드포인트
    
    앱 종료 시 Electron에서 호출하여 백그라운드 쓰레드를 안전하게 종료합니다.
    """
    try:
        logger.info("서버 종료 API 호출됨")
        
        # cleanup 함수 호출 (쓰레드 안전 종료)
        cleanup()
        
        # Flask 서버 종료 (werkzeug 사용 시)
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            # production 서버인 경우
            logger.info("Production 모드: 수동으로 서버를 종료해주세요.")
            return jsonify({
                'status': 'cleanup_done',
                'message': '백그라운드 쓰레드가 종료되었습니다. 서버는 수동으로 종료해주세요.'
            })
        
        func()
        return jsonify({
            'status': 'shutdown',
            'message': '서버가 종료되었습니다.'
        })
    
    except Exception as e:
        logger.error(f"서버 종료 오류: {e}")
        return jsonify({'error': str(e)}), 500


# ============== 요약 API ==============

@app.route('/api/summarize', methods=['POST'])
def summarize_content():
    """
    파일 내용 요약 (TextRank)
    
    Request Body:
        {
            "file_path": "C:\\path\\to\\file.pdf",  # 파일 경로
            "sentences_count": 5                     # 요약 문장 수 (옵션)
        }
    
    Returns:
        {
            "success": true,
            "method": "TextRank",
            "summary": "요약된 내용...",
            "original_length": 5000,
            "summary_length": 500,
            "compression_ratio": "10.0%"
        }
    """
    try:
        data = request.json
        
        if not data or 'file_path' not in data:
            return jsonify({'error': 'file_path가 필요합니다'}), 400
        
        file_path = data['file_path']
        
        # DB에서 인덱스된 내용 가져오기
        file_detail = db_manager.get_indexed_file_detail(file_path)
        
        if not file_detail:
            return jsonify({
                'success': False,
                'error': '파일이 인덱스되지 않았습니다'
            }), 404
        
        text = file_detail.get('content', '')
        
        if not text:
            return jsonify({
                'success': False,
                'error': '파일 내용이 비어있습니다'
            }), 400
        
        # 요약 실행
        sentences_count = data.get('sentences_count', 5)
        result = summarizer.summarize(text, sentences_count=sentences_count)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"요약 API 오류: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============== 메인 실행 ==============

def run_server(host='127.0.0.1', port=5000, debug=False):
    """서버 실행"""
    initialize()
    logger.info(f"Flask 서버 시작: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    # 개발 모드 실행
    run_server(debug=True)

