import React, { useState, useEffect } from 'react';
import { 
  Search, Play, Square, Pause, Folder, File, FileText, 
  Monitor, HardDrive, Trash2, Copy, Clipboard,
  ChevronRight, ChevronDown, Image as ImageIcon,
  ArrowUp, ArrowDown, Clock, X, Plus,
  FileSpreadsheet, FileCode, FileArchive, LayoutTemplate,
  FileBox, Star, LucideIcon, ArrowLeft, ArrowRight, FolderPlus, Edit2, AlertTriangle, List, Activity, RefreshCw
} from 'lucide-react';
import * as BackendAPI from './api/backend';

// --- Types & Interfaces ---

interface FileItem {
  name: string;
  size: string;
  date: string;
  type: string; // 'folder' | 'file' extension
  path?: string; // Full path for navigation
  indexed?: boolean; // 인덱싱 여부
}

interface FolderNode {
  name: string;
  icon: string;
  path?: string; // 실제 파일 시스템 경로
  expanded?: boolean;
  selected?: boolean;
  children?: FolderNode[];
  childrenLoaded?: boolean; // 하위 폴더를 로드했는지 여부
}

interface FavoriteItem {
  name: string;
  path: string;
  icon: LucideIcon;
}

interface SortConfig {
  key: keyof FileItem | null;
  direction: 'asc' | 'desc';
}

interface HistoryEntry {
  name: string;
  path: string;
}

interface TabItem {
  id: number;
  title: string;
  searchText: string;
  selectedFolder: string; // Current Folder Name
  currentPath: string;    // Current Full Path
  selectedFile: FileItem | null;
  files: FileItem[];      // Content of current folder
  sortConfig: SortConfig;
  // Navigation History
  history: HistoryEntry[];
  historyIndex: number;
}

interface LayoutState {
  sidebarWidth: number;
  fileListWidth: number;
  bottomPanelHeight: number;
  favoritesHeight: number;
  searchLogWidth: number;
}

interface ColWidthsState {
  name: number;
  size: number;
  date: number;
}

interface SearchOptionsState {
  content: boolean;
  subfolder: boolean;
}

interface TypeFiltersState {
  [key: string]: boolean;
}

interface ContextMenuTarget {
  name: string;
  path: string;
  type: string;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  target: ContextMenuTarget | null;
}

interface DeleteDialogState {
  isOpen: boolean;
  item: FileItem | null;
}

interface IndexLogEntry {
  time: string;
  path: string;
  filename?: string;  // 파일명 (렌더링용)
  status: 'Indexed' | 'Skipped' | 'Error' | 'Success' | 'Skip' | 'Indexing' | 'Retry Success' | 'Info' | '파싱완료';
  size: string;
}

// Component Props Interfaces
interface ResizerProps {
  direction: 'horizontal' | 'vertical';
  onResize: (delta: number) => void;
}

interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

interface TreeItemProps {
  label: string;
  IconComponent: LucideIcon;
  expanded?: boolean;
  hasChildren?: boolean;
  level?: number;
  isSelected?: boolean;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
  onToggle?: () => void;
}

// --- 스타일 상수 (Windows 11 Dark Mica) ---
const COLORS = {
  windowBg: '#191919',
  titleBarBg: '#121212',
  panelBg: '#202020',
  border: '#444444',
  textPrimary: '#FFFFFF',
  textSecondary: '#D0D0D0',
  accentBlue: '#0067C0',
  hoverBg: '#333333',
  headerBg: '#2C2C2C',
  selectionBg: '#444444',
  scrollbarTrack: '#202020',
  scrollbarThumb: '#444444',
  scrollbarThumbHover: '#666666',
  accentRed: '#DC2626',
  tabActive: '#202020',
  tabInactive: 'transparent',
  tabHover: '#2A2A2A',
  menuBg: '#2D2D2D'
};

// --- LocalStorage Hook ---
function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((val: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === "undefined") {
      return initialValue;
    }
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      }
    } catch (error) {
      console.warn(`Error setting localStorage key "${key}":`, error);
    }
  };

  return [storedValue, setValue];
}

// --- Helper Functions ---

// Get Icon based on file extension or folder type
const getFileIconProps = (item: FileItem): { Icon: LucideIcon; color: string } => {
  if (item.type === 'folder') {
    return { Icon: Folder, color: '#FBBF24' }; // Yellow Folder
  }

  const filename = item.name;
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  
  switch (ext) {
    case 'xlsx': case 'xls': case 'csv': return { Icon: FileSpreadsheet, color: '#107C41' };
    case 'pptx': case 'ppt': return { Icon: LayoutTemplate, color: '#C43E1C' };
    case 'docx': case 'doc': return { Icon: FileText, color: '#2B579A' };
    case 'hwp': return { Icon: FileBox, color: '#3B82F6' };
    case 'pdf': return { Icon: FileText, color: '#F40F02' };
    case 'zip': case 'rar': case '7z': return { Icon: FileArchive, color: '#FCD34D' };
    case 'png': case 'jpg': case 'jpeg': case 'gif': case 'svg': return { Icon: ImageIcon, color: '#A855F7' };
    case 'js': case 'ts': case 'jsx': case 'tsx': case 'py': case 'html': case 'css': case 'json': return { Icon: FileCode, color: '#0EA5E9' };
    case 'txt': case 'md': return { Icon: FileText, color: '#9CA3AF' };
    default: return { Icon: File, color: '#D1D5DB' };
  }
};

const getFolderIconColor = (IconComponent: LucideIcon): string => {
  if (IconComponent === Folder) return '#FBBF24';
  if (IconComponent === Monitor) return '#60A5FA';
  if (IconComponent === HardDrive) return '#94A3B8';
  return '#D0D0D0';
};

// --- Mock Data ---
// Base files to be scattered across folders
const MOCK_BASE_FILES: FileItem[] = [
  { name: 'Report_Q4.docx', size: '24 KB', date: '2023-10-25', type: 'doc' },
  { name: 'Design_System.fig', size: '15 MB', date: '2023-10-26', type: 'img' },
  { name: 'Budget.xlsx', size: '12 KB', date: '2023-10-27', type: 'xls' },
  { name: 'Notes.txt', size: '2 KB', date: '2023-10-27', type: 'txt' },
  { name: 'Proposal.pdf', size: '4.5 MB', date: '2023-10-20', type: 'pdf' },
  { name: 'Logo.png', size: '1.2 MB', date: '2023-10-19', type: 'img' },
  { name: 'Script.js', size: '4 KB', date: '2023-10-30', type: 'code' },
];

// 초기 폴더 구조 (드라이브는 동적으로 로드됨)
const MOCK_FOLDERS_INITIAL: FolderNode[] = [
  { 
    name: '내 PC', 
    icon: 'Monitor', 
    path: 'My Computer',
    expanded: true,
    selected: false,
    children: [],
    childrenLoaded: false
  }
];

const MOCK_INDEX_LOGS: IndexLogEntry[] = [
  { time: '14:20:01', path: 'C:\\Users\\Admin\\Documents\\Report.docx', status: 'Indexed', size: '24KB' },
  { time: '14:20:05', path: 'C:\\Users\\Admin\\Pictures\\Photo.jpg', status: 'Skipped', size: '4.2MB' },
  { time: '14:20:12', path: 'C:\\Windows\\System32\\driver.sys', status: 'Error', size: '0KB' },
  { time: '14:20:15', path: 'D:\\Backup\\archive.zip', status: 'Indexed', size: '2.5GB' },
];

// 사용자 홈 디렉토리 가져오기 (Windows)
const getUserHome = () => {
  // Windows 기본 사용자 경로
  const username = 'dylee'; // 실제 사용자명
  return `C:\\Users\\${username}`;
};

const userHome = getUserHome();

const FAVORITES: FavoriteItem[] = [
  { name: '문서', path: `${userHome}\\Documents`, icon: Folder },
  { name: '바탕화면', path: `${userHome}\\Desktop`, icon: Monitor },
  { name: '다운로드', path: `${userHome}\\Downloads`, icon: Folder },
  { name: '사진', path: `${userHome}\\Pictures`, icon: ImageIcon },
  { name: '음악', path: `${userHome}\\Music`, icon: FileText },
];

const ICON_MAP: { [key: string]: LucideIcon } = {
  'Monitor': Monitor, 'HardDrive': HardDrive, 'Folder': Folder
};

// --- Components ---

const Resizer: React.FC<ResizerProps> = ({ direction, onResize }) => {
  const [isDragging, setIsDragging] = useState(false);
  useEffect(() => {
    const onMove = (e: MouseEvent) => isDragging && onResize(direction === 'horizontal' ? e.movementX : e.movementY);
    const onUp = () => { setIsDragging(false); document.body.style.cursor = 'default'; };
    if (isDragging) { window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp); document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize'; }
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [isDragging, direction, onResize]);
  return <div onMouseDown={() => setIsDragging(true)} className={`${direction === 'horizontal' ? 'w-1 cursor-col-resize' : 'h-1 cursor-row-resize'} hover:bg-[#0067C0] bg-transparent z-50`} />;
};

const Checkbox: React.FC<CheckboxProps> = ({ label, checked, onChange }) => (
  <label className="flex items-center space-x-2 cursor-pointer select-none group active:opacity-70 transition-opacity" onClick={() => onChange(!checked)}>
    <div className={`w-4 h-4 border flex items-center justify-center transition-colors ${checked ? 'border-[#777777] bg-[#0067C0]' : 'border-[#777777] bg-transparent'}`}>
      {checked && <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 fill-none stroke-white stroke-2"><path d="M3 8 L6 11 L13 4" /></svg>}
    </div>
    <span className="text-sm text-[#D0D0D0] pt-0.5">{label}</span>
  </label>
);

const TreeItem: React.FC<TreeItemProps> = ({ label, IconComponent, expanded, hasChildren, level = 0, isSelected, onClick, onContextMenu, onToggle }) => {
  const iconColor = getFolderIconColor(IconComponent);
  return (
    <div className={`flex items-center py-1 px-2 cursor-pointer text-sm select-none transition-all duration-75 active:scale-[0.99] active:bg-[#333] ${isSelected ? 'bg-[#333333] text-white border border-[#0067C0]' : 'text-[#D0D0D0] hover:bg-[#2C2C2C] border border-transparent'}`} style={{ paddingLeft: `${level * 16 + 8}px` }} onClick={onClick} onContextMenu={onContextMenu}>
      <div className="w-4 h-4 mr-1 flex items-center justify-center text-[#777] hover:text-white" onClick={(e) => { e.stopPropagation(); onToggle && onToggle(); }}>
        {hasChildren && (expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
      </div>
      <IconComponent size={14} className="mr-2" style={{ color: iconColor }} fill={iconColor} fillOpacity={0.2} />
      <span className="truncate pt-0.5 text-xs">{label}</span>
    </div>
  );
};

// --- Main App Component ---
export default function App() {
  // --- Persistent State ---
  const [layout, setLayout] = useLocalStorage<LayoutState>('layout', { sidebarWidth: 250, fileListWidth: 600, bottomPanelHeight: 200, favoritesHeight: 180, searchLogWidth: 600 });
  const [colWidths, setColWidths] = useLocalStorage<ColWidthsState>('colWidths', { name: 350, size: 100, date: 150 });
  const [searchHistory, setSearchHistory] = useLocalStorage<string[]>('searchHistory', ['기획서', '2023년 정산']);
  const [searchOptions, setSearchOptions] = useLocalStorage<SearchOptionsState>('searchOptions', { content: true, subfolder: true });
  const [typeFilters, setTypeFilters] = useLocalStorage<TypeFiltersState>('typeFilters', { ppt: true, doc: true, hwp: true, txt: true, pdf: true, csv: true, etc: false });
  const [folderStructure, setFolderStructure] = useLocalStorage<FolderNode[]>('folderStructure', MOCK_FOLDERS_INITIAL);

  // Tabs (Multi-instance)
  const [tabs, setTabs] = useLocalStorage<TabItem[]>('tabs', [{ 
    id: 1, title: '문서', searchText: '', selectedFolder: '문서', currentPath: `${userHome}\\Documents`, selectedFile: null, 
    files: [], sortConfig: { key: null, direction: 'asc' }, 
    history: [{ name: '문서', path: `${userHome}\\Documents` }], historyIndex: 0 
  }]);
  const [activeTabId, setActiveTabId] = useLocalStorage<number>('activeTabId', 1);
  const [nextTabId, setNextTabId] = useLocalStorage<number>('nextTabId', 2);

  // --- Transient State ---
  const [clipboard, setClipboard] = useState<FileItem | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({ isOpen: false, item: null });
  const [showIndexingLog, setShowIndexingLog] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [searchLog, setSearchLog] = useState<string[]>(['검색 진행 상태를 보여 줍니다']);
  const [indexingLog, setIndexingLog] = useState<IndexLogEntry[]>([]);
  const [indexedDatabase, setIndexedDatabase] = useState<BackendAPI.IndexedFileInfo[]>([]);
  const [dbTotalCount, setDbTotalCount] = useState<number>(0);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileSummary, setFileSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [isIndexStopping, setIsIndexStopping] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState<string>('대기 중...');
  const [indexingStats, setIndexingStats] = useState<any>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, target: null });
  
  // AbortController refs for cancelling pending requests
  const statusAbortControllerRef = React.useRef<AbortController | null>(null);
  const logsAbortControllerRef = React.useRef<AbortController | null>(null);
  const statsAbortControllerRef = React.useRef<AbortController | null>(null);
  
  const activeTab = tabs.find(t => t.id === activeTabId) || tabs[0];

  // Initialize DB statistics
  useEffect(() => {
    const loadDBStats = async () => {
      try {
        const stats = await BackendAPI.getStatistics();
        setDbTotalCount(stats.total_indexed_files);
      } catch (error) {
        console.error('DB 통계 로드 오류:', error);
      }
    };
    
    loadDBStats();
    // 10초마다 DB 통계 업데이트
    const statsInterval = setInterval(loadDBStats, 10000);
    return () => clearInterval(statsInterval);
  }, []);

  // Sync indexing status from backend
  useEffect(() => {
    let syncTimeout: NodeJS.Timeout;
    let syncInterval: NodeJS.Timeout;

    const checkIndexingStatus = async () => {
      try {
        const status = await BackendAPI.getIndexingStatus();
        
        // 백엔드의 실제 인덱싱 상태와 프론트엔드 상태 동기화
        if (status.is_running && !isIndexing) {
          setIsIndexing(true);
          setIsIndexStopping(false);
          setIndexingStatus('인덱싱 진행 중...');
        } else if (!status.is_running && isIndexing) {
          setIsIndexing(false);
          setIsIndexStopping(false);
          setIndexingStatus('대기 중...');
        }
        
        // 통계 업데이트
        if (status.stats) {
          setIndexingStats(status.stats);
        }
      } catch (error) {
        // 백엔드가 준비되지 않았을 수 있으므로 조용히 무시
        // console.log('인덱싱 상태 체크 실패 (백엔드 준비 중일 수 있음)');
      }
    };

    // 초기 지연 10초 후 시작 (백엔드가 완전히 초기화될 시간 제공)
    syncTimeout = setTimeout(() => {
      checkIndexingStatus(); // 첫 번째 체크
      // 5초마다 주기적으로 체크
      syncInterval = setInterval(checkIndexingStatus, 5000);
    }, 10000);

    return () => {
      if (syncTimeout) clearTimeout(syncTimeout);
      if (syncInterval) clearInterval(syncInterval);
    };
  }, [isIndexing]); // isIndexing 상태가 변경될 때마다 재설정

  // Auto-refresh indexing DB view every 1 minute
  useEffect(() => {
    if (!showIndexingLog) return;

    const refreshDB = async () => {
      try {
        const dbResponse = await BackendAPI.getIndexedDatabase(1000, 0);
        setIndexedDatabase(dbResponse.files);
        setDbTotalCount(dbResponse.total_count);
      } catch (error) {
        console.error('DB 자동 새로고침 오류:', error);
      }
    };

    // 1분(60초)마다 DB 조회
    const dbRefreshInterval = setInterval(refreshDB, 60000);
    
    return () => clearInterval(dbRefreshInterval);
  }, [showIndexingLog]);

  // Real-time update of file indexing status during indexing
  useEffect(() => {
    const updateFileIndexingStatus = async () => {
      try {
        // 현재 탭의 파일들 중 폴더가 아닌 파일들의 경로 가져오기
        const filePaths = activeTab.files
          .filter(item => item.type !== 'folder' && item.path)
          .map(item => item.path!);
        
        if (filePaths.length === 0) return;
        
        // 인덱싱 상태 확인
        const indexedStatus = await BackendAPI.checkFilesIndexed(filePaths);
        
        // 파일 목록 업데이트 (인덱싱 상태만 변경)
        const updatedFiles = activeTab.files.map(item => {
          if (item.type !== 'folder' && item.path) {
            const isIndexed = indexedStatus[item.path] || false;
            // 상태가 변경된 경우에만 업데이트
            if (item.indexed !== isIndexed) {
              return { ...item, indexed: isIndexed };
            }
          }
          return item;
        });
        
        // 실제로 변경된 항목이 있을 때만 업데이트
        if (JSON.stringify(updatedFiles) !== JSON.stringify(activeTab.files)) {
          updateActiveTab({ files: updatedFiles });
        }
      } catch (error) {
        console.error('파일 인덱싱 상태 업데이트 오류:', error);
      }
    };
    
    // 인덱싱 진행 중일 때
    if (isIndexing) {
      // 초기 업데이트
      updateFileIndexingStatus();
      
      // 2초마다 업데이트 (인덱싱 진행 중일 때만)
      const updateInterval = setInterval(updateFileIndexingStatus, 2000);
      
      return () => clearInterval(updateInterval);
    }
    
    // 인덱싱이 방금 종료된 경우 (isIndexing이 false로 변경됨)
    // 마지막으로 한 번 더 업데이트하여 최종 상태 반영
    const finalUpdateTimer = setTimeout(() => {
      updateFileIndexingStatus();
    }, 500); // 0.5초 후 마지막 업데이트
    
    return () => clearTimeout(finalUpdateTimer);
  }, [isIndexing, activeTab.currentPath]); // 인덱싱 상태나 경로가 변경될 때 재설정

  // Initialize drives and folder structure
  useEffect(() => {
    const initializeDrives = async () => {
      if (typeof window !== 'undefined' && (window as any).electronAPI) {
        try {
          const electronAPI = (window as any).electronAPI;
          const drives = await electronAPI.getDrives();
          
          // 드라이브별로 루트 폴더를 재귀적으로 로드 (2-3 레벨까지)
          const driveNodes: FolderNode[] = await Promise.all(
            drives.map(async (drive: any) => {
              const rootDirs = await electronAPI.readDirectoriesOnly(drive.path);
              // 특수 문자로 시작하는 폴더 필터링
              const validRootDirs = rootDirs.filter((dir: any) => isValidName(dir.name));
              
              // C:\ 드라이브만 추가로 하위 폴더 로드
              const rootChildren = await Promise.all(
                validRootDirs.map(async (dir: any) => {
                  if (drive.path === 'C:\\' && (dir.name === 'Users')) {
                    // Users 폴더는 하위까지 로드
                    const userDirs = await electronAPI.readDirectoriesOnly(dir.path);
                    // 특수 문자로 시작하는 폴더 필터링
                    const validUserDirs = userDirs.filter((userDir: any) => isValidName(userDir.name));
                    return {
                      name: dir.name,
                      icon: 'Folder',
                      path: dir.path,
                      expanded: true,
                      selected: false,
                      children: validUserDirs.map((userDir: any) => ({
                        name: userDir.name,
                        icon: 'Folder',
                        path: userDir.path,
                        expanded: false,
                        selected: false,
                        children: [],
                        childrenLoaded: false
                      })),
                      childrenLoaded: true
                    };
                  }
                  
                  return {
                    name: dir.name,
                    icon: 'Folder',
                    path: dir.path,
                    expanded: false,
                    selected: false,
                    children: [],
                    childrenLoaded: false
                  };
                })
              );
              
              return {
                name: drive.name,
                icon: 'HardDrive',
                path: drive.path,
                expanded: true, // 모든 드라이브 펼침
                selected: false,
                children: rootChildren,
                childrenLoaded: true
              };
            })
          );
          
          setFolderStructure([{
            name: '내 PC',
            icon: 'Monitor',
            path: 'My Computer',
            expanded: true, // 내 PC 펼침
            selected: false,
            children: driveNodes,
            childrenLoaded: true
          }]);
          
          // 시스템 메시지는 로그에 표시하지 않음
        } catch (error) {
          console.error('Error initializing drives:', error);
        }
      }
    };
    
    initializeDrives();
  }, []);

  // Initialize content for active tab on mount (single unified effect)
  const initialLoadDone = React.useRef(false);
  useEffect(() => {
    // Only run once on component mount
    if (initialLoadDone.current) return;
    initialLoadDone.current = true;
    
    // Load initial content if tab is empty
    if (activeTab && activeTab.files.length === 0) {
      const loadInitialContent = async () => {
        try {
          await navigate(activeTab.selectedFolder, activeTab.currentPath, true);
        } catch (error) {
          console.error('Initial content load error:', error);
        }
      };
      loadInitialContent();
    }
  }, []);

  // Load file content when file is selected (image or document)
  useEffect(() => {
    const loadFileContent = async () => {
      if (activeTab.selectedFile && activeTab.selectedFile.type !== 'folder') {
        const ext = activeTab.selectedFile.type.toLowerCase();
        console.log('🔍 파일 선택됨:', activeTab.selectedFile.name, '확장자:', ext);
        
        const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico'];
        const documentExtensions = ['txt', 'pdf', 'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'hwp'];
        
        if (imageExtensions.includes(ext)) {
          // 이미지 파일 - 미리보기 로드
          setFileContent(null);
          if (typeof window !== 'undefined' && (window as any).electronAPI) {
            try {
              const electronAPI = (window as any).electronAPI;
              const result = await electronAPI.readImageFile(activeTab.selectedFile.path);
              
              if (result.success) {
                setImagePreview(result.dataUrl);
              } else {
                setImagePreview(null);
              }
            } catch (error) {
              console.error('이미지 로드 오류:', error);
              setImagePreview(null);
            }
          }
        } else if (documentExtensions.includes(ext)) {
          // 문서 파일 - 인덱싱된 내용 조회
          setImagePreview(null);
          console.log('📄 문서 파일 선택:', activeTab.selectedFile.path);
          
          try {
            const detail = await BackendAPI.getIndexedFileDetail(activeTab.selectedFile.path);
            console.log('📦 API 응답:', detail);
            
            if (detail && detail.content) {
              setFileContent(detail.content);
            } else {
              setFileContent('⚠️ 인덱싱된 내용이 없습니다.\n\n파일이 아직 인덱싱되지 않았거나\nDB에 저장되지 않았을 수 있습니다.\n\n인덱싱을 시작하거나 재시작해주세요.');
            }
          } catch (error: any) {
            console.error('파일 내용 조회 오류:', error);
            const errorMsg = error?.message || String(error);
            
            if (errorMsg.includes('404')) {
              setFileContent('❌ 파일을 DB에서 찾을 수 없습니다.\n\n• DB가 초기화되었거나\n• 파일이 아직 인덱싱되지 않았습니다.\n\n인덱싱을 시작하거나 재시작해주세요.');
            } else {
              setFileContent(`❌ 파일 내용을 불러올 수 없습니다.\n\n오류: ${errorMsg}\n\n인덱싱이 완료되지 않았거나\n오류가 발생했습니다.`);
            }
          }
        } else {
          setImagePreview(null);
          setFileContent(null);
        }
      } else {
        setImagePreview(null);
        setFileContent(null);
        setFileSummary(null); // 요약도 초기화
      }
    };
    
    loadFileContent();
  }, [activeTab.selectedFile?.path]); // path를 체크하여 파일 변경 감지

  // --- Helpers ---
  const updateActiveTab = (updates: Partial<TabItem>) => {
    setTabs(prev => prev.map(t => t.id === activeTabId ? { ...t, ...updates } : t));
  };

  const addSearchLog = (msg: string) => {
    setSearchLog(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev]);
  };

  // 인덱싱 상태 메시지 추가 (간단한 텍스트)
  const addIndexingMessage = (message: string) => {
    const time = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    const newLog: IndexLogEntry = {
      time,
      path: message,
      status: 'Info',
      size: ''
    };
    setIndexingLog(prev => [newLog, ...prev].slice(0, 1000));
  };

  // 유효한 파일/폴더 이름인지 확인 (특수 문자로 시작하는 것 제외)
  const isValidName = (name: string): boolean => {
    return /^[a-zA-Z0-9가-힣]/.test(name);
  };

  // 인덱싱 로그에서 파일 클릭 시 인덱스 내용 표시
  const handleIndexLogClick = async (filePath: string) => {
    console.log('🔍 인덱스 파일 클릭:', filePath);
    
    try {
      const detail = await BackendAPI.getIndexedFileDetail(filePath);
      console.log('📦 API 응답:', detail);
      
      if (detail && detail.content) {
        setFileContent(detail.content);
        setFileSummary(null); // 요약 초기화
        // 내용 보기 및 편집 창으로 자동 전환
        setShowIndexingLog(false);
      } else {
        setFileContent('⚠️ 인덱싱된 내용이 없습니다.\n\n파일이 아직 인덱싱되지 않았거나\nDB에 저장되지 않았을 수 있습니다.\n\n인덱싱을 시작하거나 재시작해주세요.');
        setShowIndexingLog(false);
      }
    } catch (error: any) {
      console.error('❌ 인덱스 조회 오류:', error);
      const errorMsg = error?.message || String(error);
      
      if (errorMsg.includes('404')) {
        setFileContent('❌ 파일을 DB에서 찾을 수 없습니다.\n\n• DB가 초기화되었거나\n• 파일이 아직 인덱싱되지 않았습니다.\n\n인덱싱을 시작하거나 재시작해주세요.');
      } else {
        setFileContent(`❌ 파일 내용을 불러올 수 없습니다.\n\n오류: ${errorMsg}\n\n인덱싱이 완료되지 않았거나\n오류가 발생했습니다.`);
      }
      setShowIndexingLog(false);
    }
  };

  // 파일 내용 요약
  const handleSummarize = async () => {
    if (!activeTab.selectedFile?.path) {
      addSearchLog('⚠️ 파일을 선택해주세요');
      return;
    }

    try {
      setIsSummarizing(true);
      addSearchLog(`🔄 요약 생성 중: ${activeTab.selectedFile.name}`);
      
      const result = await BackendAPI.summarizeFile(activeTab.selectedFile.path, 5);
      
      if (result.success && result.summary) {
        setFileSummary(result.summary);
        addSearchLog(`✓ 요약 완료: ${result.original_length}자 → ${result.summary_length}자 (${result.compression_ratio})`);
      } else {
        setFileSummary(null);
        addSearchLog(`❌ 요약 실패: ${result.error || '알 수 없는 오류'}`);
      }
    } catch (error) {
      console.error('요약 오류:', error);
      addSearchLog(`❌ 요약 오류: ${error}`);
    } finally {
      setIsSummarizing(false);
    }
  };

  // --- Directory Content Generator (The "Fake" File System) ---
  // 파일 크기 포맷팅
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  // 파일 확장자 추출
  const getFileExtension = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    return ext || 'file';
  };

  const generateDirectoryContent = async (folderName: string, path: string): Promise<FileItem[]> => {
    // 특수 케이스: 내 PC (드라이브 목록)
    if (folderName === '내 PC' || path === 'My Computer') {
      return [
        { name: '로컬 디스크 (C:)', size: '', date: '', type: 'folder', path: 'C:\\' },
        { name: '로컬 디스크 (D:)', size: '', date: '', type: 'folder', path: 'D:\\' }
      ];
    }

    // Electron API를 통해 실제 디렉토리 읽기
    if (typeof window !== 'undefined' && (window as any).electronAPI) {
      try {
        const electronAPI = (window as any).electronAPI;
        const files = await electronAPI.readDirectory(path);
        
        // 특수 문자로 시작하는 파일/폴더 필터링
        const validFiles = files.filter((file: any) => isValidName(file.name));
        
        const fileItems: FileItem[] = await Promise.all(
          validFiles.map(async (file: any) => {
            const stats = await electronAPI.getFileStats(file.path);
            const fileSize = stats && !stats.isDirectory ? formatFileSize(stats.size) : '';
            const modifiedDate = stats ? new Date(stats.modified).toLocaleString('ko-KR', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: false
            }) : '';
            
            return {
              name: file.name,
              size: fileSize,
              date: modifiedDate,
              type: file.isDirectory ? 'folder' : getFileExtension(file.name),
              path: file.path
            };
          })
        );
        
        return fileItems;
      } catch (error) {
        console.error('Error reading directory:', error);
        addSearchLog(`디렉토리 읽기 오류: ${path}`);
        return [];
      }
    }
    
    // Electron이 아닌 경우 빈 배열 반환
    return [];
  };

  // --- Folder Tree Sync Helper ---
  const syncFolderTreeWithPath = async (targetPath: string) => {
    // 폴더 트리를 재귀적으로 업데이트하여 targetPath를 펼치고 선택
    const updateTreeNode = async (nodes: FolderNode[], pathToFind: string): Promise<{ nodes: FolderNode[], found: boolean }> => {
      let found = false;
      const updatedNodes = await Promise.all(nodes.map(async (node) => {
        // 모든 노드의 selected를 false로 초기화
        let updatedNode: FolderNode = { ...node, selected: false };
        
        // 현재 노드가 타겟 경로와 일치하는지 확인
        const nodePath = node.path || node.name;
        const isMatch = nodePath.toLowerCase() === pathToFind.toLowerCase();
        
        // 타겟 경로가 현재 노드의 하위 경로인지 확인
        const isParentOfTarget = pathToFind.toLowerCase().startsWith(nodePath.toLowerCase() + '\\');
        
        if (isMatch) {
          // 정확히 일치하면 선택하고 펼치기
          updatedNode = {
            ...updatedNode,
            selected: true,
            expanded: true
          };
          
          // 하위 폴더가 로드되지 않았다면 로드
          if (!updatedNode.childrenLoaded && node.path) {
            const loadedNode = await loadSubfoldersForSync(updatedNode);
            updatedNode = { ...loadedNode, selected: true };
          }
          
          found = true;
        } else if (isParentOfTarget) {
          // 부모 노드라면 펼치기
          updatedNode = { ...updatedNode, expanded: true };
          
          // 하위 폴더가 로드되지 않았다면 로드
          if (!updatedNode.childrenLoaded && node.path) {
            const loadedNode = await loadSubfoldersForSync(updatedNode);
            updatedNode = { ...loadedNode, expanded: true }; // expanded 상태 보존
          }
          
          // 자식들을 재귀적으로 확인
          if (updatedNode.children) {
            const childResult = await updateTreeNode(updatedNode.children, pathToFind);
            updatedNode = {
              ...updatedNode,
              children: childResult.nodes
            };
            found = childResult.found;
          }
        } else if (node.children) {
          // 그 외의 경우 자식들만 업데이트 (selected: false 적용)
          const childResult = await updateTreeNode(node.children, pathToFind);
          updatedNode = {
            ...updatedNode,
            children: childResult.nodes
          };
          if (childResult.found) found = true;
        }
        
        return updatedNode;
      }));
      
      return { nodes: updatedNodes, found };
    };
    
    const result = await updateTreeNode(folderStructure, targetPath);
    setFolderStructure(result.nodes);
  };

  // 동기화용 하위 폴더 로드 (폴더 구조 반환)
  const loadSubfoldersForSync = async (node: FolderNode): Promise<FolderNode> => {
    if (node.childrenLoaded || !node.path) return { ...node, selected: node.selected ?? false };
    
    if (typeof window !== 'undefined' && (window as any).electronAPI) {
      try {
        const electronAPI = (window as any).electronAPI;
        const subdirs = await electronAPI.readDirectoriesOnly(node.path);
        
        // 특수 문자로 시작하는 폴더 필터링
        const validSubdirs = subdirs.filter((dir: any) => isValidName(dir.name));
        
        return {
          ...node,
          selected: node.selected ?? false,
          children: validSubdirs.map((dir: any) => ({
            name: dir.name,
            icon: 'Folder',
            path: dir.path,
            expanded: false,
            selected: false,
            children: [],
            childrenLoaded: false
          })),
          childrenLoaded: true,
          expanded: true
        };
      } catch (error) {
        console.error('Error loading subfolders for sync:', error);
        return { ...node, selected: node.selected ?? false };
      }
    }
    return { ...node, selected: node.selected ?? false };
  };

  // --- Navigation & Core Logic ---
  const navigate = async (folderName: string, folderPath: string, isHistoryNav = false) => {
    try {
      let rawContent = await generateDirectoryContent(folderName, folderPath);
      
      // Filter invalid names (starting with special chars)
      // Allowed: Letters, Numbers, Korean (and let's allow space for 'New Folder')
      // Regex: Starts with alphanumeric or Korean. 
      // We'll exclude ., _, $, [ which are typical special chars to hide
      const isValidName = (name: string) => /^[a-zA-Z0-9가-힣]/.test(name);
      rawContent = rawContent.filter(item => isValidName(item.name));

      // Sort: Folders first, then files
      rawContent.sort((a, b) => {
        if (a.type === 'folder' && b.type !== 'folder') return -1;
        if (a.type !== 'folder' && b.type === 'folder') return 1;
        return a.name.localeCompare(b.name);
      });

      // 파일들의 인덱싱 여부 확인
      const filePaths = rawContent
        .filter(item => item.type !== 'folder' && item.path)
        .map(item => item.path!);
      
      if (filePaths.length > 0) {
        try {
          const indexedStatus = await BackendAPI.checkFilesIndexed(filePaths);
          
          // 각 파일에 인덱싱 여부 추가
          rawContent = rawContent.map(item => {
            if (item.type !== 'folder' && item.path) {
              return {
                ...item,
                indexed: indexedStatus[item.path] || false
              };
            }
            return item;
          });
        } catch (error) {
          console.error('인덱싱 여부 확인 오류:', error);
          // 오류 발생 시 indexed 필드 없이 진행
        }
      }

      let newHistory = activeTab.history;
      let newIndex = activeTab.historyIndex;

      if (!isHistoryNav) {
        newHistory = activeTab.history.slice(0, activeTab.historyIndex + 1);
        newHistory.push({ name: folderName, path: folderPath });
        newIndex = newHistory.length - 1;
      }

      updateActiveTab({ 
        selectedFolder: folderName, 
        currentPath: folderPath,
        title: folderName,
        files: rawContent,
        selectedFile: null,
        searchText: '',
        history: newHistory,
        historyIndex: newIndex
      });

      // 폴더 트리 동기화 (경로 펼치기 및 선택) - 비동기 처리
      await syncFolderTreeWithPath(folderPath);

      // 폴더 이동 로그는 표시하지 않음 (너무 자주 발생)
    } catch (error) {
      console.error('Navigation error:', error);
      addSearchLog(`❌ 탐색 오류: ${folderPath}`);
    }
  };

  const handleBack = async () => {
    if (activeTab.historyIndex > 0) {
      const newIndex = activeTab.historyIndex - 1;
      const prev = activeTab.history[newIndex];
      
      try {
        let rawContent = await generateDirectoryContent(prev.name, prev.path);
        
        // Filter invalid names
        const isValidName = (name: string) => /^[a-zA-Z0-9가-힣]/.test(name);
        rawContent = rawContent.filter(item => isValidName(item.name));
        
        // Sort: Folders first, then files
        rawContent.sort((a, b) => {
          if (a.type === 'folder' && b.type !== 'folder') return -1;
          if (a.type !== 'folder' && b.type === 'folder') return 1;
          return a.name.localeCompare(b.name);
        });
        
        updateActiveTab({ 
          selectedFolder: prev.name, 
          currentPath: prev.path,
          title: prev.name,
          files: rawContent,
          selectedFile: null,
          searchText: '',
          historyIndex: newIndex
        });
        
        // 폴더 트리 동기화
        await syncFolderTreeWithPath(prev.path);
        
        // 히스토리 이동 로그는 표시하지 않음
      } catch (error) {
        console.error('Back navigation error:', error);
        addSearchLog(`❌ 뒤로 이동 오류: ${prev.path}`);
      }
    }
  };

  const handleForward = async () => {
    if (activeTab.historyIndex < activeTab.history.length - 1) {
      const newIndex = activeTab.historyIndex + 1;
      const next = activeTab.history[newIndex];
      
      try {
        let rawContent = await generateDirectoryContent(next.name, next.path);
        
        // Filter invalid names
        const isValidName = (name: string) => /^[a-zA-Z0-9가-힣]/.test(name);
        rawContent = rawContent.filter(item => isValidName(item.name));
        
        // Sort: Folders first, then files
        rawContent.sort((a, b) => {
          if (a.type === 'folder' && b.type !== 'folder') return -1;
          if (a.type !== 'folder' && b.type === 'folder') return 1;
          return a.name.localeCompare(b.name);
        });
        
        updateActiveTab({ 
          selectedFolder: next.name, 
          currentPath: next.path,
          title: next.name,
          files: rawContent,
          selectedFile: null,
          searchText: '',
          historyIndex: newIndex
        });
        
        // 폴더 트리 동기화
        await syncFolderTreeWithPath(next.path);
        
        // 히스토리 이동 로그는 표시하지 않음
      } catch (error) {
        console.error('Forward navigation error:', error);
        addSearchLog(`❌ 앞으로 이동 오류: ${next.path}`);
      }
    }
  };

  // --- Indexing Functions ---
  const getSelectedDirectory = (): string | null => {
    // 1순위: 파일 목록(파일 트리)에서 선택된 디렉토리 (폴더만)
    if (activeTab.selectedFile && activeTab.selectedFile.type === 'folder' && activeTab.selectedFile.path) {
      return activeTab.selectedFile.path;
    }

    // 2순위: 즐겨찾기에서 선택된 항목
    // 즐겨찾기를 클릭하면 activeTab.selectedFolder와 currentPath가 설정됨
    // FAVORITES 배열에 포함된 경로인지 확인
    if (activeTab.currentPath) {
      const isFavorite = FAVORITES.some(fav => fav.path === activeTab.currentPath);
      if (isFavorite) {
        return activeTab.currentPath;
      }
    }

    // 3순위: 폴더 트리에서 선택된 디렉토리
    const findSelectedInTree = (nodes: FolderNode[]): string | null => {
      for (const node of nodes) {
        if (node.selected && node.path) {
          return node.path;
        }
        if (node.children) {
          const found = findSelectedInTree(node.children);
          if (found) return found;
        }
      }
      return null;
    };

    const selectedFromTree = findSelectedInTree(folderStructure);
    if (selectedFromTree) return selectedFromTree;

    // 4순위: 현재 탭의 경로 사용 (즐겨찾기나 폴더 트리가 아닌 경우)
    if (activeTab.currentPath) {
      return activeTab.currentPath;
    }

    return null;
  };

  const handleIndexStart = async () => {
    const selectedDir = getSelectedDirectory();
    
    if (!selectedDir) {
      addIndexingMessage('인덱싱 시작 실패: 디렉토리가 선택되지 않았습니다');
      return;
    }

    try {
      setIsIndexing(true);
      setIndexingStatus('인덱싱 시작 중...');
      addIndexingMessage(`인덱싱 시작: ${selectedDir}`);
      
      const response = await BackendAPI.startIndexing([selectedDir]);
      
      if (response.status === 'started') {
        setIndexingStatus('인덱싱 진행 중...');
        addIndexingMessage('인덱싱이 시작되었습니다');
        
        // 주기적으로 상태 및 로그 확인 (Throttling + AbortController)
        const statusInterval = setInterval(async () => {
          try {
            // 1. 상태 조회 (이전 요청 취소)
            if (statusAbortControllerRef.current) {
              statusAbortControllerRef.current.abort();
            }
            statusAbortControllerRef.current = new AbortController();
            
            const status = await BackendAPI.getIndexingStatus();
            setIndexingStats(status.stats);
            
            // 2. DB 통계 업데이트 (이전 요청 취소)
            try {
              if (statsAbortControllerRef.current) {
                statsAbortControllerRef.current.abort();
              }
              statsAbortControllerRef.current = new AbortController();
              
              const stats = await BackendAPI.getStatistics();
              setDbTotalCount(stats.total_indexed_files);
            } catch (error) {
              if (error.name !== 'AbortError') {
                console.error('통계 조회 오류:', error);
              }
            }
            
            // 3. 로그 가져오기 (이전 요청 취소)
            try {
              if (logsAbortControllerRef.current) {
                logsAbortControllerRef.current.abort();
              }
              logsAbortControllerRef.current = new AbortController();
              
              const logsResponse = await BackendAPI.getIndexingLogs(100);
              if (logsResponse.logs && logsResponse.logs.length > 0) {
                const mappedLogs = logsResponse.logs.map(log => ({
                  time: log.time,
                  path: log.path || log.filename,  // 전체 경로 사용
                  filename: log.filename,           // 파일명도 저장
                  status: log.status,
                  size: log.detail
                }));
                setIndexingLog(mappedLogs);
              }
            } catch (error) {
              if (error.name !== 'AbortError') {
                console.error('로그 조회 오류:', error);
              }
            }
            
            if (!status.is_running) {
              clearInterval(statusInterval);
              setIsIndexing(false);
              
              // AbortController 정리
              statusAbortControllerRef.current = null;
              logsAbortControllerRef.current = null;
              statsAbortControllerRef.current = null;
              
              // 재시도 워커 상태 표시
              if (status.retry_worker?.is_running && status.retry_worker.pending_files > 0) {
                setIndexingStatus(`대기 중 (재시도 ${status.retry_worker.pending_files}개)`);
                addIndexingMessage(`인덱싱 완료: 총 ${status.stats.indexed_files}개 파일`);
                addIndexingMessage(`재시도 워커 시작: Skip된 ${status.retry_worker.pending_files}개 파일 ${Math.floor(status.retry_worker.interval_seconds / 60)}분마다 재시도`);
              } else {
                setIndexingStatus('대기 중...');
                addIndexingMessage(`인덱싱 완료: 총 ${status.stats.indexed_files}개 파일`);
              }
            } else {
              setIndexingStatus(`인덱싱 중... (${status.stats.indexed_files}/${status.stats.total_files})`);
            }
          } catch (error) {
            if (error.name !== 'AbortError') {
              console.error('인덱싱 상태 확인 오류:', error);
            }
          }
        }, 1000); // 1초마다 상태 확인 (Throttling)
        
      } else {
        throw new Error(response.message || '색인 시작 실패');
      }
    } catch (error) {
      console.error('인덱싱 시작 오류:', error);
      addIndexingMessage(`인덱싱 오류: ${error}`);
      setIsIndexing(false);
      setIndexingStatus('대기 중...');
    }
  };

  const handleIndexStop = async () => {
    try {
      setIsIndexStopping(true);
      addIndexingMessage('인덱싱 중지 요청...');
      
      await BackendAPI.stopIndexing();
      
      // 백엔드 마무리 작업이 완료될 때까지 대기 (상태 폴링)
      addIndexingMessage('마무리 중...');
      
      const checkStopComplete = async () => {
        try {
          const status = await BackendAPI.getIndexingStatus();
          if (!status.is_running) {
            // 마무리 완료
            setIsIndexing(false);
            setIsIndexStopping(false);
            setIndexingStatus('중지됨');
            addIndexingMessage('✓ 인덱싱이 중지되었습니다');
            
            setTimeout(() => {
              setIndexingStatus('대기 중...');
            }, 2000);
          } else {
            // 아직 마무리 중 - 1초 후 재시도
            setTimeout(checkStopComplete, 1000);
          }
        } catch (error) {
          console.error('상태 확인 오류:', error);
          setIsIndexing(false);
          setIsIndexStopping(false);
          setIndexingStatus('중지됨 (오류)');
        }
      };
      
      // 폴링 시작
      setTimeout(checkStopComplete, 500);
      
    } catch (error) {
      console.error('인덱싱 중지 오류:', error);
      addIndexingMessage(`인덱싱 중지 오류: ${error}`);
      setIsIndexStopping(false);
    }
  };

  // --- File Actions ---
  const handleNewFolder = () => {
    const base = "새 폴더";
    let name = base;
    let i = 2;
    while (activeTab.files.some(f => f.name === name)) name = `${base} (${i++})`;
    
    const newFolder: FileItem = { 
      name, 
      size: '', 
      date: new Date().toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }), 
      type: 'folder', 
      path: `${activeTab.currentPath}\\${name}` 
    };
    const newFiles = [newFolder, ...activeTab.files].sort((a, b) => (a.type === 'folder' && b.type !== 'folder' ? -1 : 1));
    updateActiveTab({ files: newFiles });
    addSearchLog(`새 폴더 생성: ${name}`);
  };

  const handleCopy = () => {
    if (activeTab.selectedFile) {
      setClipboard(activeTab.selectedFile);
      addSearchLog(`클립보드 복사: ${activeTab.selectedFile.name}`);
    }
  };

  const handlePaste = () => {
    if (!clipboard) return;
    let name = clipboard.name;
    let i = 2;
    // Simple dedupe for same directory paste
    while (activeTab.files.some(f => f.name === name)) {
      const parts = clipboard.name.split('.');
      if (clipboard.type !== 'folder' && parts.length > 1) {
        const ext = parts.pop();
        name = `${parts.join('.')} - 복사본 (${i++}).${ext}`;
      } else {
        name = `${clipboard.name} - 복사본 (${i++})`;
      }
    }
    const newFile = { 
      ...clipboard, 
      name, 
      date: new Date().toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }) 
    };
    const newFiles = [newFile, ...activeTab.files].sort((a, b) => (a.type === 'folder' && b.type !== 'folder' ? -1 : 1));
    updateActiveTab({ files: newFiles });
    addSearchLog(`붙여넣기: ${name}`);
  };

  const handleRefresh = async () => {
    if (!activeTab.currentPath) return;
    try {
      addSearchLog('📁 파일 목록 새로고침 중...');
      await navigate(activeTab.selectedFolder || '현재 폴더', activeTab.currentPath);
      addSearchLog('✅ 새로고침 완료');
    } catch (err) {
      console.error('새로고침 실패:', err);
      addSearchLog('❌ 새로고침 실패');
    }
  };

  const handleRename = () => {
    if (!activeTab.selectedFile) return;
    const oldName = activeTab.selectedFile.name;
    const newName = prompt("새 이름을 입력하세요:", oldName);
    if (newName && newName !== oldName) {
      const updatedFiles = activeTab.files.map(f => f.name === oldName ? { ...f, name: newName } : f);
      updateActiveTab({ files: updatedFiles, selectedFile: { ...activeTab.selectedFile, name: newName } });
      addSearchLog(`이름 변경: ${oldName} -> ${newName}`);
    }
  };

  const handleDelete = () => {
    if (!activeTab.selectedFile) return;
    setDeleteDialog({ isOpen: true, item: activeTab.selectedFile });
  };

  const confirmDelete = () => {
    if (deleteDialog.item) {
      const newFiles = activeTab.files.filter(f => f.name !== deleteDialog.item?.name);
      updateActiveTab({ files: newFiles, selectedFile: null });
      addSearchLog(`삭제됨: ${deleteDialog.item.name}`);
      setDeleteDialog({ isOpen: false, item: null });
    }
  };

  // --- Sort & Search ---
  const handleSort = (key: keyof FileItem) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (activeTab.sortConfig.key === key && activeTab.sortConfig.direction === 'asc') direction = 'desc';
    
    const sorted = [...activeTab.files].sort((a, b) => {
      // Always keep folders on top
      if (a.type === 'folder' && b.type !== 'folder') return -1;
      if (a.type !== 'folder' && b.type === 'folder') return 1;

      if (key === 'size') {
        const valA = parseFloat(a.size) || 0;
        const valB = parseFloat(b.size) || 0; // Simple mock parse
        return (valA - valB) * (direction === 'asc' ? 1 : -1);
      }
      return (a[key]?.toString() || '').localeCompare(b[key]?.toString() || '') * (direction === 'asc' ? 1 : -1);
    });
    updateActiveTab({ files: sorted, sortConfig: { key, direction } });
  };

  const handleSearch = async () => {
    if (isSearching) return;
    
    const searchTerm = activeTab.searchText;
    if (!searchTerm || searchTerm.trim() === '') {
      addSearchLog(`⚠️ 검색어를 입력하세요`);
      return;
    }
    
    setIsSearching(true);
    
    // 검색 타입 감지
    const isExactMatch = searchTerm.startsWith('"') && searchTerm.endsWith('"');
    const searchTerms = searchTerm.split(' ').filter(t => t.trim());
    const isMultiWord = !isExactMatch && searchTerms.length > 1;
    
    let searchType = '';
    if (isExactMatch) {
      searchType = '정확한 문장 일치';
    } else if (isMultiWord) {
      searchType = `복합 검색 (${searchTerms.length}개 단어 모두 포함)`;
    } else {
      searchType = '단일 단어 포함';
    }
    
    // 로딩 시작 로그
    addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    addSearchLog(`⏳ 검색 준비 중...`);
    addSearchLog(`   검색어: "${searchTerm}"`);
    addSearchLog(`   검색 타입: ${searchType}`);
    
    // 0.5초 지연 (로딩 효과)
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 검색 시작 로그
    addSearchLog(`🔍 검색 시작: "${searchTerm}"`);
    addSearchLog(`검색 범위: ${activeTab.currentPath}`);
    addSearchLog(`대상: 인덱스 DB (최우선) + 윈도우 파일시스템`);
    addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    
    // 검색 히스토리 저장
    setSearchHistory(prev => [searchTerm, ...prev.filter(t => t !== searchTerm)].slice(0, 10));
    
    try {
      // 백엔드 검색 API 호출
      addSearchLog(`📡 백엔드 검색 엔진에 요청 중...`);
      
      const searchPath = searchOptions.subfolder ? activeTab.currentPath : undefined;
      const response = await BackendAPI.searchCombined(searchTerm, searchPath, 100);
      
      addSearchLog(`✓ 검색 쿼리 파싱 완료`);
      addSearchLog(`📂 DB에서 파일 검색 중...`);
      
      const results: BackendAPI.SearchResult[] = response.results || [];
      
      if (results.length === 0) {
        addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        addSearchLog(`⚠️ 검색 결과 없음`);
        addSearchLog(`   검색어: "${searchTerm}"`);
        addSearchLog(`   힌트: 먼저 색인을 시작하여 파일을 인덱싱하세요`);
        addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        updateActiveTab({ files: [] });
        setIsSearching(false);
        return;
      }
      
      // 각 파일의 매칭 정보 표시 및 통계 집계
      let totalMatches = 0;
      let filenameMatchCount = 0;
      let contentMatchCount = 0;
      
      results.forEach((result, index) => {
        // 매칭 수 계산 (rank를 기반으로 추정)
        const matchCount = result.highlight ? result.highlight.length : 0;
        totalMatches += matchCount;
        
        // source 필드로 파일명/내용 매칭 카운트
        if (result.source === 'filesystem') {
          filenameMatchCount++;
        } else if (result.source === 'database') {
          contentMatchCount++;
        }
        
        setTimeout(() => {
          const fileName = result.name;
          // source 필드로 정확한 매칭 유형 표시
          let matchInfo = '';
          if (result.source === 'filesystem') {
            matchInfo = '파일명 매칭';
          } else if (result.source === 'database') {
            matchInfo = matchCount > 0 ? `내용 ${matchCount}개 매칭` : '내용 매칭';
          } else {
            // source가 없는 경우 (하위 호환성)
            matchInfo = matchCount > 0 ? `${matchCount}개 매칭` : '매칭';
          }
          addSearchLog(`  ✓ ${fileName} - ${matchInfo}`);
        }, 50 * (index + 1));
      });
      
      // 검색 완료 로그
      setTimeout(() => {
        addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        addSearchLog(`✅ 검색 완료!`);
        if (contentMatchCount > 0) {
          addSearchLog(`   내용 매칭: 총 ${contentMatchCount}개 발견`);
        }
        if (filenameMatchCount > 0) {
          addSearchLog(`   파일명 매칭: 총 ${filenameMatchCount}개 발견`);
        }
        addSearchLog(`   검색 시간: ${(response.search_time || 0).toFixed(2)}초`);
        addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        
        // 파일 리스트 업데이트
        const fileItems: FileItem[] = results.map(result => ({
          name: result.name,
          size: result.size ? `${(result.size / 1024).toFixed(1)} KB` : '-',
          date: result.mtime ? new Date(result.mtime).toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
          }) : '-',
          type: result.extension || 'file',
          path: result.path,
          indexed: result.indexed || false  // 인덱싱 여부 추가
        }));
        
        updateActiveTab({ files: fileItems });
        setIsSearching(false);
      }, 50 * results.length + 200);
      
    } catch (error) {
      console.error('검색 오류:', error);
      addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      addSearchLog(`❌ 검색 실패: ${error}`);
      addSearchLog(`   백엔드 서버가 실행 중인지 확인하세요`);
      addSearchLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      setIsSearching(false);
    }
  };

  // --- Render Helpers ---
  // 폴더 확장 시 하위 디렉토리 동적 로드
  const loadSubfolders = async (node: FolderNode) => {
    if (node.childrenLoaded || !node.path) return;
    
    if (typeof window !== 'undefined' && (window as any).electronAPI) {
      try {
        const electronAPI = (window as any).electronAPI;
        const subdirs = await electronAPI.readDirectoriesOnly(node.path);
        
        // 특수 문자로 시작하는 폴더 필터링
        const validSubdirs = subdirs.filter((dir: any) => isValidName(dir.name));
        
        const updateNode = (list: FolderNode[]): FolderNode[] => 
          list.map(n => {
            if (n === node) {
              return {
                ...n,
                children: validSubdirs.map((dir: any) => ({
                  name: dir.name,
                  icon: 'Folder',
                  path: dir.path,
                  expanded: false,
                  selected: false,
                  children: [],
                  childrenLoaded: false
                })),
                childrenLoaded: true,
                expanded: true
              };
            }
            if (n.children) {
              return { ...n, children: updateNode(n.children) };
            }
            return n;
          });
        
        setFolderStructure(updateNode(folderStructure));
      } catch (error) {
        console.error('Error loading subfolders:', error);
      }
    }
  };

  const renderTree = (nodes: FolderNode[], level = 0) => {
    return nodes.filter(node => isValidName(node.name)).map((node, idx) => {
      // 경로는 노드에 저장된 path 사용
      const currentPath = node.path || node.name;

      const IconComp = ICON_MAP[node.icon] || Folder;
      const hasChildren = node.children && node.children.length > 0;
      
      return (
        <div key={idx}>
          <TreeItem 
            label={node.name} 
            IconComponent={IconComp} 
            expanded={node.expanded} 
            hasChildren={hasChildren || !node.childrenLoaded} 
            level={level}
            isSelected={node.selected || false}
            onClick={() => navigate(node.name, currentPath)}
            onContextMenu={(e) => { 
              e.preventDefault(); 
              setContextMenu({ 
                visible: true, 
                x: e.clientX, 
                y: e.clientY, 
                target: { name: node.name, path: currentPath, type: 'folder' } 
              }); 
            }}
            onToggle={async () => {
              if (!node.expanded && !node.childrenLoaded) {
                // 확장하면서 하위 폴더 로드
                await loadSubfolders(node);
              } else {
                // 단순 토글
                const toggle = (list: FolderNode[]): FolderNode[] => 
                  list.map(n => n === node ? { ...n, expanded: !n.expanded } : { ...n, children: n.children ? toggle(n.children) : undefined });
                setFolderStructure(toggle(folderStructure));
              }
            }}
          />
          {node.expanded && node.children && renderTree(node.children, level + 1)}
        </div>
      );
    });
  };

  // --- Context Menu Close ---
  useEffect(() => {
    const closeMenu = () => setContextMenu(p => ({ ...p, visible: false }));
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const canGoBack = activeTab.historyIndex > 0;
  const canGoForward = activeTab.historyIndex < activeTab.history.length - 1;
  const hasSelection = !!activeTab.selectedFile;

  return (
    <div className="flex flex-col h-screen w-full font-sans overflow-hidden select-none text-[12px]" style={{ backgroundColor: COLORS.windowBg, color: COLORS.textPrimary }}>
      <style>{`
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: ${COLORS.scrollbarTrack}; }
        ::-webkit-scrollbar-thumb { background: ${COLORS.scrollbarThumb}; border-radius: 5px; border: 2px solid ${COLORS.scrollbarTrack}; }
        ::-webkit-scrollbar-thumb:hover { background: ${COLORS.scrollbarThumbHover}; }
      `}</style>

      {/* --- Indexing Stopping Dialog --- */}
      {isIndexStopping && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-[350px] bg-[#202020] border border-[#444] rounded-lg shadow-2xl p-6 transform scale-100">
            <div className="flex flex-col items-center text-center">
              <div className="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center mb-4">
                <div className="animate-spin">
                  <Activity className="text-blue-500" size={32} />
                </div>
              </div>
              <h3 className="text-base font-bold text-white mb-2">마무리 중입니다</h3>
              <p className="text-sm text-gray-400">잠시만 기다려 주세요...</p>
              <p className="text-xs text-gray-500 mt-2">현재 처리 중인 파일을 완료하고 있습니다</p>
            </div>
          </div>
        </div>
      )}

      {/* --- Delete Dialog --- */}
      {deleteDialog.isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-[320px] bg-[#202020] border border-[#444] rounded-lg shadow-2xl p-4 transform scale-100">
            <div className="flex gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center shrink-0">
                <AlertTriangle className="text-red-500" size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">삭제 확인</h3>
                <p className="text-xs text-gray-400 mt-1">'{deleteDialog.item?.name}' 항목을 영구적으로 삭제하시겠습니까?</p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteDialog({ isOpen: false, item: null })} className="px-4 py-1.5 bg-[#333] hover:bg-[#444] rounded border border-[#555] text-white transition-colors active:scale-95 duration-100">취소</button>
              <button onClick={confirmDelete} className="px-4 py-1.5 bg-red-600 hover:bg-red-500 rounded text-white transition-colors active:scale-95 duration-100">삭제</button>
            </div>
          </div>
        </div>
      )}

      {/* --- Context Menu --- */}
      {contextMenu.visible && contextMenu.target && (
        <div className="fixed z-50 min-w-[200px] py-1 rounded-md shadow-2xl border flex flex-col bg-[#2D2D2D] border-[#444]" style={{ top: contextMenu.y, left: contextMenu.x }}>
          <div className="px-3 py-2 text-xs text-gray-500 border-b border-[#444] mb-1 truncate max-w-[250px]">{contextMenu.target.path}</div>
          
          {/* 인덱싱하기 (파일만) */}
          {contextMenu.target.type !== 'folder' && (
            <>
              <button 
                className="w-full text-left px-3 py-1.5 hover:bg-[#0067C0] hover:text-white flex items-center gap-2 group active:bg-[#005a9e] transition-colors duration-75" 
                onClick={async () => { 
                  const filePath = contextMenu.target!.path;
                  try {
                    addSearchLog(`인덱싱 시작: ${contextMenu.target!.name}`);
                    const result = await BackendAPI.indexSingleFile(filePath);
                    
                    if (result.success) {
                      addSearchLog(`✅ ${result.message}`);
                      
                      // 파일 리스트에서 해당 파일의 인덱싱 상태 업데이트
                      const updatedFiles = activeTab.files.map(f => 
                        f.path === filePath ? { ...f, indexed: true } : f
                      );
                      updateActiveTab({ files: updatedFiles });
                    } else {
                      addSearchLog(`❌ ${result.message}`);
                    }
                  } catch (error) {
                    addSearchLog(`❌ 인덱싱 오류: ${error}`);
                  }
                }}
              >
                <FileText size={14} className="text-gray-400 group-hover:text-white" /> 
                인덱싱하기
              </button>
              <div className="h-px bg-[#444] my-1"></div>
            </>
          )}
          
          <button className="w-full text-left px-3 py-1.5 hover:bg-[#0067C0] hover:text-white flex items-center gap-2 group active:bg-[#005a9e] transition-colors duration-75" onClick={() => { 
            const dirPath = contextMenu.target!.path.substring(0, contextMenu.target!.path.lastIndexOf('\\') + 1); 
            navigator.clipboard.writeText(dirPath); 
            addSearchLog(`경로 복사됨: ${dirPath}`); 
          }}>
            <Copy size={14} className="text-gray-400 group-hover:text-white" /> 경로 복사
          </button>
          <button className="w-full text-left px-3 py-1.5 hover:bg-[#0067C0] hover:text-white flex items-center gap-2 group active:bg-[#005a9e] transition-colors duration-75" onClick={() => { navigator.clipboard.writeText(contextMenu.target!.name); addSearchLog('이름 복사됨'); }}>
            <FileText size={14} className="text-gray-400 group-hover:text-white" /> 이름 복사
          </button>
        </div>
      )}

      {/* --- Tab Bar --- */}
      <div className="flex items-end h-[40px] px-2 pt-2 space-x-1 shrink-0 bg-[#121212] border-b border-[#2C2C2C]">
        {tabs.map(tab => (
          <div key={tab.id} onClick={() => setActiveTabId(tab.id)} className={`group relative flex items-center min-w-[150px] max-w-[240px] h-full px-3 rounded-t-lg cursor-pointer transition-colors border-t border-x ${tab.id === activeTabId ? 'bg-[#202020] text-white border-[#333] border-b-0 z-10' : 'bg-transparent text-[#AAA] hover:bg-[#1F1F1F] border-transparent hover:border-[#333] active:bg-[#252525]'}`}>
            <Folder size={14} className="mr-2 text-[#FBBF24]" fill="#FBBF24" fillOpacity={0.2} />
            <span className="truncate flex-1 mr-2 text-xs">{tab.title}</span>
            <div onClick={(e) => { e.stopPropagation(); if(tabs.length > 1) { const remain = tabs.filter(t=>t.id!==tab.id); setTabs(remain); if(tab.id===activeTabId) setActiveTabId(remain[remain.length-1].id); }}} className="p-0.5 rounded hover:bg-[#333] hover:text-red-400 opacity-0 group-hover:opacity-100 active:scale-90 transition-transform duration-100"><X size={12} /></div>
          </div>
        ))}
        <button onClick={() => { const id = nextTabId; setTabs([...tabs, { id, title: '문서', searchText: '', selectedFolder: '문서', currentPath: `${userHome}\\Documents`, selectedFile: null, files: [], sortConfig: {key:null, direction:'asc'}, history: [{name:'문서', path: `${userHome}\\Documents`}], historyIndex: 0 }]); setNextTabId(id+1); setActiveTabId(id); }} tabIndex={-1} className="flex items-center justify-center w-8 h-8 mb-1 rounded hover:bg-[#333] text-[#AAA] hover:text-white active:scale-90 transition-transform duration-100"><Plus size={16} /></button>
        <div className="flex-1 h-full" style={{ WebkitAppRegion: 'drag' } as any}></div>
      </div>

      {/* --- Top Container --- */}
      <div className="flex flex-col border-b h-[110px] shrink-0 bg-[#202020] border-[#444]">
        {/* Row 1: Search */}
        <div className="flex items-center p-3 space-x-3">
          <div className="relative w-[300px] z-50">
            <input 
              type="text" 
              placeholder="검색어를 입력하세요..." 
              className="w-full h-8 px-2 pl-3 bg-[#2C2C2C] border border-[#444] text-white focus:outline-none focus:border-[#0067C0] rounded-sm placeholder-gray-500"
              value={activeTab.searchText}
              onChange={(e) => updateActiveTab({ searchText: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              onFocus={() => setIsHistoryOpen(true)}
              onBlur={() => setTimeout(() => setIsHistoryOpen(false), 200)}
            />
            {isHistoryOpen && searchHistory.length > 0 && (
              <div className="absolute top-full left-0 w-full mt-1 bg-[#2D2D2D] border border-[#444] shadow-xl z-50 max-h-60 overflow-y-auto rounded-sm">
                {searchHistory.map((term, i) => (
                  <div key={i} className="flex justify-between px-3 py-2 hover:bg-[#0067C0] hover:text-white cursor-pointer group active:bg-[#005a9e]" onMouseDown={() => updateActiveTab({ searchText: term })}>
                    <span className="flex items-center gap-2 text-[#D0D0D0] group-hover:text-white"><Clock size={12}/> {term}</span>
                    <X size={12} className="text-gray-500 hover:text-red-300 active:scale-90" onMouseDown={(e) => { e.stopPropagation(); setSearchHistory(h => h.filter(t => t !== term)); }}/>
                  </div>
                ))}
              </div>
            )}
          </div>
          {/* Search Button with click effect */}
          <button onClick={handleSearch} disabled={isSearching} className={`flex items-center px-4 py-1.5 text-white border border-[#005A9E] rounded-sm active:scale-95 active:bg-[#005a9e] transition-all duration-100 ${isSearching ? 'bg-gray-600' : 'bg-[#0067C0] hover:bg-[#0078D7]'}`}>
            {isSearching ? <Activity size={14} className="animate-spin mr-1"/> : <Play size={14} className="mr-1" fill="currentColor"/>} 검색
          </button>
          <button onClick={() => { setIsSearching(false); addSearchLog('검색 중단됨'); }} className="flex items-center px-3 py-1.5 border border-[#444] bg-[#202020] text-[#D0D0D0] hover:bg-[#333] hover:text-white rounded-sm active:scale-95 transition-all duration-100">
            <Square size={14} className="mr-1" fill="currentColor"/> 중지
          </button>
          <div className="w-4" />
          <Checkbox label="내용 포함" checked={searchOptions.content} onChange={(v) => setSearchOptions(p => ({...p, content: v}))} />
          <Checkbox label="하위 폴더" checked={searchOptions.subfolder} onChange={(v) => setSearchOptions(p => ({...p, subfolder: v}))} />
        </div>

        {/* Row 2: Indexing & Filters */}
        <div className="flex items-center px-3 pb-3 space-x-3 justify-between">
          <div className="flex items-center space-x-3">
            <span className="font-bold text-[#D0D0D0]">색인:</span>
            <button 
              onClick={handleIndexStart} 
              disabled={isIndexing || isIndexStopping} 
              className={`flex items-center px-4 py-1.5 border rounded-sm transition-all duration-100 ${
                isIndexing || isIndexStopping
                  ? 'bg-[#333] text-[#666] border-[#444] cursor-not-allowed opacity-50' 
                  : 'bg-[#0067C0] text-white border-[#005A9E] hover:bg-[#0078D7] active:scale-95 active:bg-[#005a9e]'
              }`}>
              <Play size={14} className="mr-1" fill="currentColor"/> 시작
            </button>
            <button 
              onClick={handleIndexStop} 
              disabled={!isIndexing || isIndexStopping}
              className={`flex items-center px-3 py-1.5 border rounded-sm transition-all duration-100 ${
                !isIndexing || isIndexStopping
                  ? 'bg-[#202020] text-[#666] border-[#444] cursor-not-allowed opacity-50' 
                  : 'bg-[#DC2626] text-white border-[#991B1B] hover:bg-[#EF4444] active:scale-95 active:bg-[#B91C1C]'
              }`}>
              <Pause size={14} className="mr-1" fill="currentColor"/> 중지
            </button>
            <span className={`px-2 ${isIndexing ? 'text-[#0078D7]' : 'text-gray-500'}`}>{indexingStatus}</span>
            <span className="text-[#D0D0D0]">인덱싱 DB 저장 파일 수: {dbTotalCount.toLocaleString()} 개</span>
          </div>
          <div className="flex space-x-4">
            {['ppt', 'doc', 'hwp', 'txt', 'pdf', 'csv'].map(ext => (
              <Checkbox key={ext} label={ext} checked={typeFilters[ext]} onChange={(v) => setTypeFilters(p => ({...p, [ext]: v}))} />
            ))}
          </div>
        </div>
      </div>

      {/* --- Center Wrapper --- */}
      <div className="flex flex-col flex-grow overflow-hidden relative">
        <div className="flex flex-row flex-grow overflow-hidden" style={{ height: `calc(100% - ${layout.bottomPanelHeight}px)` }}>
          
          {/* Sidebar */}
          <div style={{ width: layout.sidebarWidth }} className="flex flex-col border-r border-[#444] bg-[#202020]">
            {/* Toolbar */}
            <div className="flex items-center p-1 space-x-1 border-b border-[#444] h-[36px] select-none">
              <div className="flex items-center space-x-0.5">
                <button onClick={handleBack} disabled={!canGoBack} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 active:bg-[#444] ${canGoBack ? 'text-[#D0D0D0] hover:bg-[#333]' : 'text-[#555]'}`} title="뒤로"><ArrowLeft size={16}/></button>
                <button onClick={handleForward} disabled={!canGoForward} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 active:bg-[#444] ${canGoForward ? 'text-[#D0D0D0] hover:bg-[#333]' : 'text-[#555]'}`} title="앞으로"><ArrowRight size={16}/></button>
              </div>
              <div className="w-px h-4 bg-[#444] mx-2" />
              <div className="flex items-center space-x-0.5">
                <button onClick={handleNewFolder} className="p-1.5 text-[#D0D0D0] rounded hover:bg-[#333] active:bg-[#444] active:scale-95 transition-transform duration-100" title="새 폴더"><FolderPlus size={16}/></button>
                <button onClick={handleCopy} disabled={!hasSelection} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 ${hasSelection ? 'text-[#D0D0D0] hover:bg-[#333]' : 'text-[#555]'}`} title="복사"><Copy size={16}/></button>
                <button onClick={handleRename} disabled={!hasSelection} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 ${hasSelection ? 'text-[#D0D0D0] hover:bg-[#333]' : 'text-[#555]'}`} title="이름 변경"><Edit2 size={16}/></button>
                <button onClick={handleDelete} disabled={!hasSelection} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 ${hasSelection ? 'text-[#D0D0D0] hover:bg-[#333] hover:text-red-400' : 'text-[#555]'}`} title="삭제"><Trash2 size={16}/></button>
                <button onClick={handlePaste} disabled={!clipboard} className={`p-1.5 rounded transition-transform duration-100 active:scale-95 ${clipboard ? 'text-[#D0D0D0] hover:bg-[#333]' : 'text-[#555]'}`} title="붙여넣기"><Clipboard size={16}/></button>
                <button onClick={handleRefresh} className="p-1.5 text-[#D0D0D0] rounded hover:bg-[#333] active:bg-[#444] active:scale-95 transition-transform duration-100" title="새로고침"><RefreshCw size={16}/></button>
              </div>
            </div>

            {/* Tree Area */}
            <div className="flex-1 flex flex-col min-h-0">
              {/* Favorites */}
              <div style={{ height: layout.favoritesHeight }} className="flex flex-col border-b border-[#444] min-h-0">
                <div className="flex items-center px-2 py-1.5 text-xs font-bold text-[#D0D0D0] bg-[#2C2C2C] border-b border-[#444]">
                  <Star size={12} className="mr-1.5 text-[#A855F7]" fill="#A855F7"/> 즐겨찾기
                </div>
                <div className="flex-1 overflow-y-auto min-h-0">
                  {FAVORITES.filter(fav => /^[a-zA-Z0-9가-힣]/.test(fav.name)).map((fav, i) => (
                    <TreeItem key={i} label={fav.name} IconComponent={fav.icon} isSelected={activeTab.selectedFolder === fav.name} onClick={() => navigate(fav.name, fav.path)} onContextMenu={(e) => { e.preventDefault(); setContextMenu({ visible: true, x: e.clientX, y: e.clientY, target: { name: fav.name, path: fav.path, type: 'folder' } }); }} />
                  ))}
                </div>
              </div>
              
              <Resizer direction="vertical" onResize={(d) => setLayout(p => ({ ...p, favoritesHeight: Math.max(50, p.favoritesHeight + d) }))} />
              
              {/* Folder Tree */}
              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex items-center px-2 py-1.5 text-xs font-bold text-[#D0D0D0] bg-[#2C2C2C] border-b border-[#444]">
                  <Folder size={12} className="mr-1.5 text-[#FBBF24]" fill="#FBBF24"/> 폴더 트리
                </div>
                <div className="flex-1 overflow-y-auto min-h-0">{renderTree(folderStructure)}</div>
              </div>
            </div>
          </div>
          <Resizer direction="horizontal" onResize={(d) => setLayout(p => ({ ...p, sidebarWidth: Math.max(150, p.sidebarWidth + d) }))} />

          {/* File List */}
          <div style={{ width: layout.fileListWidth }} className="flex flex-col border-r border-[#444] bg-[#202020]">
            {/* Header */}
            <div className="flex h-8 bg-[#202020] border-b border-[#444] text-[#D0D0D0]">
              <div style={{ width: colWidths.name }} className="pl-3 pr-2 flex items-center hover:bg-[#333] cursor-pointer text-xs border-r border-[#333333]" onClick={() => handleSort('name')}>이름 {activeTab.sortConfig.key === 'name' && (activeTab.sortConfig.direction === 'asc' ? <ArrowUp size={12}/> : <ArrowDown size={12}/>)}</div>
              <Resizer direction="horizontal" onResize={(d) => setColWidths(p => ({ ...p, name: Math.max(50, p.name + d) }))} />
              <div style={{ width: colWidths.size }} className="px-2 flex items-center justify-end hover:bg-[#333] cursor-pointer text-xs border-r border-[#333333]" onClick={() => handleSort('size')}>크기 {activeTab.sortConfig.key === 'size' && (activeTab.sortConfig.direction === 'asc' ? <ArrowUp size={12}/> : <ArrowDown size={12}/>)}</div>
              <Resizer direction="horizontal" onResize={(d) => setColWidths(p => ({ ...p, size: Math.max(50, p.size + d) }))} />
              <div style={{ width: colWidths.date }} className="px-2 flex items-center hover:bg-[#333] cursor-pointer text-xs flex-1" onClick={() => handleSort('date')}>수정한 날짜 {activeTab.sortConfig.key === 'date' && (activeTab.sortConfig.direction === 'asc' ? <ArrowUp size={12}/> : <ArrowDown size={12}/>)}</div>
            </div>
            {/* List */}
            <div className="flex-1 overflow-y-auto" onClick={() => updateActiveTab({ selectedFile: null })}>
              <div className="min-w-max">
                {activeTab.files.map((file, i) => {
                  const { Icon: FileIcon, color: iconColor } = getFileIconProps(file);
                  const isSelected = activeTab.selectedFile?.name === file.name;
                  return (
                    <div 
                      key={i} 
                      // 수평선(border-b) 제거
                      className={`flex h-7 items-center cursor-default text-xs active:bg-[#383838] transition-colors duration-75 ${isSelected ? 'bg-[#333] text-white' : 'text-[#D0D0D0] hover:bg-[#2A2A2A]'}`}
                      onClick={(e) => { e.stopPropagation(); updateActiveTab({ selectedFile: file }); }}
                      onDoubleClick={async () => {
                        if (file.type === 'folder') {
                          navigate(file.name, file.path || `...\\${file.name}`);
                        } else if (file.path) {
                          // 일반 파일 - 기본 프로그램으로 열기
                          if (typeof window !== 'undefined' && (window as any).electronAPI) {
                            try {
                              const result = await (window as any).electronAPI.openFile(file.path);
                              if (result.success) {
                                addSearchLog(`파일 열기: ${file.name}`);
                              } else {
                                addSearchLog(`파일 열기 실패: ${file.name} - ${result.error}`);
                              }
                            } catch (error) {
                              console.error('Error opening file:', error);
                              addSearchLog(`파일 열기 오류: ${file.name}`);
                            }
                          }
                        }
                      }}
                      onContextMenu={(e) => { e.preventDefault(); setContextMenu({ visible: true, x: e.clientX, y: e.clientY, target: { name: file.name, path: file.path || '', type: file.type } }); }}
                    >
                      <div style={{ width: colWidths.name }} className="pl-3 pr-2 flex items-center overflow-hidden border-r border-[#2a2a2a]">
                        <FileIcon size={14} className="mr-2 flex-shrink-0" style={{ color: iconColor }} />
                        <span className="truncate">{file.name}</span>
                        {file.indexed !== undefined && (
                          <span 
                            className="ml-2 flex-shrink-0" 
                            title={file.indexed ? "인덱싱 완료" : "인덱싱 안됨"}
                          >
                            {file.indexed ? (
                              <span className="text-green-400 text-[10px]">✓</span>
                            ) : (
                              <span className="text-gray-600 text-[10px]">○</span>
                            )}
                          </span>
                        )}
                      </div>
                      
                      {/* Resizer 공간 (4px - w-1과 동일) */}
                      <div className="w-1 h-full flex-shrink-0" />
                      
                      <div style={{ width: colWidths.size }} className="px-2 text-right text-gray-400 border-r border-[#2a2a2a]">{file.size}</div>
                      
                      {/* Resizer 공간 (4px - w-1과 동일) */}
                      <div className="w-1 h-full flex-shrink-0" />
                      
                      <div style={{ width: colWidths.date }} className="px-2 text-gray-400 flex-1">{file.date}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          <Resizer direction="horizontal" onResize={(d) => setLayout(p => ({ ...p, fileListWidth: Math.max(200, p.fileListWidth + d) }))} />

          {/* Right Panel (Preview) */}
          <div className="flex-1 flex flex-col bg-[#202020] min-w-[200px]">
            <div className="h-8 border-b border-[#444] bg-[#252525] flex items-center justify-between px-3">
              <span className="text-xs font-bold text-[#D0D0D0]">{showIndexingLog ? '인덱싱 DB 내역' : '내용 보기 및 편집'}</span>
              <button 
                onClick={async () => {
                  if (!showIndexingLog) {
                    // 인덱싱 보기로 전환 시 DB 조회
                    try {
                      const dbResponse = await BackendAPI.getIndexedDatabase(1000, 0);
                      setIndexedDatabase(dbResponse.files);
                      setDbTotalCount(dbResponse.total_count);
                    } catch (error) {
                      console.error('DB 조회 오류:', error);
                      addSearchLog('DB 조회 실패');
                    }
                  }
                  setShowIndexingLog(!showIndexingLog);
                }} 
                className="flex items-center gap-1 text-[11px] px-2 py-0.5 border border-[#444] rounded bg-[#333] text-gray-300 hover:text-white hover:bg-[#444] active:scale-95 transition-transform duration-100"
              >
                {showIndexingLog ? <FileText size={10}/> : <List size={10}/>}
                {showIndexingLog ? '미리보기' : '인덱싱 보기'}
              </button>
            </div>
            <div className="flex-1 p-4 overflow-auto text-[#D0D0D0] text-xs font-mono">
              {showIndexingLog ? (
                <div className="space-y-2">
                  <div className="flex justify-between items-center mb-3 pb-2 border-b border-[#444]">
                    <span className="text-sm font-bold text-[#0078D7]">
                      인덱싱 DB 조회 결과 (총 {dbTotalCount.toLocaleString()}개)
                    </span>
                    <span className="text-[10px] text-gray-500">
                      SELECT * FROM files_fts ORDER BY mtime DESC LIMIT 1000
                    </span>
                  </div>
                  
                  {indexedDatabase.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">
                      <div className="mb-2">인덱싱된 파일이 없습니다.</div>
                      <div className="text-[10px]">색인을 시작하여 파일을 인덱싱하세요.</div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {indexedDatabase.map((file, i) => (
                        <div key={i} className="border border-[#333] rounded p-2 hover:bg-[#252525] transition-colors">
                          <div className="flex items-start gap-2 mb-1">
                            <span className="text-[10px] text-gray-500 shrink-0">#{i + 1}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <FileText size={12} className="text-blue-400 shrink-0" />
                                <span className="text-[11px] text-[#0078D7] truncate font-semibold" title={file.path}>
                                  {file.path}
                                </span>
                              </div>
                              
                              <div className="grid grid-cols-3 gap-2 text-[10px] mb-2">
                                <div className="text-gray-400">
                                  <span className="text-gray-500">크기:</span> {file.content_length.toLocaleString()}자
                                </div>
                                <div className="text-gray-400">
                                  <span className="text-gray-500">토큰:</span> {Math.floor(file.content_length / 5).toLocaleString()}개 (추정)
                                </div>
                                <div className="text-gray-400">
                                  <span className="text-gray-500">수정:</span> {file.mtime_formatted}
                                </div>
                              </div>
                              
                              <div className="bg-[#1a1a1a] p-2 rounded border border-[#2a2a2a]">
                                <div className="text-[10px] text-gray-500 mb-1">내용 미리보기:</div>
                                <div className="text-[10px] text-gray-300 leading-relaxed whitespace-pre-wrap break-all">
                                  {file.content_preview}
                                  {file.content_length > 200 && <span className="text-gray-500">...</span>}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : fileContent ? (
                // 인덱싱 로그에서 클릭한 파일의 내용 표시
                <div className="h-full flex flex-col gap-2 p-3 bg-[#151515] border border-[#333] rounded">
                  <div className="text-sm text-gray-400 border-b border-[#333] pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="font-bold">인덱싱된 파일 내용</div>
                        <div className="text-xs mt-1 text-green-400">
                          ✓ 인덱싱 DB에서 불러온 내용
                        </div>
                      </div>
                      <button
                        onClick={handleSummarize}
                        disabled={isSummarizing}
                        className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs transition-all ${
                          isSummarizing 
                            ? 'bg-gray-600 text-gray-400 cursor-not-allowed' 
                            : 'bg-blue-600 hover:bg-blue-500 text-white active:scale-95'
                        }`}
                      >
                        {isSummarizing ? (
                          <>
                            <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent"></div>
                            요약 중...
                          </>
                        ) : (
                          <>
                            <FileText size={12} />
                            요약 생성
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  {/* 요약 결과 표시 */}
                  {fileSummary && (
                    <div className="bg-[#1a3a1a] border border-green-800 rounded p-3 mb-2">
                      <div className="flex items-center gap-2 mb-2 text-green-400 text-xs font-bold">
                        <FileText size={12} />
                        <span>📝 AI 요약 (TextRank)</span>
                      </div>
                      <pre className="text-xs text-green-200 whitespace-pre-wrap font-mono leading-relaxed" style={{ lineHeight: '1.8' }}>
                        {fileSummary}
                      </pre>
                    </div>
                  )}
                  
                  {/* 전체 내용 */}
                  <div className="flex-1 overflow-auto bg-[#1a1a1a] rounded p-3">
                    <div className="text-[10px] text-gray-500 mb-2">전체 내용:</div>
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono">
                      {fileContent}
                    </pre>
                  </div>
                </div>
              ) : (
                activeTab.selectedFile ? (
                  <div className="h-full">
                    {activeTab.selectedFile.type === 'folder' ? (
                      <div className="p-3 bg-[#151515] border border-[#333] rounded h-full">
                        폴더 내용 미리보기 불가
                      </div>
                    ) : imagePreview ? (
                      <div className="h-full flex flex-col gap-2 p-3 bg-[#151515] border border-[#333] rounded">
                        <div className="text-sm text-gray-400 border-b border-[#333] pb-2">
                          <div className="font-bold">{activeTab.selectedFile.name}</div>
                          <div className="text-xs mt-1">
                            크기: {activeTab.selectedFile.size} | 수정: {activeTab.selectedFile.date}
                          </div>
                        </div>
                        <div className="flex-1 overflow-auto flex items-center justify-center bg-[#1a1a1a] rounded">
                          <img 
                            src={imagePreview} 
                            alt={activeTab.selectedFile.name}
                            className="max-w-full max-h-full object-contain"
                            style={{ imageRendering: 'auto' }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="p-3 bg-[#151515] border border-[#333] rounded h-full flex flex-col items-center justify-center">
                        <AlertTriangle className="text-yellow-500 mb-3" size={48} />
                        <div className="text-sm text-gray-400 mb-2">
                          <div className="font-bold text-center">{activeTab.selectedFile.name}</div>
                          <div className="text-xs mt-1 text-center">
                            크기: {activeTab.selectedFile.size} | 수정: {activeTab.selectedFile.date}
                          </div>
                        </div>
                        <div className="text-yellow-400 text-sm font-semibold mt-4 text-center">
                          ⚠️ 이 파일은 아직 인덱싱되지 않았습니다
                        </div>
                        <div className="text-gray-500 text-xs mt-2 text-center max-w-md">
                          <div className="mb-2">이 파일의 내용을 보려면 먼저 인덱싱을 시작해야 합니다.</div>
                          <div className="text-yellow-300">💡 왼쪽 상단의 "색인" 탭에서 이 파일이 있는 폴더를 선택하고 "색인 시작" 버튼을 클릭하세요.</div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex h-full items-center justify-center text-gray-600">선택된 파일 없음</div>
                )
              )}
            </div>
          </div>
        </div>
        <Resizer direction="vertical" onResize={(d) => setLayout(p => ({ ...p, bottomPanelHeight: Math.max(50, p.bottomPanelHeight - d) }))} />

        {/* --- Bottom Panel --- */}
        <div style={{ height: layout.bottomPanelHeight }} className="flex bg-[#202020] border-t border-[#444]">
          {/* 왼쪽: Search Log */}
          <div style={{ width: layout.searchLogWidth }} className="flex flex-col border-r border-[#444]">
            <div className="px-2 py-1 text-xs font-bold text-[#AAA] bg-[#252525] border-b border-[#444] flex items-center gap-2">
              <Search size={12} />
              Search Log
              {searchLog.length > 1 && (
                <span className="px-1.5 py-0.5 bg-[#0078D7] text-white rounded text-[9px]">
                  {searchLog.length}
                </span>
              )}
            </div>
            <div className="flex-1 p-2 overflow-y-auto font-mono text-xs text-[#D0D0D0] space-y-0.5">
              {searchLog.map((log, i) => (
                <div key={i} className="flex items-center gap-1">
                  {i === 0 && <Search size={12} className="text-blue-400" />}
                  {log}
                </div>
              ))}
            </div>
          </div>
          
          <Resizer direction="horizontal" onResize={(d) => setLayout(p => ({ ...p, searchLogWidth: Math.max(100, p.searchLogWidth + d) }))} />
          
          {/* 오른쪽: Indexing Log */}
          <div className="flex flex-col flex-1">
            <div className="px-2 py-1 text-xs font-bold text-[#AAA] bg-[#252525] border-b border-[#444] flex items-center gap-2">
              <Activity size={12} />
              Indexing Log
              {indexingLog.length > 0 && (
                <span className="px-1.5 py-0.5 bg-[#0078D7] text-white rounded text-[9px]">
                  {indexingLog.length}
                </span>
              )}
            </div>
            <div className="flex-1 p-2 overflow-y-auto font-mono text-xs text-[#D0D0D0] space-y-1">
              {indexingLog.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <Activity size={24} className="mx-auto mb-2 opacity-50" />
                    <div>인덱싱 대기 중...</div>
                    <div className="text-[10px] mt-1">색인을 시작하면 진행 상황이 표시됩니다</div>
                  </div>
                </div>
              ) : (
                indexingLog.map((log, i) => {
                  // DB 저장 완료 여부 확인
                  const isDBSaved = log.size?.includes('✓ DB 저장 완료');
                  const isDBPending = log.size?.includes('⊗ DB 저장 대기');
                  // path가 있고 전체 경로인 경우만 클릭 가능 (특수 문자로 시작하지 않음)
                  const isClickable = isDBSaved && log.path && log.path.includes('\\') && !log.path.startsWith('📋') && !log.path.startsWith('⏸️') && !log.path.startsWith('▶️');
                  
                  // UI에는 파일명만 표시
                  const displayName = log.filename || log.path.split('\\').pop() || log.path;
                  
                  return (
                    <div 
                      key={i} 
                      className={`flex items-center gap-2 pb-1 border-b border-[#333] hover:bg-[#2a2a2a] ${isClickable ? 'cursor-pointer' : ''}`}
                      onClick={() => isClickable && handleIndexLogClick(log.path)}
                      title={isClickable ? `클릭하여 인덱스 내용 보기\n${log.path}` : log.path}
                    >
                      <span className="text-gray-500 shrink-0 text-[10px]">[{log.time}]</span>
                      <span className={`shrink-0 font-bold text-[10px] min-w-[80px] ${
                        log.status === 'Error' ? 'text-red-400' : 
                        log.status === 'Skip' || log.status === 'Skipped' ? 'text-yellow-400' : 
                        log.status === 'Indexing' ? 'text-blue-400' :
                        log.status === '파싱완료' ? 'text-cyan-400' :
                        log.status === 'Retry Success' ? 'text-cyan-400' :
                        log.status === 'Info' ? 'text-purple-400' :
                        'text-green-400'
                      }`}>
                        {log.status === 'Info' ? '📋' : 
                         log.status === 'Success' ? '✓ 완료' : 
                         log.status === '파싱완료' ? '✓ 파싱' :
                         log.status === 'Error' ? '✗' : 
                         log.status === 'Indexing' ? '⟳ 처리중' : 
                         log.status}
                      </span>
                      <span className={`flex-1 truncate text-white text-[10px] ${isClickable ? 'underline decoration-dotted' : ''}`} title={log.path}>
                        {displayName}
                      </span>
                      {log.size && (
                        <span className="shrink-0 text-gray-400 text-[9px]">
                          {log.size}
                        </span>
                      )}
                      {isDBSaved && (
                        <span className="shrink-0 text-green-400 text-[9px] font-bold bg-green-900/20 px-1.5 py-0.5 rounded">
                          ✓ DB완료
                        </span>
                      )}
                      {isDBPending && (
                        <span className="shrink-0 text-yellow-400 text-[9px] font-bold bg-yellow-900/20 px-1.5 py-0.5 rounded">
                          ⊗ DB대기
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}