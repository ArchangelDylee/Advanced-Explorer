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

from database import DatabaseManager
from indexer import FileIndexer
from search import SearchEngine

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask 앱 생성
app = Flask(__name__)
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
        return jsonify({
            'is_running': indexer.is_running,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"상태 조회 오류: {e}")
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

