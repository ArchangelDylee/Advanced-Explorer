const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// 개발 모드 감지
const isDev = !app.isPackaged;

// 설정 파일 로드
let config = null;
try {
  const configPath = path.join(__dirname, '../config.json');
  const configData = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(configData);
  console.log('✓ 설정 파일 로드 완료:', configPath);
  console.log('  - Python 가상환경:', config.python.pythonExecutable);
  console.log('  - 가상환경 필수:', config.python.requireVenv);
  console.log('  - 백엔드 자동 시작:', config.backend.autoStart);
} catch (error) {
  console.error('⚠ 설정 파일 로드 실패, 기본값 사용:', error.message);
  config = {
    python: {
      venvPath: 'python-backend/venv',
      pythonExecutable: 'python-backend/venv/Scripts/python.exe',
      backendPath: 'python-backend',
      serverScript: 'server.py',
      requireVenv: true,
      autoInstallDependencies: true
    },
    backend: {
      host: '127.0.0.1',
      port: 5000,
      autoStart: true
    },
    indexing: {
      enableActivityMonitor: true,
      idleThreshold: 3.0,
      maxFileSize: 104857600,
      parseTimeout: 60
    }
  };
}

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

// Python 백엔드 시작 (설정 파일 기반)
function startPythonBackend() {
  try {
    console.log('========================================');
    console.log('Python 백엔드 시작 (가상환경 사용)');
    console.log('========================================');
    
    const pythonBackendPath = path.join(__dirname, '..', config.python.backendPath);
    const pythonExe = path.join(__dirname, '..', config.python.pythonExecutable);
    const serverScript = path.join(pythonBackendPath, config.python.serverScript);
    
    console.log('  - 백엔드 경로:', pythonBackendPath);
    console.log('  - Python 실행 파일:', pythonExe);
    console.log('  - 서버 스크립트:', serverScript);
    
    // 가상환경 Python 확인
    if (!fs.existsSync(pythonExe)) {
      if (config.python.requireVenv) {
        console.error('❌ 가상환경 Python이 없습니다:', pythonExe);
        console.error('❌ 가상환경이 필수입니다. python-backend/venv를 설정하세요.');
        return null;
      } else {
        console.warn('⚠ 가상환경 Python이 없습니다. 시스템 Python을 사용합니다.');
      }
    } else {
      console.log('✓ 가상환경 Python 확인됨');
    }
    
    // 서버 스크립트 확인
    if (!fs.existsSync(serverScript)) {
      console.error('❌ Python 백엔드 스크립트가 없습니다:', serverScript);
      return null;
    }
    console.log('✓ 서버 스크립트 확인됨');
    
    // Python 실행 파일 결정
    const pythonCmd = fs.existsSync(pythonExe) ? pythonExe : 'python';
    
    if (pythonCmd === 'python') {
      console.warn('⚠ 시스템 Python을 사용합니다 (가상환경 아님)');
    } else {
      console.log('✓ 가상환경 Python 사용:', pythonCmd);
    }
    
    // Python 프로세스 시작 (UTF-8 인코딩 강제)
    pythonProcess = spawn(pythonCmd, [serverScript], {
      cwd: pythonBackendPath,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
        LANG: 'ko_KR.UTF-8',
        LC_ALL: 'ko_KR.UTF-8',
        // 설정 값 환경 변수로 전달
        ENABLE_ACTIVITY_MONITOR: config.indexing.enableActivityMonitor.toString(),
        IDLE_THRESHOLD: config.indexing.idleThreshold.toString(),
        MAX_FILE_SIZE: config.indexing.maxFileSize.toString(),
        PARSE_TIMEOUT: config.indexing.parseTimeout.toString()
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
    
    console.log('✓ Python 백엔드 시작 완료');
    console.log('========================================');
    return pythonProcess;
  } catch (error) {
    console.error('❌ Python 백엔드 시작 오류:', error);
    return null;
  }
}

// 앱이 준비되면 윈도우 생성
app.whenReady().then(() => {
  // 설정에 따라 Python 백엔드 자동 시작
  if (config.backend.autoStart) {
    // 개발 모드에서는 외부에서 Python을 실행하므로 자동 시작 비활성화
    if (!isDev) {
      startPythonBackend();
    } else {
      console.log('⚠ 개발 모드: Python 백엔드 자동 시작 건너뜀 (수동 실행 필요)');
    }
  } else {
    console.log('⚠ 설정에서 백엔드 자동 시작이 비활성화됨');
  }
  
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

// Python 프로세스 종료 함수 (재사용 가능)
async function terminatePythonProcess() {
  if (!pythonProcess) {
    return true; // 이미 종료됨
  }

  console.log('Python 백엔드 안전 종료 시작...');
  
  try {
    // 1. 백엔드 shutdown API 호출 (쓰레드 안전 종료)
    const http = require('http');
    
    await new Promise((resolve, reject) => {
      const shutdownTimeout = setTimeout(() => {
        console.warn('백엔드 종료 API 타임아웃 (5초)');
        reject(new Error('Shutdown API timeout'));
      }, 5000); // 5초 타임아웃
      
      const options = {
        hostname: '127.0.0.1',
        port: 5000,
        path: '/api/shutdown',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      };
      
      const req = http.request(options, (res) => {
        console.log(`백엔드 shutdown API 응답: ${res.statusCode}`);
        clearTimeout(shutdownTimeout);
        resolve();
      });
      
      req.on('error', (error) => {
        console.error('백엔드 shutdown API 호출 오류:', error.message);
        clearTimeout(shutdownTimeout);
        reject(error);
      });
      
      req.end();
    });
    
    console.log('✓ 백엔드 안전 종료 완료');
    
  } catch (error) {
    console.warn('백엔드 안전 종료 실패, 강제 종료 시도:', error.message);
  }
  
  // 2. Python 프로세스 강제 종료 (안전 종료 실패 시 대비)
  if (pythonProcess && !pythonProcess.killed) {
    console.log('Python 프로세스 강제 종료...');
    pythonProcess.kill('SIGTERM'); // 정상 종료 시그널
    
    // 1초 후에도 종료되지 않으면 SIGKILL
    await new Promise(resolve => {
      setTimeout(() => {
        if (pythonProcess && !pythonProcess.killed) {
          console.warn('Python 프로세스 SIGKILL로 강제 종료');
          pythonProcess.kill('SIGKILL');
        }
        resolve();
      }, 1000);
    });
  }
  
  pythonProcess = null;
  console.log('✓ Python 프로세스 종료 완료');
  return true;
}

// 앱 종료 전 Python 프로세스 안전하게 종료
let isQuitting = false; // 중복 종료 방지 플래그

app.on('before-quit', async (event) => {
  if (isQuitting) {
    return; // 이미 종료 진행 중
  }
  
  if (pythonProcess) {
    // 앱 종료를 일시 중단하고 백엔드를 안전하게 종료
    event.preventDefault();
    isQuitting = true;
    
    try {
      await terminatePythonProcess();
    } catch (error) {
      console.error('Python 프로세스 종료 오류:', error);
    }
    
    // 앱 종료 재개
    setTimeout(() => {
      console.log('앱 종료');
      app.quit();
    }, 1500); // 1.5초 대기 후 앱 종료
  }
});

// will-quit 이벤트 추가 (추가 안전장치)
app.on('will-quit', async (event) => {
  if (pythonProcess && !isQuitting) {
    console.log('will-quit: 백그라운드 프로세스 확인...');
    event.preventDefault();
    isQuitting = true;
    
    try {
      await terminatePythonProcess();
    } catch (error) {
      console.error('will-quit: Python 프로세스 종료 오류:', error);
    }
    
    setTimeout(() => {
      app.quit();
    }, 1000);
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

