const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('autodiscoveryDesktop', {
  onBootstrapStatus(callback) {
    ipcRenderer.on('bootstrap-status', (_event, status) => callback(status));
  },
});