# -*- coding: utf-8 -*-
"""
파일 시스템 감시 모듈 - 실시간 파일 변경 감지 및 자동 인덱싱
"""

import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Set
from database import DatabaseManager
from indexer import FileIndexer

logger = logging.getLogger(__name__)


class IndexedFileWatcher(FileSystemEventHandler):
    """
    파일 시스템 변경을 감지하고 자동으로 인덱싱/업데이트/삭제 마킹을 수행하는 핸들러
    
    기능:
    1. 파일 수정 감지 → 자동 재인덱싱
    2. 파일 삭제 감지 → DB에 삭제 마킹 (물리적 삭제 X)
    3. 파일 추가 감지 → 자동 인덱싱
    4. 파일 이동 감지 → DB 경로 업데이트
    """
    
    def __init__(self, db: DatabaseManager, indexer: FileIndexer):
        """
        Args:
            db: DatabaseManager 인스턴스
            indexer: FileIndexer 인스턴스
        """
        super().__init__()
        self.db = db
        self.indexer = indexer
        self.processing_files: Set[str] = set()  # 현재 처리 중인 파일 (중복 처리 방지)
        
        logger.info("📡 파일 감시 핸들러 초기화 완료")
    
    def _is_supported_file(self, file_path: str) -> bool:
        """
        지원하는 파일 형식인지 확인
        
        Args:
            file_path: 파일 경로
            
        Returns:
            bool: 지원 여부
        """
        ext = os.path.splitext(file_path)[1].lower()
        supported_exts = (
            self.indexer.SUPPORTED_TEXT_EXTENSIONS | 
            self.indexer.SUPPORTED_DOC_EXTENSIONS | 
            self.indexer.SUPPORTED_IMAGE_EXTENSIONS
        )
        return ext in supported_exts
    
    def _should_exclude(self, file_path: str) -> bool:
        """
        제외할 파일인지 확인
        
        Args:
            file_path: 파일 경로
            
        Returns:
            bool: 제외 여부
        """
        # 제외할 폴더 패턴
        path_lower = file_path.lower()
        for excluded_dir in self.indexer.EXCLUDED_DIRS:
            if f"\\{excluded_dir}\\" in path_lower or f"/{excluded_dir}/" in path_lower:
                return True
        
        # 제외할 파일 확장자
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.indexer.EXCLUDED_EXTENSIONS:
            return True
        
        return False
    
    def on_created(self, event):
        """
        파일 생성 이벤트 처리
        
        Args:
            event: 파일 시스템 이벤트
        """
        if event.is_directory:
            return
        
        file_path = os.path.normpath(event.src_path)
        
        # 중복 처리 방지
        if file_path in self.processing_files:
            return
        
        # 지원하지 않는 파일 또는 제외 대상 체크
        if not self._is_supported_file(file_path) or self._should_exclude(file_path):
            return
        
        try:
            self.processing_files.add(file_path)
            
            # 파일이 완전히 생성될 때까지 대기 (쓰기 완료 대기)
            time.sleep(0.5)
            
            logger.info(f"➕ 새 파일 감지: {os.path.basename(file_path)}")
            
            # 자동 인덱싱
            self.indexer.index_single_file(file_path)
            logger.info(f"✅ 자동 인덱싱 완료: {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"❌ 파일 생성 처리 오류 [{os.path.basename(file_path)}]: {e}")
        finally:
            self.processing_files.discard(file_path)
    
    def on_modified(self, event):
        """
        파일 수정 이벤트 처리
        
        Args:
            event: 파일 시스템 이벤트
        """
        if event.is_directory:
            return
        
        file_path = os.path.normpath(event.src_path)
        
        # 중복 처리 방지
        if file_path in self.processing_files:
            return
        
        # 지원하지 않는 파일 또는 제외 대상 체크
        if not self._is_supported_file(file_path) or self._should_exclude(file_path):
            return
        
        # 인덱싱된 파일만 처리
        if not self.db.is_file_indexed(file_path):
            return
        
        try:
            self.processing_files.add(file_path)
            
            # 파일 쓰기가 완료될 때까지 대기
            time.sleep(0.5)
            
            logger.info(f"🔄 인덱싱된 파일 수정 감지: {os.path.basename(file_path)}")
            
            # 자동 재인덱싱
            self.indexer.index_single_file(file_path)
            logger.info(f"✅ 자동 재인덱싱 완료: {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"❌ 파일 수정 처리 오류 [{os.path.basename(file_path)}]: {e}")
        finally:
            self.processing_files.discard(file_path)
    
    def on_deleted(self, event):
        """
        파일 삭제 이벤트 처리
        
        Args:
            event: 파일 시스템 이벤트
        """
        if event.is_directory:
            return
        
        file_path = os.path.normpath(event.src_path)
        
        # 인덱싱된 파일만 처리 (deleted='0'인 파일만)
        # 이미 삭제 마킹된 파일(deleted='1')은 무시 (중복 처리 방지)
        if not self.db.is_file_indexed(file_path):
            return
        
        try:
            logger.info(f"🗑️ 인덱싱된 파일 삭제 감지: {os.path.basename(file_path)}")
            
            # DB에 삭제 마킹 (물리적 삭제 X)
            self.db.mark_as_deleted(file_path)
            logger.info(f"✅ 삭제 마킹 완료: {os.path.basename(file_path)}")
            
        except Exception as e:
            logger.error(f"❌ 파일 삭제 처리 오류 [{os.path.basename(file_path)}]: {e}")
    
    def on_moved(self, event):
        """
        파일 이동/이름 변경 이벤트 처리
        
        Args:
            event: 파일 시스템 이벤트
        """
        if event.is_directory:
            return
        
        src_path = os.path.normpath(event.src_path)
        dest_path = os.path.normpath(event.dest_path)
        
        # 중복 처리 방지
        if src_path in self.processing_files or dest_path in self.processing_files:
            return
        
        # 인덱싱된 파일만 처리
        if not self.db.is_file_indexed(src_path):
            return
        
        try:
            self.processing_files.add(src_path)
            self.processing_files.add(dest_path)
            
            logger.info(f"📦 파일 이동 감지: {os.path.basename(src_path)} → {os.path.basename(dest_path)}")
            
            # 기존 파일 삭제 마킹
            self.db.mark_as_deleted(src_path)
            
            # 새 위치에 파일이 지원 형식이고 제외 대상이 아니면 재인덱싱
            if self._is_supported_file(dest_path) and not self._should_exclude(dest_path):
                time.sleep(0.5)  # 이동 완료 대기
                self.indexer.index_single_file(dest_path)
                logger.info(f"✅ 이동된 파일 재인덱싱 완료: {os.path.basename(dest_path)}")
            else:
                logger.info(f"⚠️ 이동된 파일은 지원하지 않거나 제외 대상: {os.path.basename(dest_path)}")
            
        except Exception as e:
            logger.error(f"❌ 파일 이동 처리 오류 [{os.path.basename(src_path)}]: {e}")
        finally:
            self.processing_files.discard(src_path)
            self.processing_files.discard(dest_path)


class FileSystemWatcher:
    """
    파일 시스템 감시 관리자
    """
    
    def __init__(self, db: DatabaseManager, indexer: FileIndexer):
        """
        Args:
            db: DatabaseManager 인스턴스
            indexer: FileIndexer 인스턴스
        """
        self.db = db
        self.indexer = indexer
        self.observer = Observer()
        self.event_handler = IndexedFileWatcher(db, indexer)
        self.watched_paths: Set[str] = set()
        self.watch_handles = {}  # 경로별 watch handle 저장
        
        logger.info("📡 파일 시스템 감시 관리자 초기화 완료")
    
    def add_watch_path(self, directory: str):
        """
        감시할 디렉토리 추가
        
        Args:
            directory: 감시할 디렉토리 경로
        """
        if not os.path.isdir(directory):
            logger.warning(f"⚠️ 디렉토리가 존재하지 않음: {directory}")
            return
        
        if directory in self.watched_paths:
            logger.info(f"ℹ️ 이미 감시 중인 디렉토리: {directory}")
            return
        
        try:
            # watch handle 저장 (제거 시 필요)
            watch = self.observer.schedule(self.event_handler, directory, recursive=True)
            self.watch_handles[directory] = watch
            self.watched_paths.add(directory)
            logger.info(f"👀 감시 시작: {directory} (하위 폴더 포함)")
        except Exception as e:
            logger.error(f"❌ 감시 추가 오류 [{directory}]: {e}")
    
    def remove_watch_path(self, directory: str):
        """
        감시 중인 디렉토리 제거
        
        Args:
            directory: 제거할 디렉토리 경로
        """
        if directory not in self.watched_paths:
            logger.warning(f"⚠️ 감시 중이 아닌 디렉토리: {directory}")
            return
        
        try:
            # watch handle을 사용하여 observer에서 제거
            if directory in self.watch_handles:
                watch = self.watch_handles[directory]
                self.observer.unschedule(watch)
                del self.watch_handles[directory]
            
            self.watched_paths.discard(directory)
            logger.info(f"🚫 감시 중지: {directory}")
        except Exception as e:
            logger.error(f"❌ 감시 제거 오류 [{directory}]: {e}")
    
    def start(self):
        """파일 시스템 감시 시작"""
        if not self.observer.is_alive():
            self.observer.start()
            logger.info("🚀 파일 시스템 감시 시작")
    
    def stop(self):
        """파일 시스템 감시 중지"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("🛑 파일 시스템 감시 중지")
    
    def get_watched_paths(self) -> list:
        """
        감시 중인 디렉토리 목록 반환
        
        Returns:
            list: 감시 중인 디렉토리 경로 리스트
        """
        return list(self.watched_paths)


if __name__ == "__main__":
    # 테스트 코드
    db = DatabaseManager()
    indexer = FileIndexer(db)
    watcher = FileSystemWatcher(db, indexer)
    
    # 테스트 디렉토리 감시
    test_dir = "C:\\Users\\dylee\\Documents\\Test Documents"
    if os.path.exists(test_dir):
        watcher.add_watch_path(test_dir)
        watcher.start()
        
        print(f"📡 감시 중인 디렉토리: {watcher.get_watched_paths()}")
        print("파일을 생성, 수정, 삭제해보세요. Ctrl+C로 종료합니다.")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
            print("\n👋 감시 종료")
    else:
        print(f"⚠️ 테스트 디렉토리가 존재하지 않습니다: {test_dir}")
