# -*- coding: utf-8 -*-
"""
PyQt6 GUI for Advanced Explorer
로컬 파일 인덱싱 및 검색 도구
"""

import sys
import os
import io
import requests
from typing import List, Dict, Optional

# ========================================
# UTF-8 전역 설정 (최우선 실행)
# ========================================
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
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QProgressBar, QSplitter, QFrame, QHeaderView, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor

# Flask API 기본 URL
API_BASE_URL = 'http://127.0.0.1:5000/api'


class SearchWorker(QThread):
    """검색 Worker Thread"""
    
    # Signals
    progress_signal = pyqtSignal(int, int)  # current, total
    log_signal = pyqtSignal(str)  # message
    status_signal = pyqtSignal(str)  # status text
    finished_signal = pyqtSignal(list)  # results
    
    def __init__(self, query: str, search_path: str = None):
        super().__init__()
        self.query = query
        self.search_path = search_path
        self.is_running = True
    
    def run(self):
        """검색 실행"""
        try:
            self.status_signal.emit(f"검색 중: '{self.query}'...")
            self.log_signal.emit(f"검색 시작: {self.query}")
            
            # Flask API 호출
            response = requests.post(
                f"{API_BASE_URL}/search/combined",
                json={
                    'query': self.query,
                    'search_path': self.search_path,
                    'max_results': 100
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                count = len(results)
                
                self.log_signal.emit(f"Found {count} results for '{self.query}'")
                self.status_signal.emit(f"검색 완료: {count}개 결과")
                self.finished_signal.emit(results)
            else:
                self.log_signal.emit(f"Error: {response.status_code}")
                self.status_signal.emit("검색 오류")
                self.finished_signal.emit([])
        
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.status_signal.emit("검색 실패")
            self.finished_signal.emit([])
    
    def stop(self):
        """검색 중지"""
        self.is_running = False


class IndexingWorker(QThread):
    """인덱싱 Worker Thread"""
    
    # Signals
    progress_signal = pyqtSignal(int, int)  # current, total
    log_signal = pyqtSignal(str)  # message
    status_signal = pyqtSignal(str)  # status text
    finished_signal = pyqtSignal()
    
    def __init__(self, paths: List[str]):
        super().__init__()
        self.paths = paths
        self.is_running = True
    
    def run(self):
        """인덱싱 실행"""
        try:
            self.status_signal.emit("인덱싱 시작...")
            self.log_signal.emit(f"인덱싱 경로: {', '.join(self.paths)}")
            
            # Flask API 호출
            response = requests.post(
                f"{API_BASE_URL}/indexing/start",
                json={'paths': self.paths},
                timeout=5
            )
            
            if response.status_code == 200:
                self.log_signal.emit("인덱싱이 백그라운드에서 시작되었습니다.")
                
                # 상태 폴링
                while self.is_running:
                    self.msleep(1000)  # 1초 대기
                    
                    status_response = requests.get(
                        f"{API_BASE_URL}/indexing/status",
                        timeout=5
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        stats = status_data.get('stats', {})
                        is_running = status_data.get('is_running', False)
                        
                        total = stats.get('total_files', 0)
                        indexed = stats.get('indexed_files', 0)
                        
                        if total > 0:
                            self.progress_signal.emit(indexed, total)
                            self.status_signal.emit(f"인덱싱 중: {indexed}/{total}")
                        
                        if not is_running:
                            break
                
                self.log_signal.emit("인덱싱 완료!")
                self.status_signal.emit("인덱싱 완료")
                self.finished_signal.emit()
            else:
                self.log_signal.emit(f"Error: {response.status_code}")
                self.status_signal.emit("인덱싱 오류")
        
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.status_signal.emit("인덱싱 실패")
    
    def stop(self):
        """인덱싱 중지"""
        self.is_running = False
        try:
            requests.post(f"{API_BASE_URL}/indexing/stop", timeout=5)
        except:
            pass


class AdvancedExplorerGUI(QMainWindow):
    """Advanced Explorer 메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.search_worker: Optional[SearchWorker] = None
        self.indexing_worker: Optional[IndexingWorker] = None
        self.current_directory = "C:\\Users"
        
        self.init_ui()
        self.check_backend_connection()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("Advanced Explorer - PyQt6")
        self.setGeometry(100, 100, 1400, 900)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 상단: 검색 바
        search_layout = self._create_search_bar()
        main_layout.addLayout(search_layout)
        
        # 중앙: Splitter (좌측, 중앙, 우측)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 좌측: 즐겨찾기 + 폴더 트리
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 중앙: 파일 리스트
        center_panel = self._create_center_panel()
        splitter.addWidget(center_panel)
        
        # 우측: 내역 보기 및 편집
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        
        main_layout.addWidget(splitter)
        
        # 하단: 상태바 + 인덱싱 로그
        bottom_layout = self._create_bottom_panel()
        main_layout.addLayout(bottom_layout)
    
    def _create_search_bar(self) -> QHBoxLayout:
        """검색 바 생성"""
        layout = QHBoxLayout()
        
        # 검색 입력
        self.cbo_search_keyword = QComboBox()
        self.cbo_search_keyword.setEditable(True)
        self.cbo_search_keyword.setPlaceholderText("검색어 입력...")
        self.cbo_search_keyword.lineEdit().returnPressed.connect(self.on_search)
        layout.addWidget(QLabel("검색:"))
        layout.addWidget(self.cbo_search_keyword, 3)
        
        # 검색 버튼
        self.btn_search = QPushButton("검색")
        self.btn_search.clicked.connect(self.on_search)
        layout.addWidget(self.btn_search)
        
        # 검색 중지
        self.btn_stop_search = QPushButton("검색 중지")
        self.btn_stop_search.clicked.connect(self.on_stop_search)
        self.btn_stop_search.setEnabled(False)
        layout.addWidget(self.btn_stop_search)
        
        return layout
    
    def _create_left_panel(self) -> QWidget:
        """좌측 패널: 즐겨찾기 + 폴더 트리"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 즐겨찾기
        layout.addWidget(QLabel("⭐ 즐겨찾기"))
        self.tree_favorites = QTreeWidget()
        self.tree_favorites.setHeaderLabel("이름")
        self.tree_favorites.itemClicked.connect(self.on_favorite_clicked)
        layout.addWidget(self.tree_favorites, 1)
        
        # 폴더 트리
        layout.addWidget(QLabel("📁 폴더 트리"))
        self.tree_folders = QTreeWidget()
        self.tree_folders.setHeaderLabel("폴더")
        self.tree_folders.itemClicked.connect(self.on_folder_clicked)
        layout.addWidget(self.tree_folders, 2)
        
        # 초기 데이터 로드
        self._load_favorites()
        self._load_folder_tree()
        
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """중앙 패널: 파일 리스트 + 인덱싱 버튼"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 인덱싱 버튼
        btn_layout = QHBoxLayout()
        self.btn_index_start = QPushButton("인덱싱 시작")
        self.btn_index_start.clicked.connect(self.on_index_start)
        btn_layout.addWidget(self.btn_index_start)
        
        self.btn_index_stop = QPushButton("인덱싱 중지")
        self.btn_index_stop.clicked.connect(self.on_index_stop)
        self.btn_index_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_index_stop)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 파일 리스트
        layout.addWidget(QLabel("📄 파일 리스트"))
        self.tree_file_list = QTreeWidget()
        self.tree_file_list.setHeaderLabels(["이름", "크기", "수정한 날짜", "경로"])
        self.tree_file_list.itemClicked.connect(self.on_file_clicked)
        
        # 스타일: 수평선 없애고 수직선 점선
        self.tree_file_list.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ccc;
                gridline-color: #ddd;
                outline: none;
            }
            QTreeWidget::item {
                border: 0px;
                border-right: 1px dotted #ddd;
            }
        """)
        
        header = self.tree_file_list.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        layout.addWidget(self.tree_file_list, 1)
        
        # 진행 상황
        self.lbl_total_count = QLabel("Total: 0 files")
        layout.addWidget(self.lbl_total_count)
        
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """우측 패널: 내역 보기 및 편집"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # 버튼
        btn_layout = QHBoxLayout()
        self.btn_view_indexed = QPushButton("인덱싱 보기")
        self.btn_view_indexed.clicked.connect(self.on_view_indexed)
        btn_layout.addWidget(self.btn_view_indexed)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 내역 표시
        layout.addWidget(QLabel("📝 내역 보기 및 편집"))
        self.txt_content_view = QTextEdit()
        self.txt_content_view.setReadOnly(True)
        layout.addWidget(self.txt_content_view, 1)
        
        return panel
    
    def _create_bottom_panel(self) -> QVBoxLayout:
        """하단 패널: 로그 + 상태"""
        layout = QVBoxLayout()
        
        # 탭 형식 로그
        log_layout = QHBoxLayout()
        
        # 검색 로그
        search_log_widget = QWidget()
        search_log_layout = QVBoxLayout()
        search_log_widget.setLayout(search_log_layout)
        search_log_layout.addWidget(QLabel("🔍 검색 로그"))
        self.txt_log_search = QTextEdit()
        self.txt_log_search.setMaximumHeight(150)
        self.txt_log_search.setReadOnly(True)
        search_log_layout.addWidget(self.txt_log_search)
        log_layout.addWidget(search_log_widget)
        
        # 인덱싱 로그
        indexing_log_widget = QWidget()
        indexing_log_layout = QVBoxLayout()
        indexing_log_widget.setLayout(indexing_log_layout)
        indexing_log_layout.addWidget(QLabel("📊 인덱싱 로그"))
        self.txt_log_indexing = QTextEdit()
        self.txt_log_indexing.setMaximumHeight(150)
        self.txt_log_indexing.setReadOnly(True)
        indexing_log_layout.addWidget(self.txt_log_indexing)
        log_layout.addWidget(indexing_log_widget)
        
        layout.addLayout(log_layout)
        
        # 상태 바
        self.lbl_process_status = QLabel("준비")
        self.lbl_process_status.setStyleSheet("QLabel { padding: 5px; background-color: #f0f0f0; }")
        layout.addWidget(self.lbl_process_status)
        
        return layout
    
    def _load_favorites(self):
        """즐겨찾기 로드"""
        user_home = os.path.expanduser("~")
        favorites = [
            ("문서", os.path.join(user_home, "Documents")),
            ("바탕화면", os.path.join(user_home, "Desktop")),
            ("다운로드", os.path.join(user_home, "Downloads")),
            ("사진", os.path.join(user_home, "Pictures")),
            ("음악", os.path.join(user_home, "Music"))
        ]
        
        for name, path in favorites:
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self.tree_favorites.addTopLevelItem(item)
    
    def _load_folder_tree(self):
        """폴더 트리 로드"""
        # 드라이브 목록
        import string
        from pathlib import Path
        
        for drive in string.ascii_uppercase:
            drive_path = f"{drive}:\\"
            if Path(drive_path).exists():
                item = QTreeWidgetItem([f"로컬 디스크 ({drive}:)"])
                item.setData(0, Qt.ItemDataRole.UserRole, drive_path)
                self.tree_folders.addTopLevelItem(item)
    
    def check_backend_connection(self):
        """백엔드 연결 확인"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                self.lbl_process_status.setText("✅ Python 백엔드 연결됨")
                self.lbl_process_status.setStyleSheet("QLabel { padding: 5px; background-color: #d4edda; color: #155724; }")
            else:
                self.lbl_process_status.setText("⚠️ 백엔드 응답 없음")
                self.lbl_process_status.setStyleSheet("QLabel { padding: 5px; background-color: #fff3cd; color: #856404; }")
        except:
            self.lbl_process_status.setText("❌ Python 백엔드 연결 실패 (http://127.0.0.1:5000)")
            self.lbl_process_status.setStyleSheet("QLabel { padding: 5px; background-color: #f8d7da; color: #721c24; }")
            QMessageBox.warning(self, "연결 오류", "Python 백엔드에 연결할 수 없습니다.\n서버를 시작했는지 확인하세요.")
    
    def on_search(self):
        """검색 실행"""
        query = self.cbo_search_keyword.currentText().strip()
        if not query:
            QMessageBox.warning(self, "입력 오류", "검색어를 입력하세요.")
            return
        
        # 검색 시작
        self.btn_search.setEnabled(False)
        self.btn_stop_search.setEnabled(True)
        self.tree_file_list.clear()
        
        self.search_worker = SearchWorker(query, self.current_directory)
        self.search_worker.progress_signal.connect(self.on_search_progress)
        self.search_worker.log_signal.connect(self.on_search_log)
        self.search_worker.status_signal.connect(self.on_status_update)
        self.search_worker.finished_signal.connect(self.on_search_finished)
        self.search_worker.start()
    
    def on_stop_search(self):
        """검색 중지"""
        if self.search_worker:
            self.search_worker.stop()
            self.btn_search.setEnabled(True)
            self.btn_stop_search.setEnabled(False)
    
    def on_search_progress(self, current: int, total: int):
        """검색 진행 상황"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def on_search_log(self, message: str):
        """검색 로그"""
        self.txt_log_search.append(message)
    
    def on_status_update(self, status: str):
        """상태 업데이트"""
        self.lbl_process_status.setText(status)
    
    def on_search_finished(self, results: List[Dict]):
        """검색 완료"""
        self.btn_search.setEnabled(True)
        self.btn_stop_search.setEnabled(False)
        
        # 결과 표시
        for result in results:
            name = result.get('name', '')
            size = self._format_size(result.get('size', 0))
            mtime = result.get('mtime', '')
            path = result.get('path', '')
            indexed = "✓" if result.get('indexed', False) else ""
            
            item = QTreeWidgetItem([f"{indexed} {name}", size, mtime, path])
            item.setData(0, Qt.ItemDataRole.UserRole, result)
            self.tree_file_list.addTopLevelItem(item)
        
        self.lbl_total_count.setText(f"Total: {len(results)} files")
        self.progress_bar.setValue(0)
    
    def on_index_start(self):
        """인덱싱 시작"""
        # 선택된 디렉토리 확인
        if not self.current_directory:
            QMessageBox.warning(self, "경로 오류", "인덱싱할 경로를 선택하세요.")
            return
        
        reply = QMessageBox.question(
            self, "인덱싱 확인",
            f"다음 경로를 인덱싱하시겠습니까?\n\n{self.current_directory}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_index_start.setEnabled(False)
            self.btn_index_stop.setEnabled(True)
            
            self.indexing_worker = IndexingWorker([self.current_directory])
            self.indexing_worker.progress_signal.connect(self.on_indexing_progress)
            self.indexing_worker.log_signal.connect(self.on_indexing_log)
            self.indexing_worker.status_signal.connect(self.on_status_update)
            self.indexing_worker.finished_signal.connect(self.on_indexing_finished)
            self.indexing_worker.start()
    
    def on_index_stop(self):
        """인덱싱 중지"""
        if self.indexing_worker:
            self.indexing_worker.stop()
            self.btn_index_start.setEnabled(True)
            self.btn_index_stop.setEnabled(False)
    
    def on_indexing_progress(self, current: int, total: int):
        """인덱싱 진행 상황"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_total_count.setText(f"Total: {current}/{total} files")
    
    def on_indexing_log(self, message: str):
        """인덱싱 로그"""
        self.txt_log_indexing.append(message)
    
    def on_indexing_finished(self):
        """인덱싱 완료"""
        self.btn_index_start.setEnabled(True)
        self.btn_index_stop.setEnabled(False)
        self.progress_bar.setValue(0)
        QMessageBox.information(self, "완료", "인덱싱이 완료되었습니다!")
    
    def on_favorite_clicked(self, item: QTreeWidgetItem, column: int):
        """즐겨찾기 클릭"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.current_directory = path
            self.lbl_process_status.setText(f"선택: {path}")
    
    def on_folder_clicked(self, item: QTreeWidgetItem, column: int):
        """폴더 트리 클릭"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.current_directory = path
            self.lbl_process_status.setText(f"선택: {path}")
    
    def on_file_clicked(self, item: QTreeWidgetItem, column: int):
        """파일 리스트 클릭"""
        result = item.data(0, Qt.ItemDataRole.UserRole)
        if result:
            # 인덱싱된 파일이면 내용 표시
            if result.get('indexed', False):
                self._show_indexed_content(result['path'])
            else:
                # 이미지 파일이면 미리보기
                ext = result.get('extension', '').lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    self.txt_content_view.setPlainText(f"[이미지 파일]\n\n경로: {result['path']}\n\n이미지 미리보기 기능은 추후 구현 예정")
                else:
                    self.txt_content_view.setPlainText(f"[인덱싱되지 않은 파일]\n\n경로: {result['path']}")
    
    def on_view_indexed(self):
        """인덱싱 DB 내역 보기"""
        try:
            response = requests.get(f"{API_BASE_URL}/statistics", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                total = stats.get('total_indexed_files', 0)
                size = stats.get('database_size', 0)
                
                self.txt_content_view.setPlainText(
                    f"=== 인덱싱 DB 통계 ===\n\n"
                    f"총 인덱싱된 파일: {total:,}개\n"
                    f"데이터베이스 크기: {self._format_size(size)}\n"
                )
        except Exception as e:
            QMessageBox.warning(self, "오류", f"DB 통계 조회 실패:\n{str(e)}")
    
    def _show_indexed_content(self, file_path: str):
        """인덱싱된 파일 내용 표시"""
        try:
            response = requests.post(
                f"{API_BASE_URL}/indexing/indexed-content",
                json={'path': file_path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('indexed', False):
                    content = data.get('content', '')
                    self.txt_content_view.setPlainText(
                        f"[인덱싱된 파일]\n\n"
                        f"경로: {file_path}\n\n"
                        f"--- 내용 ---\n\n{content[:5000]}"  # 처음 5000자
                    )
                else:
                    self.txt_content_view.setPlainText(f"인덱싱되지 않은 파일입니다.")
        except Exception as e:
            self.txt_content_view.setPlainText(f"오류: {str(e)}")
    
    def _format_size(self, bytes_size: int) -> str:
        """파일 크기 포맷팅"""
        if bytes_size == 0:
            return "0 B"
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        size = float(bytes_size)
        while size >= 1024 and i < len(units) - 1:
            size /= 1024
            i += 1
        return f"{size:.1f} {units[i]}"


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    # 폰트 설정
    font = QFont("맑은 고딕", 9)
    app.setFont(font)
    
    # 메인 윈도우
    window = AdvancedExplorerGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()



