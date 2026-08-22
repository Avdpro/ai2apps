"use strict";

const path = require("node:path");
const { pathToFileURL } = require("node:url");
const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  session,
  shell,
} = require("electron");

const { ConnectionStore } = require("./connection-store");
const { createDesktopLogger } = require("./desktop-logger");
const {
  DEFAULT_NODE_URL,
  configuredNodeOverride,
  waitForNode,
} = require("./node-connection");
const {
  classifyNavigation,
  isAllowedExternalUrl,
  isTrustedIpcSender,
  isTrustedNodeUrl,
} = require("./security-policy");

app.enableSandbox();
app.setName("AI2Apps");

const bootstrapPath = path.join(__dirname, "..", "renderer", "bootstrap", "index.html");
const bootstrapUrl = pathToFileURL(bootstrapPath).toString();
const preloadPath = path.join(__dirname, "..", "preload", "index.js");
const smokeExitAfterLoad = process.argv.includes("--smoke-exit-after-load");

let requestedNodeOverride = null;
let initialConfigurationError = null;
try {
  requestedNodeOverride = configuredNodeOverride();
} catch (error) {
  initialConfigurationError = error.message;
}

let mainWindow = null;
let connectionAttempt = 0;
let connectionStore = null;
let activeConnection = null;
let nodeUrl = requestedNodeOverride || DEFAULT_NODE_URL;
let configurationError = initialConfigurationError;
let logger = null;
let bootstrapState = {
  phase: "checking",
  message: "Checking AI2Apps node…",
  nodeUrl,
  attempt: 0,
  attempts: 0,
};

function activePublicConnection() {
  return activeConnection
    ? {
        id: activeConnection.id,
        name: activeConnection.name,
        url: activeConnection.url,
        kind: activeConnection.kind,
        trustState: activeConnection.trustState,
      }
    : null;
}

function publicState(state) {
  return {
    phase: String(state.phase || "unknown"),
    message: String(state.message || ""),
    nodeUrl: String(state.nodeUrl || ""),
    attempt: Number(state.attempt || 0),
    attempts: Number(state.attempts || 0),
    productVerified: Boolean(state.productVerified),
    authRequired: Boolean(state.authRequired),
    connection: activePublicConnection(),
    platform: state.platform
      ? {
          version: String(state.platform.version || "unknown"),
          apiVersion: String(state.platform.apiVersion || "unknown"),
          runtimeProvider: String(state.platform.runtimeProvider || "unknown"),
        }
      : null,
  };
}

function updateBootstrapState(next) {
  bootstrapState = publicState({ ...bootstrapState, ...next });
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("desktop:bootstrap-state", bootstrapState);
  }
}

function connectionSnapshot() {
  const snapshot = connectionStore.snapshot();
  if (!requestedNodeOverride || initialConfigurationError) {
    return snapshot;
  }
  const override = activePublicConnection();
  return {
    ...snapshot,
    activeConnectionId: override.id,
    connections: [override, ...snapshot.connections],
  };
}

function notifyConnectionsChanged() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("desktop:connections-changed", connectionSnapshot());
  }
}

function senderUrl(event) {
  return event.senderFrame?.url || event.sender?.getURL?.() || "";
}

function assertTrustedSender(event) {
  if (!isTrustedIpcSender(senderUrl(event), nodeUrl, bootstrapUrl)) {
    throw new Error("Rejected IPC from an untrusted frame.");
  }
}

function assertBootstrapSender(event) {
  if (senderUrl(event) !== bootstrapUrl) {
    throw new Error("Connection changes are only available from the Desktop node picker.");
  }
}

async function openExternalSafely(candidate) {
  if (!isAllowedExternalUrl(candidate)) {
    return;
  }
  try {
    await shell.openExternal(candidate);
  } catch (error) {
    logger?.error("Failed to open external URL", error);
  }
}

function installWebContentsPolicy(window) {
  const handleNavigation = (event, candidate) => {
    const classification = classifyNavigation(candidate, nodeUrl, bootstrapUrl);
    if (classification === "trusted-node" || classification === "bootstrap") {
      return;
    }
    event.preventDefault();
    logger?.warn("Blocked renderer navigation", classification, candidate);
    if (classification === "external") {
      void openExternalSafely(candidate);
    }
  };

  window.webContents.on("will-navigate", handleNavigation);
  window.webContents.on("will-redirect", handleNavigation);
  window.webContents.setWindowOpenHandler(({ url }) => {
    const classification = classifyNavigation(url, nodeUrl, bootstrapUrl);
    if (classification === "external") {
      void openExternalSafely(url);
    } else {
      logger?.warn("Blocked renderer window creation", classification, url);
    }
    return { action: "deny" };
  });

  window.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
      if (!isMainFrame || !isTrustedNodeUrl(validatedURL, nodeUrl)) {
        return;
      }
      logger?.error("AI2Apps Shell load failed", errorCode, errorDescription, validatedURL);
      updateBootstrapState({
        phase: "error",
        message: `Failed to load AI2Apps Shell (${errorCode}): ${errorDescription}`,
      });
      void window.loadFile(bootstrapPath);
    },
  );
  window.webContents.on("render-process-gone", (_event, details) => {
    logger?.error("Renderer process exited", details);
  });
  window.webContents.on("did-finish-load", () => {
    const loadedUrl = window.webContents.getURL();
    if (!smokeExitAfterLoad || !isTrustedNodeUrl(loadedUrl, nodeUrl)) {
      return;
    }
    console.log(`AI2Apps Desktop smoke loaded ${loadedUrl}`);
    setTimeout(() => app.quit(), 100);
  });
}

async function showNodePicker(message = "Select an AI2Apps node.") {
  connectionAttempt += 1;
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  await mainWindow.loadFile(bootstrapPath);
  updateBootstrapState({
    phase: "idle",
    message,
    nodeUrl,
    attempt: 0,
    attempts: 0,
    platform: null,
  });
  notifyConnectionsChanged();
}

async function connectToNode() {
  const currentAttempt = ++connectionAttempt;
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  if (!mainWindow.webContents.getURL().startsWith("file:")) {
    await mainWindow.loadFile(bootstrapPath);
  }
  if (configurationError) {
    updateBootstrapState({
      phase: "incompatible",
      message: configurationError,
      nodeUrl,
      attempt: 0,
      attempts: 0,
    });
    return;
  }
  updateBootstrapState({
    phase: "checking",
    message: `Checking ${activeConnection?.name || "AI2Apps node"}…`,
    nodeUrl,
    attempt: 0,
    attempts: 15,
    platform: null,
    productVerified: false,
    authRequired: false,
  });

  logger?.info("Checking AI2Apps node", activeConnection?.id, nodeUrl);
  const result = await waitForNode(nodeUrl, {
    attempts: 15,
    intervalMs: 1000,
    timeoutMs: 2500,
    onAttempt: (attemptResult, attempt, attempts) => {
      if (currentAttempt !== connectionAttempt) {
        return;
      }
      updateBootstrapState({ ...attemptResult, attempt, attempts });
    },
  });

  if (currentAttempt !== connectionAttempt || !mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  if (result.phase !== "ready") {
    logger?.warn("AI2Apps node did not become ready", result.phase, result.message);
    updateBootstrapState(result);
    return;
  }

  if (!requestedNodeOverride && activeConnection?.id) {
    activeConnection = connectionStore.select(activeConnection.id);
  }
  logger?.info("AI2Apps node ready", activeConnection?.id, result.platform || "auth-required");
  updateBootstrapState({ ...result, phase: "loading", message: "Opening AI2Apps…" });
  try {
    await mainWindow.loadURL(nodeUrl);
  } catch (error) {
    logger?.error("Failed to open AI2Apps Shell", error);
    updateBootstrapState({
      phase: "error",
      message: `Failed to open AI2Apps Shell: ${error.message}`,
    });
    await mainWindow.loadFile(bootstrapPath);
  }
}

async function activateStoredConnection(connectionId) {
  requestedNodeOverride = null;
  initialConfigurationError = null;
  configurationError = null;
  activeConnection = connectionStore.select(String(connectionId));
  nodeUrl = activeConnection.url;
  notifyConnectionsChanged();
  await connectToNode();
  return activePublicConnection();
}

async function chooseFiles(properties) {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: properties.includes("openDirectory")
      ? "Choose an AI2Apps Folder"
      : "Choose AI2Apps Files",
    properties,
  });
  if (result.canceled) {
    return [];
  }
  return result.filePaths.map((filename) => ({
    name: path.basename(filename),
    path: filename,
  }));
}

async function chooseFilesAndNotify(properties) {
  const selection = await chooseFiles(properties);
  if (selection.length && mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("desktop:file-selection", selection);
  }
  return selection;
}

async function openLogsDirectory() {
  const error = await shell.openPath(logger.directory);
  if (error) {
    logger.warn("Failed to open Desktop logs directory", error);
  }
}

function createApplicationMenu() {
  const isMac = process.platform === "darwin";
  const template = [
    ...(isMac
      ? [{
          label: "AI2Apps",
          submenu: [
            { role: "about" },
            { type: "separator" },
            { role: "hide" },
            { role: "hideOthers" },
            { role: "unhide" },
            { type: "separator" },
            { role: "quit" },
          ],
        }]
      : []),
    {
      label: "File",
      submenu: [
        {
          label: "Choose Files…",
          accelerator: "CommandOrControl+O",
          click: () => void chooseFilesAndNotify(["openFile", "multiSelections"]),
        },
        {
          label: "Choose Folder…",
          accelerator: "CommandOrControl+Shift+O",
          click: () => void chooseFilesAndNotify(["openDirectory"]),
        },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },
    {
      label: "Node",
      submenu: [
        {
          label: "Manage Nodes…",
          accelerator: "CommandOrControl+Shift+N",
          click: () => void showNodePicker(),
        },
        {
          label: "Reconnect",
          accelerator: "CommandOrControl+Shift+R",
          click: () => void connectToNode(),
        },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        ...(!app.isPackaged ? [{ type: "separator" }, { role: "toggleDevTools" }] : []),
      ],
    },
    { role: "windowMenu" },
    {
      role: "help",
      submenu: [
        { label: "Open Desktop Logs", click: () => void openLogsDirectory() },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    show: false,
    backgroundColor: "#0d1117",
    title: "AI2Apps",
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      nodeIntegrationInWorker: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      webviewTag: false,
      allowRunningInsecureContent: false,
      experimentalFeatures: false,
    },
  });

  installWebContentsPolicy(mainWindow);
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
    connectionAttempt += 1;
  });
  void mainWindow.loadFile(bootstrapPath).then(connectToNode);
}

function configureSessionPolicy() {
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  session.defaultSession.on("will-download", (event, item) => {
    if (!isTrustedNodeUrl(item.getURL(), nodeUrl)) {
      logger.warn("Blocked download from untrusted origin", item.getURL());
      event.preventDefault();
      return;
    }
    item.setSaveDialogOptions({
      title: "Save AI2Apps Download",
      buttonLabel: "Save",
    });
  });
}

function registerIpc() {
  ipcMain.handle("desktop:get-bootstrap-state", (event) => {
    assertTrustedSender(event);
    return bootstrapState;
  });
  ipcMain.handle("desktop:retry-connection", (event) => {
    assertTrustedSender(event);
    void connectToNode();
    return true;
  });
  ipcMain.handle("desktop:show-node-picker", (event) => {
    assertTrustedSender(event);
    void showNodePicker();
    return true;
  });
  ipcMain.handle("desktop:get-connections", (event) => {
    assertTrustedSender(event);
    return connectionSnapshot();
  });
  ipcMain.handle("desktop:add-connection", async (event, input) => {
    assertBootstrapSender(event);
    const added = connectionStore.add({ name: input?.name, url: input?.url });
    logger.info("Desktop connection added", added.id, added.kind, added.url);
    await activateStoredConnection(added.id);
    return added;
  });
  ipcMain.handle("desktop:select-connection", async (event, connectionId) => {
    assertBootstrapSender(event);
    return activateStoredConnection(connectionId);
  });
  ipcMain.handle("desktop:remove-connection", (event, connectionId) => {
    assertBootstrapSender(event);
    const removed = connectionStore.remove(String(connectionId));
    logger.info("Desktop connection removed", removed.id, removed.kind, removed.url);
    if (activeConnection?.id === removed.id) {
      activeConnection = connectionStore.active();
      nodeUrl = activeConnection.url;
    }
    notifyConnectionsChanged();
    return removed;
  });
  ipcMain.handle("desktop:choose-files", async (event) => {
    assertTrustedSender(event);
    return chooseFiles(["openFile", "multiSelections"]);
  });
  ipcMain.handle("desktop:choose-directory", async (event) => {
    assertTrustedSender(event);
    const result = await chooseFiles(["openDirectory"]);
    return result[0] || null;
  });
  ipcMain.handle("desktop:open-logs", (event) => {
    assertTrustedSender(event);
    void openLogsDirectory();
    return true;
  });
  ipcMain.handle("desktop:get-info", (event) => {
    assertTrustedSender(event);
    return {
      version: app.getVersion(),
      platform: process.platform,
      architecture: process.arch,
      packaged: app.isPackaged,
    };
  });
}

app.whenReady().then(() => {
  const userData = app.getPath("userData");
  logger = createDesktopLogger(path.join(userData, "logs"));
  connectionStore = new ConnectionStore(path.join(userData, "connections.json"));
  activeConnection = requestedNodeOverride && !initialConfigurationError
    ? {
        id: "development-override",
        name: "Development Node",
        url: requestedNodeOverride,
        kind: requestedNodeOverride.startsWith("http://") ? "existing-local" : "remote",
        trustState: "development-override",
      }
    : connectionStore.active();
  nodeUrl = activeConnection.url;

  logger.info("AI2Apps Desktop starting", app.getVersion(), process.platform, process.arch);
  configureSessionPolicy();
  registerIpc();
  createApplicationMenu();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("child-process-gone", (_event, details) => {
  logger?.error("Electron child process exited", details);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
