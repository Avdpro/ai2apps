"use strict";

const title = document.querySelector("#title");
const message = document.querySelector("#message");
const nodeUrl = document.querySelector("#node-url");
const status = document.querySelector("#status");
const desktopInfo = document.querySelector("#desktop-info");
const progress = document.querySelector("#progress-bar");
const retry = document.querySelector("#retry");
const manageNodes = document.querySelector("#manage-nodes");
const openLogs = document.querySelector("#open-logs");
const nodeManager = document.querySelector("#node-manager");
const closeManager = document.querySelector("#close-manager");
const connectionList = document.querySelector("#connection-list");
const addConnection = document.querySelector("#add-connection");
const connectionName = document.querySelector("#connection-name");
const connectionUrl = document.querySelector("#connection-url");
const connectionError = document.querySelector("#connection-error");

let connections = { activeConnectionId: null, connections: [] };

const labels = {
  idle: "Ready",
  checking: "Checking",
  starting: "Starting",
  unavailable: "Unavailable",
  incompatible: "Incompatible",
  loading: "Opening",
  error: "Error",
};

function renderState(state) {
  const phase = state?.phase || "checking";
  title.textContent =
    phase === "idle"
      ? "Choose where AI2Apps runs"
      : phase === "incompatible"
        ? "This node is not compatible"
        : phase === "error" || phase === "unavailable"
          ? "AI2Apps is not available"
          : "Connecting to your AI node";
  message.textContent = state?.message || "Checking AI2Apps node…";
  nodeUrl.textContent = state?.nodeUrl || "—";
  status.textContent = labels[phase] || phase;
  const attempt = Number(state?.attempt || 0);
  const attempts = Math.max(Number(state?.attempts || 0), 1);
  progress.style.width = `${Math.max(8, Math.min(100, (attempt / attempts) * 100))}%`;
  retry.hidden = !["unavailable", "incompatible", "error"].includes(phase);
  retry.disabled = false;
  if (["idle", "unavailable", "incompatible", "error"].includes(phase)) {
    nodeManager.hidden = false;
  }
}

function button(label, className, onClick) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  if (className) {
    element.className = className;
  }
  element.addEventListener("click", onClick);
  return element;
}

function renderConnections(snapshot) {
  connections = snapshot || { activeConnectionId: null, connections: [] };
  connectionList.replaceChildren();
  for (const connection of connections.connections) {
    const row = document.createElement("article");
    row.className = `connection${connection.id === connections.activeConnectionId ? " active" : ""}`;

    const detail = document.createElement("div");
    const name = document.createElement("p");
    name.className = "connection-name";
    name.textContent = connection.name;
    const url = document.createElement("div");
    url.className = "connection-url";
    url.textContent = `${connection.kind === "remote" ? "Remote" : "Local"} · ${connection.url}`;
    detail.append(name, url);

    const actions = document.createElement("div");
    actions.className = "connection-actions";
    actions.append(
      button("Connect", "", async (event) => {
        event.currentTarget.disabled = true;
        connectionError.textContent = "";
        try {
          await window.ai2appsDesktop.selectConnection(connection.id);
        } catch (error) {
          connectionError.textContent = error.message;
          event.currentTarget.disabled = false;
        }
      }),
    );
    if (connection.id !== "local-default" && connection.id !== "development-override") {
      actions.append(
        button("Remove", "danger", async () => {
          connectionError.textContent = "";
          try {
            await window.ai2appsDesktop.removeConnection(connection.id);
          } catch (error) {
            connectionError.textContent = error.message;
          }
        }),
      );
    }
    row.append(detail, actions);
    connectionList.append(row);
  }
}

retry.addEventListener("click", async () => {
  retry.disabled = true;
  await window.ai2appsDesktop.retryConnection();
});

manageNodes.addEventListener("click", async () => {
  nodeManager.hidden = false;
  renderConnections(await window.ai2appsDesktop.getConnections());
});

closeManager.addEventListener("click", () => {
  nodeManager.hidden = true;
});

openLogs.addEventListener("click", () => window.ai2appsDesktop.openLogs());

addConnection.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = addConnection.querySelector("button[type=submit]");
  submit.disabled = true;
  connectionError.textContent = "";
  try {
    await window.ai2appsDesktop.addConnection({
      name: connectionName.value,
      url: connectionUrl.value,
    });
  } catch (error) {
    connectionError.textContent = error.message;
    submit.disabled = false;
  }
});

window.ai2appsDesktop.onBootstrapState(renderState);
window.ai2appsDesktop.onConnectionsChanged(renderConnections);

Promise.all([
  window.ai2appsDesktop.getBootstrapState(),
  window.ai2appsDesktop.getDesktopInfo(),
  window.ai2appsDesktop.getConnections(),
]).then(([state, info, connectionState]) => {
  renderState(state);
  renderConnections(connectionState);
  desktopInfo.textContent = `${info.version} · ${info.platform}-${info.architecture}`;
});
