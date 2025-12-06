const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// 개발 모드 감지
const isDev = !app.isPackaged;

let mainWindow;
let pythonProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    backgroundColor: '#191919',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
    },
    frame: true,
    titleBarStyle: 'default',
    icon: path.join(__dirname, '../build/icon.ico'),
    show: false // 준비될 때까지 숨김
  });

  // 윈도우가 준비되면 표시
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // 개발 모드면 Vite 서버 주소로, 프로덕션이면 빌드된 파일로
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // 개발자 도구 자동 열기 (필요시 주석 해제)
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // 윈도우가 닫힐 때
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Python 백엔드 시작
function startPythonBackend() {
  try {
    const pythonBackendPath = path.join(__dirname, '../python-backend');
    const pythonExe = path.join(pythonBackendPath, 'venv/Scripts/python.exe');
    const serverScript = path.join(pythonBackendPath, 'server.py');
    
    // Python이 설치되어 있는지 확인
    const fs = require('fs');
    if (!fs.existsSync(serverScript)) {
      console.warn('Python 백엔드가 설치되지 않았습니다. 검색 기능이 제한됩니다.');
      return null;
    }
    
    // Python 프로세스 시작 (UTF-8 인코딩 강제)
    const pythonCmd = fs.existsSync(pythonExe) ? pythonExe : 'python';
    pythonProcess = spawn(pythonCmd, [serverScript], {
      cwd: pythonBackendPath,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',  // Python 입출력 UTF-8 강제
        PYTHONUTF8: '1',  // Python 3.7+ UTF-8 모드 활성화
        LANG: 'ko_KR.UTF-8',  // 로케일 설정
        LC_ALL: 'ko_KR.UTF-8'  // 전체 로케일 설정
      }
    });
    
    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python] ${data.toString('utf8').trim()}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data.toString('utf8').trim()}`);
    });
    
    pythonProcess.on('close', (code) => {
      console.log(`Python 백엔드 종료 (코드: ${code})`);
      pythonProcess = null;
    });
    
    console.log('Python 백엔드 시작됨');
    return pythonProcess;
  } catch (error) {
    console.error('Python 백엔드 시작 오류:', error);
    return null;
  }
}

// 앱이 준비되면 윈도우 생성
app.whenReady().then(() => {
  // Python 백엔드 시작
  startPythonBackend();
  
  createWindow();

  app.on('activate', () => {
    // macOS에서 독 아이콘 클릭 시 윈도우 재생성
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// 모든 윈도우가 닫히면 앱 종료 (macOS 제외)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 앱 종료 전 Python 프로세스 종료
app.on('before-quit', () => {
  if (pythonProcess) {
    console.log('Python 백엔드 종료 중...');
    pythonProcess.kill();
    pythonProcess = null;
  }
});

// 파일 시스템 접근 IPC 핸들러들
ipcMain.handle('get-drives', async () => {
  const fs = require('fs');
  
  try {
    if (process.platform === 'win32') {
      // Windows: A-Z 드라이브를 순회하며 존재하는 드라이브 찾기
      const drives = [];
      for (let i = 65; i <= 90; i++) { // A-Z
        const driveLetter = String.fromCharCode(i);
        const drivePath = `${driveLetter}:\\`;
        try {
          // 드라이브 존재 여부 확인
          if (fs.existsSync(drivePath)) {
            drives.push({
              name: `로컬 디스크 (${driveLetter}:)`,
              path: drivePath
            });
          }
        } catch (err) {
          // 접근 불가능한 드라이브는 무시
        }
      }
      return drives.length > 0 ? drives : [
        { name: '로컬 디스크 (C:)', path: 'C:\\' }
      ];
    }
  } catch (error) {
    console.error('Error getting drives:', error);
  }
  
  // 기본값 반환
  return [
    { name: '로컬 디스크 (C:)', path: 'C:\\' }
  ];
});

ipcMain.handle('read-directories-only', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    // 폴더만 필터링하고 특수 문자로 시작하는 폴더 제외
    return files
      .filter(file => file.isDirectory())
      .filter(file => /^[a-zA-Z0-9가-힣]/.test(file.name))
      .map(file => ({
        name: file.name,
        path: path.join(dirPath, file.name)
      }));
  } catch (error) {
    console.error('Error reading directories:', error);
    return [];
  }
});

ipcMain.handle('read-directory', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    return files.map(file => ({
      name: file.name,
      isDirectory: file.isDirectory(),
      path: path.join(dirPath, file.name)
    }));
  } catch (error) {
    console.error('Error reading directory:', error);
    return [];
  }
});

ipcMain.handle('get-file-stats', async (event, filePath) => {
  const fs = require('fs').promises;
  try {
    const stats = await fs.stat(filePath);
    return {
      size: stats.size,
      modified: stats.mtime,
      created: stats.birthtime,
      isDirectory: stats.isDirectory()
    };
  } catch (error) {
    console.error('Error getting file stats:', error);
    return null;
  }
});

ipcMain.handle('read-image-file', async (event, filePath) => {
  const fs = require('fs').promises;
  try {
    const data = await fs.readFile(filePath);
    const base64 = data.toString('base64');
    const ext = path.extname(filePath).toLowerCase();
    
    // MIME 타입 결정
    const mimeTypes = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.bmp': 'image/bmp',
      '.webp': 'image/webp',
      '.svg': 'image/svg+xml',
      '.ico': 'image/x-icon'
    };
    
    const mimeType = mimeTypes[ext] || 'image/jpeg';
    
    return {
      success: true,
      dataUrl: `data:${mimeType};base64,${base64}`
    };
  } catch (error) {
    console.error('Error reading image file:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// 파일을 기본 프로그램으로 열기
ipcMain.handle('open-file', async (event, filePath) => {
  try {
    const result = await shell.openPath(filePath);
    if (result) {
      // openPath는 에러가 있으면 에러 메시지를 반환, 없으면 빈 문자열
      console.error('Error opening file:', result);
      return {
        success: false,
        error: result
      };
    }
    return {
      success: true
    };
  } catch (error) {
    console.error('Error opening file:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

