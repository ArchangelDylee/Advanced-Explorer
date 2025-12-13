const { app, BrowserWindow, ipcMain, shell, powerMonitor, globalShortcut } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const processControl = require('./processControl.cjs');

// UTF-8 인코딩 환경 변수 설정 (한글 처리)
if (process.platform === 'win32') {
  // Windows에서 콘솔 UTF-8 출력 강제
  process.env.PYTHONIOENCODING = 'utf-8';
  process.env.PYTHONUTF8 = '1';
  process.env.LANG = 'ko_KR.UTF-8';
  process.env.LC_ALL = 'ko_KR.UTF-8';
}

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
let pythonPid = null;

// 사용자 활동 모니터링 (Python Suspend/Resume용)
let userActivityMonitor = {
  lastActivityTime: Date.now(),
  isPythonSuspended: false,
  checkInterval: null,
  idleThreshold: 500 // 0.5초
};

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
  
  // 로드 에러 핸들링
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('페이지 로드 실패:', errorCode, errorDescription);
  });

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
      pythonPid = null;
    });
    
    // Python PID 저장 (Suspend/Resume용)
    pythonPid = pythonProcess.pid;
    console.log(`✓ Python 백엔드 시작 완료 (PID: ${pythonPid})`);
    console.log('========================================');
    
    // Python Suspend/Resume 모니터링 시작
    startPythonActivityMonitor();
    
    return pythonProcess;
  } catch (error) {
    console.error('❌ Python 백엔드 시작 오류:', error);
    return null;
  }
}

// Python Suspend/Resume을 위한 사용자 활동 모니터링
function startPythonActivityMonitor() {
  if (!pythonPid) {
    console.warn('⚠ Python PID가 없어 활동 모니터링을 시작할 수 없습니다');
    return;
  }
  
  console.log('========================================');
  console.log('🎮 Python Suspend/Resume 모니터링 시작');
  console.log(`  - Python PID: ${pythonPid}`);
  console.log(`  - 유휴 임계값: ${userActivityMonitor.idleThreshold}ms (0.5초)`);
  console.log('========================================');
  
  // 전역 키보드/마우스 이벤트 모니터링 (간접적 방법)
  // Electron은 전역 이벤트를 직접 감지할 수 없으므로 
  // 앱 내부 이벤트로 대리 감지
  if (mainWindow) {
    mainWindow.webContents.on('before-input-event', (event, input) => {
      onUserActivity();
    });
  }
  
  // 주기적으로 유휴 상태 체크 (50ms마다)
  userActivityMonitor.checkInterval = setInterval(() => {
    checkPythonSuspendResume();
  }, 50); // 매우 빠른 응답
  
  console.log('✓ Python 활동 모니터링 시작 완료');
}

function onUserActivity() {
  userActivityMonitor.lastActivityTime = Date.now();
  
  // Python이 실행 중이면 즉시 Suspend
  if (pythonPid && !userActivityMonitor.isPythonSuspended) {
    console.log('⏸️ 사용자 활동 감지 - Python Suspend');
    if (processControl.suspendProcess(pythonPid)) {
      userActivityMonitor.isPythonSuspended = true;
    }
  }
}

function checkPythonSuspendResume() {
  if (!pythonPid) return;
  
  const idleTime = Date.now() - userActivityMonitor.lastActivityTime;
  
  // 0.5초 이상 유휴 상태이고 Python이 Suspend 상태라면 Resume
  if (idleTime >= userActivityMonitor.idleThreshold && userActivityMonitor.isPythonSuspended) {
    console.log('▶️ 유휴 상태 감지 (0.5초) - Python Resume');
    if (processControl.resumeProcess(pythonPid)) {
      userActivityMonitor.isPythonSuspended = false;
    }
  }
}

function stopPythonActivityMonitor() {
  if (userActivityMonitor.checkInterval) {
    clearInterval(userActivityMonitor.checkInterval);
    userActivityMonitor.checkInterval = null;
  }
  
  // Python이 Suspend 상태라면 Resume
  if (pythonPid && userActivityMonitor.isPythonSuspended) {
    console.log('🔄 모니터링 중지 - Python Resume');
    processControl.resumeProcess(pythonPid);
    userActivityMonitor.isPythonSuspended = false;
  }
  
  console.log('✓ Python 활동 모니터링 중지 완료');
}

// 인덱싱 상태 저장 변수
let indexingStateBeforeSleep = null;

// ========================================
// 절전 모드 복귀 시 시스템 점검 헬퍼 함수
// ========================================

/**
 * Python 백엔드 Health Check
 * @returns {Promise<boolean>} 정상이면 true
 */
async function checkBackendHealth() {
  try {
    const response = await fetch('http://127.0.0.1:5000/api/health', {
      method: 'GET',
      timeout: 5000
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // 'ok'와 'degraded' 모두 허용 (서버가 응답하고 있으면 재시작 불필요)
      // 'degraded'는 일부 컴포넌트에 문제가 있지만 서버는 정상 작동 중
      if (data.status === 'ok') {
        return true;
      } else if (data.status === 'degraded') {
        console.warn('⚠️ 백엔드 상태: degraded (일부 컴포넌트 오류)');
        if (data.components) {
          Object.keys(data.components).forEach(component => {
            if (data.components[component].status === 'error') {
              console.warn(`  - ${component}: ${data.components[component].message || 'error'}`);
            }
          });
        }
        return true; // 서버는 응답 중이므로 재시작 불필요
      }
      return false;
    }
    return false;
  } catch (error) {
    console.error('❌ Health Check 실패:', error.message);
    return false;
  }
}

/**
 * 데이터베이스 연결 상태 확인
 * @returns {Promise<boolean>} 정상이면 true
 */
async function checkDatabaseConnection() {
  try {
    const response = await fetch('http://127.0.0.1:5000/api/statistics', {
      method: 'GET',
      timeout: 5000
    });
    
    if (response.ok) {
      const data = await response.json();
      // 응답에 total_files가 있으면 DB 조회 성공
      return typeof data.total_files !== 'undefined';
    }
    return false;
  } catch (error) {
    console.error('❌ DB 연결 확인 실패:', error.message);
    return false;
  }
}

/**
 * Python 백엔드 재시작
 * @returns {Promise<boolean>} 성공이면 true
 */
async function restartPythonBackend() {
  try {
    console.log('🔄 Python 백엔드 재시작 중...');
    
    // 기존 프로세스 종료
    if (pythonProcess) {
      pythonProcess.kill();
      pythonProcess = null;
      pythonPid = null;
      await sleep(1000);
    }
    
    // 새 프로세스 시작
    const newProcess = startPythonBackend();
    
    if (!newProcess) {
      return false;
    }
    
    // 시작 대기 (최대 10초)
    for (let i = 0; i < 10; i++) {
      await sleep(1000);
      const healthOk = await checkBackendHealth();
      if (healthOk) {
        console.log('✅ Python 백엔드 재시작 완료');
        return true;
      }
    }
    
    console.error('❌ Python 백엔드 재시작 후 응답 없음');
    return false;
    
  } catch (error) {
    console.error('❌ Python 백엔드 재시작 실패:', error);
    return false;
  }
}

/**
 * 지연 함수
 * @param {number} ms 밀리초
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Windows 절전 모드 감지 및 인덱싱 재개
function setupPowerMonitoring() {
  console.log('========================================');
  console.log('🔋 절전 모드 모니터링 시작');
  console.log('========================================');
  
  // 절전 모드 진입 (Suspend/Sleep/Dormant)
  powerMonitor.on('suspend', async () => {
    console.log('💤 시스템이 절전 모드로 진입합니다...');
    
    try {
      // 현재 인덱싱 상태 확인
      const response = await fetch('http://127.0.0.1:5000/api/indexing/status');
      const status = await response.json();
      
      if (status.is_running) {
        console.log('📌 인덱싱 진행 중 - 상태 저장');
        indexingStateBeforeSleep = {
          was_running: true,
          paths: status.target_paths || [],
          timestamp: new Date().toISOString()
        };
      } else {
        indexingStateBeforeSleep = null;
      }
    } catch (error) {
      console.error('❌ 절전 모드 진입 시 상태 저장 실패:', error);
      indexingStateBeforeSleep = null;
    }
  });
  
  // 절전 모드 복귀 (Resume)
  powerMonitor.on('resume', async () => {
    console.log('⚡ 시스템이 절전 모드에서 복귀했습니다');
    console.log('========================================');
    console.log('🔍 시스템 상태 점검 시작');
    console.log('========================================');
    
    // 약간의 지연 후 상태 확인 (시스템이 완전히 복귀할 시간 제공)
    setTimeout(async () => {
      try {
        // 1단계: Python 백엔드 Health Check
        console.log('1️⃣ Python 백엔드 상태 확인 중...');
        const healthOk = await checkBackendHealth();
        
        if (!healthOk) {
          console.error('❌ Python 백엔드 응답 없음 - 재시작 시도');
          const restarted = await restartPythonBackend();
          
          if (!restarted) {
            console.error('❌ Python 백엔드 재시작 실패 - 인덱싱 재개 불가');
            indexingStateBeforeSleep = null;
            return;
          }
          
          console.log('✅ Python 백엔드 재시작 완료');
          // 재시작 후 안정화 대기
          await sleep(2000);
        } else {
          console.log('✅ Python 백엔드 정상 작동 중');
        }
        
        // 2단계: DB 연결 상태 확인
        console.log('2️⃣ 데이터베이스 연결 상태 확인 중...');
        const dbOk = await checkDatabaseConnection();
        
        if (!dbOk) {
          console.error('❌ 데이터베이스 연결 오류 - 인덱싱 재개 불가');
          indexingStateBeforeSleep = null;
          return;
        }
        
        console.log('✅ 데이터베이스 연결 정상');
        
        // 3단계: 인덱싱 재개 (절전 전 실행 중이었다면)
        if (indexingStateBeforeSleep && indexingStateBeforeSleep.was_running) {
          console.log('3️⃣ 인덱싱 재개 중...');
          console.log('  - 중단 시각:', indexingStateBeforeSleep.timestamp);
          console.log('  - 인덱싱 경로:', indexingStateBeforeSleep.paths.join(', '));
          
          const response = await fetch('http://127.0.0.1:5000/api/indexing/start', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              paths: indexingStateBeforeSleep.paths
            })
          });
          
          if (response.ok) {
            console.log('✅ 인덱싱 재개 성공');
            console.log('========================================');
            
            // 윈도우에 알림 전송
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('indexing-resumed', {
                message: '절전 모드에서 복귀하여 인덱싱을 재개합니다',
                paths: indexingStateBeforeSleep.paths
              });
            }
          } else {
            console.error('❌ 인덱싱 재개 실패:', response.statusText);
          }
        } else {
          console.log('ℹ️ 복귀 전 인덱싱이 실행 중이 아니었습니다');
          console.log('========================================');
        }
        
      } catch (error) {
        console.error('❌ 절전 모드 복귀 처리 중 오류:', error);
      } finally {
        // 상태 초기화
        indexingStateBeforeSleep = null;
      }
    }, 3000); // 3초 대기
  });
  
  // 화면 잠금
  powerMonitor.on('lock-screen', () => {
    console.log('🔒 화면이 잠겼습니다');
  });
  
  // 화면 잠금 해제
  powerMonitor.on('unlock-screen', () => {
    console.log('🔓 화면 잠금이 해제되었습니다');
  });
  
  console.log('✓ 절전 모드 모니터링 활성화 완료');
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

  // Windows 절전 모드 감지 및 인덱싱 재개
  setupPowerMonitoring();

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
  
  // Python 활동 모니터링 중지
  stopPythonActivityMonitor();
  
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
    const directories = files
      .filter(file => file.isDirectory())
      .filter(file => /^[a-zA-Z0-9가-힣]/.test(file.name));
    
    // 접근 권한 체크
    const accessibleDirs = [];
    for (const file of directories) {
      const fullPath = path.join(dirPath, file.name);
      try {
        // 읽기 권한 확인
        await fs.access(fullPath, fs.constants.R_OK);
        accessibleDirs.push({
          name: file.name,
          path: fullPath
        });
      } catch (accessError) {
        // 접근 권한이 없으면 목록에 포함하지 않음
        console.debug(`Access denied: ${fullPath}`);
      }
    }
    
    return accessibleDirs;
  } catch (error) {
    console.error('Error reading directories:', error);
    return [];
  }
});

ipcMain.handle('read-directory', async (event, dirPath) => {
  const fs = require('fs').promises;
  try {
    const files = await fs.readdir(dirPath, { withFileTypes: true });
    
    // 접근 권한 체크
    const accessibleFiles = [];
    for (const file of files) {
      const fullPath = path.join(dirPath, file.name);
      try {
        // 읽기 권한 확인
        await fs.access(fullPath, fs.constants.R_OK);
        accessibleFiles.push({
          name: file.name,
          isDirectory: file.isDirectory(),
          path: fullPath
        });
      } catch (accessError) {
        // 접근 권한이 없으면 목록에 포함하지 않음
        console.debug(`Access denied: ${fullPath}`);
      }
    }
    
    return accessibleFiles;
  } catch (error) {
    console.error('Error reading directory:', error);
    return [];
  }
});

ipcMain.handle('get-file-stats', async (event, filePath) => {
  const fs = require('fs').promises;
  try {
    // 먼저 접근 권한 확인
    await fs.access(filePath, fs.constants.R_OK);
    
    const stats = await fs.stat(filePath);
    return {
      size: stats.size,
      modified: stats.mtime,
      created: stats.birthtime,
      isDirectory: stats.isDirectory()
    };
  } catch (error) {
    if (error.code === 'EACCES' || error.code === 'EPERM') {
      console.debug(`Access denied: ${filePath}`);
    } else {
      console.error('Error getting file stats:', error);
    }
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

// ========================================
// 백엔드 Health Check 및 재시작 IPC 핸들러
// ========================================

// 백엔드 상태 확인
ipcMain.handle('check-backend-health', async () => {
  try {
    console.log('🔍 백엔드 Health Check 요청됨...');
    const isHealthy = await checkBackendHealth();
    
    return {
      success: true,
      healthy: isHealthy,
      message: isHealthy ? 'Backend is healthy' : 'Backend is not responding'
    };
  } catch (error) {
    console.error('❌ Health Check 실행 오류:', error);
    return {
      success: false,
      healthy: false,
      error: error.message
    };
  }
});

// 백엔드 재시작
ipcMain.handle('restart-backend', async () => {
  try {
    console.log('🔄 백엔드 재시작 요청됨...');
    const restarted = await restartPythonBackend();
    
    if (restarted) {
      console.log('✅ 백엔드 재시작 완료');
      return {
        success: true,
        message: 'Backend restarted successfully'
      };
    } else {
      console.error('❌ 백엔드 재시작 실패');
      return {
        success: false,
        error: 'Failed to restart backend'
      };
    }
  } catch (error) {
    console.error('❌ 백엔드 재시작 오류:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// 파일/폴더 삭제 (휴지통으로)
ipcMain.handle('delete-files', async (event, filePaths) => {
  try {
    const results = [];
    for (const filePath of filePaths) {
      try {
        await shell.trashItem(filePath);
        console.log(`✅ 삭제 완료 (휴지통): ${filePath}`);
        results.push({ path: filePath, success: true });
      } catch (error) {
        console.error(`❌ 삭제 실패: ${filePath}`, error);
        results.push({ path: filePath, success: false, error: error.message });
      }
    }
    return { success: true, results };
  } catch (error) {
    console.error('파일 삭제 오류:', error);
    return { success: false, error: error.message };
  }
});

// 파일/폴더 복사
ipcMain.handle('copy-files', async (event, filePaths, destPath) => {
  const fs = require('fs').promises;
  const pathModule = require('path');
  
  try {
    const results = [];
    for (const srcPath of filePaths) {
      try {
        const fileName = pathModule.basename(srcPath);
        let destFilePath = pathModule.join(destPath, fileName);
        
        // 같은 이름의 파일이 있으면 (사본) 추가
        let counter = 1;
        const parsedPath = pathModule.parse(destFilePath);
        while (await fs.access(destFilePath).then(() => true).catch(() => false)) {
          destFilePath = pathModule.join(
            parsedPath.dir,
            `${parsedPath.name} (사본 ${counter})${parsedPath.ext}`
          );
          counter++;
        }
        
        // 파일인지 폴더인지 확인
        const stats = await fs.stat(srcPath);
        
        if (stats.isDirectory()) {
          // 폴더 복사 (재귀적)
          await copyDirectory(srcPath, destFilePath);
          console.log(`✅ 폴더 복사 완료: ${srcPath} → ${destFilePath}`);
        } else {
          // 파일 복사
          await fs.copyFile(srcPath, destFilePath);
          console.log(`✅ 파일 복사 완료: ${srcPath} → ${destFilePath}`);
        }
        
        results.push({ path: srcPath, success: true, dest: destFilePath });
      } catch (error) {
        console.error(`❌ 복사 실패: ${srcPath}`, error);
        results.push({ path: srcPath, success: false, error: error.message });
      }
    }
    return { success: true, results };
  } catch (error) {
    console.error('파일 복사 오류:', error);
    return { success: false, error: error.message };
  }
});

// 파일/폴더 이름 바꾸기
ipcMain.handle('rename-file', async (event, oldPath, newName) => {
  const fs = require('fs').promises;
  const pathModule = require('path');
  
  try {
    // 새 경로 생성 (같은 디렉토리 내에서 이름만 변경)
    const dirPath = pathModule.dirname(oldPath);
    const newPath = pathModule.join(dirPath, newName);
    
    // 같은 이름이면 무시
    if (oldPath === newPath) {
      return { success: true, message: '변경 사항 없음' };
    }
    
    // 이미 존재하는 이름인지 확인
    const exists = await fs.access(newPath).then(() => true).catch(() => false);
    if (exists) {
      return { success: false, error: '이미 존재하는 이름입니다' };
    }
    
    // 이름 변경
    await fs.rename(oldPath, newPath);
    console.log(`✅ 이름 변경 완료: ${oldPath} → ${newPath}`);
    
    return { success: true, oldPath, newPath };
  } catch (error) {
    console.error('이름 변경 오류:', error);
    return { success: false, error: error.message };
  }
});

// 재귀적 폴더 복사 헬퍼 함수
async function copyDirectory(src, dest) {
  const fs = require('fs').promises;
  const pathModule = require('path');
  
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  
  for (const entry of entries) {
    const srcPath = pathModule.join(src, entry.name);
    const destPath = pathModule.join(dest, entry.name);
    
    if (entry.isDirectory()) {
      await copyDirectory(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
}
