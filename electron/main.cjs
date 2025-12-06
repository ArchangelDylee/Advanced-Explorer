const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// 개발 모드 감지
const isDev = !app.isPackaged;

let mainWindow;

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

// 앱이 준비되면 윈도우 생성
app.whenReady().then(() => {
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

