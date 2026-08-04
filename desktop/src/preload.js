const { contextBridge, ipcRenderer } = require('electron');

window.addEventListener('DOMContentLoaded', () => {
  document.documentElement.classList.add('autodiscovery-desktop');
});

contextBridge.exposeInMainWorld('autodiscoveryDesktop', {
  onBootstrapStatus(callback) {
    ipcRenderer.on('bootstrap-status', (_event, status) => callback(status));
  },
});