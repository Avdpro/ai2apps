"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld(
  "ai2appsDesktop",
  Object.freeze({
    getBootstrapState: () => ipcRenderer.invoke("desktop:get-bootstrap-state"),
    retryConnection: () => ipcRenderer.invoke("desktop:retry-connection"),
    showNodePicker: () => ipcRenderer.invoke("desktop:show-node-picker"),
    getConnections: () => ipcRenderer.invoke("desktop:get-connections"),
    addConnection: (input) => ipcRenderer.invoke("desktop:add-connection", {
      name: String(input?.name || ""),
      url: String(input?.url || ""),
    }),
    selectConnection: (connectionId) =>
      ipcRenderer.invoke("desktop:select-connection", String(connectionId || "")),
    removeConnection: (connectionId) =>
      ipcRenderer.invoke("desktop:remove-connection", String(connectionId || "")),
    chooseFiles: () => ipcRenderer.invoke("desktop:choose-files"),
    chooseDirectory: () => ipcRenderer.invoke("desktop:choose-directory"),
    openLogs: () => ipcRenderer.invoke("desktop:open-logs"),
    getDesktopInfo: () => ipcRenderer.invoke("desktop:get-info"),
    onBootstrapState: (listener) => {
      if (typeof listener !== "function") {
        throw new TypeError("Bootstrap listener must be a function.");
      }
      const handler = (_event, state) => listener(state);
      ipcRenderer.on("desktop:bootstrap-state", handler);
      return () => ipcRenderer.removeListener("desktop:bootstrap-state", handler);
    },
    onConnectionsChanged: (listener) => {
      if (typeof listener !== "function") {
        throw new TypeError("Connection listener must be a function.");
      }
      const handler = (_event, state) => listener(state);
      ipcRenderer.on("desktop:connections-changed", handler);
      return () => ipcRenderer.removeListener("desktop:connections-changed", handler);
    },
    onFileSelection: (listener) => {
      if (typeof listener !== "function") {
        throw new TypeError("File selection listener must be a function.");
      }
      const handler = (_event, selection) => listener(selection);
      ipcRenderer.on("desktop:file-selection", handler);
      return () => ipcRenderer.removeListener("desktop:file-selection", handler);
    },
  }),
);
