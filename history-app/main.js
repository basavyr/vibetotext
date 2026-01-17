const { app, BrowserWindow, Tray, Menu, nativeImage, screen, globalShortcut } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const chokidar = require('chokidar');
const os = require('os');

console.log('Starting VibeToText app...');

// History file path
const HISTORY_PATH = path.join(os.homedir(), '.vibetotext', 'history.json');

let tray = null;
let mainWindow = null;
let watcher = null;
let devWatcher = null;
let pythonProcess = null;

// Get path to the Python engine binary
function getPythonEnginePath() {
  if (app.isPackaged) {
    // In production: binary is in Resources folder
    return path.join(process.resourcesPath, 'vibetotext-engine');
  } else {
    // In development: use the dist folder or run Python directly
    const distPath = path.join(__dirname, '..', 'dist', 'vibetotext-engine');
    if (fs.existsSync(distPath)) {
      return distPath;
    }
    // Fallback: not built yet
    return null;
  }
}

// Start the Python voice-to-text engine
function startPythonEngine() {
  const enginePath = getPythonEnginePath();

  if (!enginePath) {
    console.log('[ENGINE] Python engine not found. Run "npm run build:python" first.');
    console.log('[ENGINE] Or run Python directly: source .venv/bin/activate && python -m vibetotext');
    return;
  }

  console.log(`[ENGINE] Starting Python engine: ${enginePath}`);

  pythonProcess = spawn(enginePath, [], {
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[ENGINE] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[ENGINE ERROR] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[ENGINE] Python engine exited with code ${code}`);
    pythonProcess = null;
  });

  pythonProcess.on('error', (err) => {
    console.error(`[ENGINE] Failed to start Python engine: ${err.message}`);
    pythonProcess = null;
  });
}

// Stop the Python engine
function stopPythonEngine() {
  if (pythonProcess) {
    console.log('[ENGINE] Stopping Python engine...');
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
}

function createWindow() {
  // Get cursor position to show window near it
  const cursorPoint = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPoint);

  mainWindow = new BrowserWindow({
    width: 450,
    height: 600,
    x: Math.min(cursorPoint.x, display.bounds.x + display.bounds.width - 450),
    y: display.bounds.y + 50,
    frame: true,  // Show window frame with title bar
    titleBarStyle: 'hiddenInset',  // macOS style with traffic lights
    resizable: true,
    show: false,
    skipTaskbar: false,  // Show in taskbar/dock
    alwaysOnTop: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  mainWindow.loadFile('index.html');

  // Open dev tools with keyboard shortcut
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.meta && input.alt && input.key === 'i') {
      mainWindow.webContents.toggleDevTools();
    }
  });

  // Don't hide on blur - let user close manually
  // mainWindow.on('blur', () => {
  //   mainWindow.hide();
  // });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function toggleWindow() {
  if (mainWindow === null) {
    createWindow();
  }

  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    // Reposition near cursor
    const cursorPoint = screen.getCursorScreenPoint();
    const display = screen.getDisplayNearestPoint(cursorPoint);
    mainWindow.setPosition(
      Math.min(cursorPoint.x - 225, display.bounds.x + display.bounds.width - 450),
      display.bounds.y + 25
    );
    mainWindow.show();
    mainWindow.focus();
  }
}

function createTray() {
  // Create a minimal 16x16 PNG icon (required for Tray)
  // This is a simple microphone-style icon
  const iconData = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsTAAALEwEAmpwYAAAA' +
    'QklEQVQ4y2NgGAWjYBSMgsEDGBkZGf6TiRmJVfyfgYHhPxmYkVgF/8nBjIyMjAxEuoQBl0v+M5Dh' +
    'EmK9MApGwSgAAI6RBxHfOuHYAAAAAElFTkSuQmCC',
    'base64'
  );
  let icon = nativeImage.createFromBuffer(iconData);

  // Set as template image for macOS (adapts to light/dark mode)
  if (process.platform === 'darwin') {
    icon.setTemplateImage(true);
  }

  tray = new Tray(icon);

  // Also show text label on macOS for better visibility
  if (process.platform === 'darwin') {
    tray.setTitle(' VTT');
  }
  tray.setToolTip('VibeToText History');

  // Click to toggle window
  tray.on('click', () => {
    toggleWindow();
  });

  // Right-click menu
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show History', click: () => toggleWindow() },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() }
  ]);

  tray.setContextMenu(contextMenu);
}

function setupFileWatcher() {
  // Ensure directory exists
  const dir = path.dirname(HISTORY_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // Watch for changes to history file
  watcher = chokidar.watch(HISTORY_PATH, {
    persistent: true,
    ignoreInitial: true,
  });

  watcher.on('change', () => {
    if (mainWindow && mainWindow.isVisible()) {
      mainWindow.webContents.send('history-updated');
    }
  });
}

function setupDevHotReload() {
  // Watch UI source files for hot reload
  const filesToWatch = [
    path.join(__dirname, 'index.html'),
    path.join(__dirname, 'styles.css'),
    path.join(__dirname, 'renderer.js'),
    path.join(__dirname, 'analytics.js'),
  ];

  devWatcher = chokidar.watch(filesToWatch, {
    persistent: true,
    ignoreInitial: true,
  });

  devWatcher.on('change', (filePath) => {
    console.log(`[HOT RELOAD] ${path.basename(filePath)} changed, reloading...`);
    if (mainWindow) {
      mainWindow.webContents.reloadIgnoringCache();
    }
  });

  console.log('[HOT RELOAD] Watching UI files for changes');
}

// Single instance lock
console.log('Requesting single instance lock...');
const gotTheLock = app.requestSingleInstanceLock();
console.log('Got lock:', gotTheLock);
if (!gotTheLock) {
  console.log('Another instance is running, quitting...');
  app.quit();
} else {
  console.log('We have the lock, proceeding...');
  app.on('second-instance', () => {
    // Someone tried to run a second instance, show window
    console.log('Second instance detected, showing window');
    toggleWindow();
  });
}

app.whenReady().then(() => {
  console.log('App is ready');

  // Start the Python voice-to-text engine
  console.log('Starting Python engine...');
  startPythonEngine();

  // Keep dock icon visible for now (easier to find)
  // if (process.platform === 'darwin') {
  //   app.dock.hide();
  // }

  console.log('Creating tray...');
  createTray();
  console.log('Tray created');

  console.log('Setting up file watcher...');
  setupFileWatcher();
  console.log('File watcher set up');

  // Hot reload for dev
  setupDevHotReload();

  // Create and show window on startup
  console.log('Creating window...');
  createWindow();
  if (mainWindow) {
    mainWindow.show();
    console.log('Window shown');
  }
  console.log('Window created, app running');
});

app.on('window-all-closed', (e) => {
  // Don't quit when window is closed - keep running in tray
  e.preventDefault();
});

app.on('activate', () => {
  toggleWindow();
});

app.on('before-quit', () => {
  // Stop the Python engine
  stopPythonEngine();

  if (watcher) {
    watcher.close();
  }
  if (devWatcher) {
    devWatcher.close();
  }
});
