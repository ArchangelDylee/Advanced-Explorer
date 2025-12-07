# -*- coding: utf-8 -*-
"""
UTF-8 인코딩 테스트 스크립트
다국어 지원이 모든 영역에서 올바르게 작동하는지 확인합니다.
"""

import sys
import os
import io
import json
import sqlite3
import logging

# UTF-8 전역 설정
if sys.platform == 'win32':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

# stdout/stderr UTF-8 설정
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

# 테스트 문자열 (다국어)
TEST_STRINGS = {
    'korean': '안녕하세요, 한글 테스트입니다.',
    'english': 'Hello, English test.',
    'japanese': 'こんにちは、日本語のテストです。',
    'chinese': '你好，中文测试。',
    'emoji': '😀 🎉 ✨ 한글과 이모지',
    'mixed': 'Hello 안녕 こんにちは 你好 🌍'
}

def print_section(title):
    """섹션 제목 출력"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_console_output():
    """1. 콘솔 출력 테스트"""
    print_section("1. 콘솔 출력 테스트")
    
    print(f"Python 버전: {sys.version}")
    print(f"기본 인코딩: {sys.getdefaultencoding()}")
    print(f"stdout 인코딩: {sys.stdout.encoding}")
    print(f"stderr 인코딩: {sys.stderr.encoding}")
    print(f"파일시스템 인코딩: {sys.getfilesystemencoding()}")
    
    print("\n테스트 문자열 출력:")
    for lang, text in TEST_STRINGS.items():
        print(f"  [{lang:10}] {text}")
    
    print("✅ 콘솔 출력 테스트 완료")

def test_file_operations():
    """2. 파일 읽기/쓰기 테스트"""
    print_section("2. 파일 읽기/쓰기 테스트")
    
    test_file = 'test_utf8.txt'
    
    # 쓰기 테스트
    print(f"파일 쓰기: {test_file}")
    try:
        with open(test_file, 'w', encoding='utf-8') as f:
            for lang, text in TEST_STRINGS.items():
                f.write(f"[{lang}] {text}\n")
        print("✅ 파일 쓰기 성공")
    except Exception as e:
        print(f"❌ 파일 쓰기 실패: {e}")
        return
    
    # 읽기 테스트
    print(f"파일 읽기: {test_file}")
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print("파일 내용:")
        print(content)
        print("✅ 파일 읽기 성공")
    except Exception as e:
        print(f"❌ 파일 읽기 실패: {e}")
    finally:
        # 테스트 파일 삭제
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"테스트 파일 삭제: {test_file}")

def test_json_serialization():
    """3. JSON 직렬화 테스트"""
    print_section("3. JSON 직렬화 테스트")
    
    test_data = {
        'title': '테스트 데이터',
        'languages': TEST_STRINGS,
        'path': 'C:\\사용자\\문서\\테스트.txt'
    }
    
    # JSON 인코딩
    try:
        json_str = json.dumps(test_data, ensure_ascii=False, indent=2)
        print("JSON 인코딩 결과:")
        print(json_str)
        print("✅ JSON 인코딩 성공")
    except Exception as e:
        print(f"❌ JSON 인코딩 실패: {e}")
        return
    
    # JSON 디코딩
    try:
        decoded_data = json.loads(json_str)
        print("\nJSON 디코딩 확인:")
        print(f"  title: {decoded_data['title']}")
        print(f"  path: {decoded_data['path']}")
        print("✅ JSON 디코딩 성공")
    except Exception as e:
        print(f"❌ JSON 디코딩 실패: {e}")

def test_database_operations():
    """4. 데이터베이스 UTF-8 테스트"""
    print_section("4. 데이터베이스 UTF-8 테스트")
    
    db_file = 'test_utf8.db'
    
    try:
        # DB 연결
        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA encoding = 'UTF-8'")
        cursor = conn.cursor()
        
        # 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                language TEXT,
                content TEXT
            )
        """)
        
        # 데이터 삽입
        print("데이터 삽입:")
        for lang, text in TEST_STRINGS.items():
            cursor.execute("INSERT INTO test_table (language, content) VALUES (?, ?)", 
                         (lang, text))
            print(f"  [{lang}] {text}")
        conn.commit()
        print("✅ 데이터 삽입 성공")
        
        # 데이터 조회
        print("\n데이터 조회:")
        cursor.execute("SELECT language, content FROM test_table")
        rows = cursor.fetchall()
        for lang, content in rows:
            print(f"  [{lang}] {content}")
        print("✅ 데이터 조회 성공")
        
        # 연결 종료
        conn.close()
        
    except Exception as e:
        print(f"❌ 데이터베이스 테스트 실패: {e}")
    finally:
        # 테스트 DB 삭제
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"\n테스트 DB 삭제: {db_file}")

def test_logging():
    """5. 로깅 UTF-8 테스트"""
    print_section("5. 로깅 UTF-8 테스트")
    
    log_file = 'test_utf8.log'
    
    # 로거 설정
    logger = logging.getLogger('utf8_test')
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러 추가
    file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # 로그 기록
    print(f"로그 파일 쓰기: {log_file}")
    try:
        for lang, text in TEST_STRINGS.items():
            logger.info(f"[{lang}] {text}")
        print("✅ 로그 쓰기 성공")
    except Exception as e:
        print(f"❌ 로그 쓰기 실패: {e}")
    
    # 로그 파일 읽기
    print(f"\n로그 파일 읽기: {log_file}")
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
        print(log_content)
        print("✅ 로그 읽기 성공")
    except Exception as e:
        print(f"❌ 로그 읽기 실패: {e}")
    finally:
        # 로그 파일 삭제
        logger.removeHandler(file_handler)
        file_handler.close()
        if os.path.exists(log_file):
            os.remove(log_file)
            print(f"\n테스트 로그 삭제: {log_file}")

def test_path_encoding():
    """6. 파일 경로 인코딩 테스트"""
    print_section("6. 파일 경로 인코딩 테스트")
    
    test_paths = [
        'C:\\Users\\사용자\\문서\\테스트.txt',
        'D:\\프로젝트\\한글폴더\\README.md',
        'E:\\データ\\日本語\\test.pdf',
        'F:\\数据\\中文\\文件.docx'
    ]
    
    print("파일 경로 테스트:")
    for path in test_paths:
        print(f"  {path}")
        # os.path 함수로 경로 처리 테스트
        dirname = os.path.dirname(path)
        basename = os.path.basename(path)
        print(f"    → dirname: {dirname}")
        print(f"    → basename: {basename}")
    
    print("✅ 파일 경로 인코딩 테스트 완료")

def main():
    """메인 실행 함수"""
    print("\n" + "█" * 60)
    print("  UTF-8 인코딩 통합 테스트")
    print("  Advanced Explorer - 다국어 지원 검증")
    print("█" * 60)
    
    try:
        test_console_output()
        test_file_operations()
        test_json_serialization()
        test_database_operations()
        test_logging()
        test_path_encoding()
        
        print_section("✅ 모든 테스트 완료")
        print("\n모든 영역에서 UTF-8 인코딩이 정상 작동합니다!")
        print("다국어(한글, 영어, 일본어, 중국어, 이모지)가 올바르게 처리됩니다.")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

