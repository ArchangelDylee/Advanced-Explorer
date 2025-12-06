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

# ========================================
# UTF-8 전역 설정 (최우선 실행)
# ========================================
# Python 표준 출력/에러 스트림을 UTF-8로 강제 설정
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Windows 콘솔 코드 페이지를 UTF-8로 설정 (가능한 경우)
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)  # UTF-8 입력
        kernel32.SetConsoleOutputCP(65001)  # UTF-8 출력
    except Exception:
        pass

from database import DatabaseManager
from indexer import FileIndexer
from search import SearchEngine

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


def initialize():
    """백엔드 초기화"""
    global db_manager, indexer, search_engine
    
    # 데이터베이스 경로
    db_path = os.path.join(os.path.dirname(__file__), "file_index.db")
    
    # 데이터베이스 초기화
    db_manager = DatabaseManager(db_path)
    logger.info(f"데이터베이스 초기화: {db_path}")
    
    # 인덱서 초기화
    indexer = FileIndexer(db_manager)
    logger.info("파일 인덱서 초기화 완료")
    
    # 검색 엔진 초기화
    search_engine = SearchEngine(db_manager)
    logger.info("검색 엔진 초기화 완료")
    
    # 종료 시 정리 함수 등록
    atexit.register(cleanup)


def cleanup():
    """백엔드 종료 시 정리"""
    global indexer, db_manager
    
    try:
        if indexer:
            # 재시도 워커 중지
            indexer.stop_retry_worker()
            
            # 인덱싱 중지
            if indexer.is_running:
                indexer.stop_indexing()
        
        if db_manager:
            db_manager.close()
        
        logger.info("백엔드 정리 완료")
    
    except Exception as e:
        logger.error(f"정리 중 오류: {e}")


# ============== API 엔드포인트 ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'ok',
        'message': 'Python backend is running'
    })


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
        file_path: 파일 경로
    """
    try:
        file_detail = db_manager.get_indexed_file_detail(file_path)
        
        if file_detail:
            return jsonify(file_detail)
        else:
            return jsonify({'error': 'File not found in index'}), 404
    except Exception as e:
        logger.error(f"파일 상세 조회 오류: {e}")
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
        
        return jsonify({
            'query': query,
            'parsed': parsed,
            'count': len(results),
            'results': results
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
        return jsonify(stats)
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
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


# ============== 메인 실행 ==============

def run_server(host='127.0.0.1', port=5000, debug=False):
    """서버 실행"""
    initialize()
    logger.info(f"Flask 서버 시작: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    # 개발 모드 실행
    run_server(debug=True)

