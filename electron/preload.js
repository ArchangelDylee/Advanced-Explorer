const { contextBridge, ipcRenderer } = require('electron');

// 렌더러 프로세스에 안전한 API 노출
contextBridge.exposeInMainWorld('electronAPI', {
  getDrives: () => ipcRenderer.invoke('get-drives'),
  readDirectoriesOnly: (dirPath) => ipcRenderer.invoke('read-directories-only', dirPath),
  readDirectory: (dirPath) => ipcRenderer.invoke('read-directory', dirPath),
  getFileStats: (filePath) => ipcRenderer.invoke('get-file-stats', filePath),
  readImageFile: (filePath) => ipcRenderer.invoke('read-image-file', filePath),
  openFile: (filePath) => ipcRenderer.invoke('open-file', filePath),
  // 백엔드 Health Check 및 재시작
  checkBackendHealth: () => ipcRenderer.invoke('check-backend-health'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  // 파일 시스템 작업
  deleteFiles: (filePaths) => ipcRenderer.invoke('delete-files', filePaths),
  copyFiles: (filePaths, destPath) => ipcRenderer.invoke('copy-files', filePaths, destPath),
  renameFile: (oldPath, newName) => ipcRenderer.invoke('rename-file', oldPath, newName),
  platform: process.platform,
  isElectron: true
});
