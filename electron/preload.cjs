const { contextBridge, ipcRenderer } = require('electron');

// 렌더러 프로세스에 안전한 API 노출
contextBridge.exposeInMainWorld('electronAPI', {
  getDrives: () => ipcRenderer.invoke('get-drives'),
  readDirectoriesOnly: (dirPath) => ipcRenderer.invoke('read-directories-only', dirPath),
  readDirectory: (dirPath) => ipcRenderer.invoke('read-directory', dirPath),
  getFileStats: (filePath) => ipcRenderer.invoke('get-file-stats', filePath),
  readImageFile: (filePath) => ipcRenderer.invoke('read-image-file', filePath),
  openFile: (filePath) => ipcRenderer.invoke('open-file', filePath),
  platform: process.platform,
  isElectron: true
});


