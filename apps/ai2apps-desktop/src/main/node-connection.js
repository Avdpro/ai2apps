"use strict";

const DEFAULT_NODE_URL = "http://127.0.0.1:8000/";
const SUPPORTED_API_VERSIONS = new Set(["v1"]);

function isLoopbackHostname(hostname) {
  const normalized = String(hostname || "")
    .toLowerCase()
    .replace(/^\[|\]$/g, "");
  return (
    normalized === "localhost" ||
    normalized === "127.0.0.1" ||
    normalized === "::1"
  );
}

function normalizeNodeUrl(value) {
  let parsed;
  try {
    parsed = new URL(value || DEFAULT_NODE_URL);
  } catch {
    throw new Error("Node URL must be a valid absolute URL.");
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error("Node URL must use HTTP or HTTPS.");
  }
  if (parsed.username || parsed.password) {
    throw new Error("Node URL must not contain credentials.");
  }
  if (parsed.protocol === "http:" && !isLoopbackHostname(parsed.hostname)) {
    throw new Error("Remote AI2Apps nodes must use HTTPS.");
  }
  if (parsed.search || parsed.hash) {
    throw new Error("Node URL must not contain a query string or fragment.");
  }

  parsed.pathname = `${parsed.pathname.replace(/\/+$/, "")}/`;
  return parsed.toString();
}

function configuredNodeUrl(argv = process.argv, env = process.env) {
  return configuredNodeOverride(argv, env) || DEFAULT_NODE_URL;
}

function configuredNodeOverride(argv = process.argv, env = process.env) {
  const argument = argv.find((item) => item.startsWith("--node-url="));
  const raw = argument
    ? argument.slice("--node-url=".length)
    : env.AI2APPS_DESKTOP_NODE_URL;
  return raw ? normalizeNodeUrl(raw) : null;
}

function endpoint(baseUrl, relativePath) {
  return new URL(relativePath.replace(/^\//, ""), normalizeNodeUrl(baseUrl)).toString();
}

async function jsonResponse(response) {
  const contentType = response.headers?.get?.("content-type") || "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return null;
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function fetchWithTimeout(fetchImpl, url, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetchImpl(url, {
      method: "GET",
      redirect: "manual",
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
  } finally {
    clearTimeout(timeout);
  }
}

function validatePlatformHealth(body) {
  if (!body || typeof body !== "object") {
    throw new Error("AI2Apps platform health returned invalid JSON.");
  }
  if (body.product !== "ai2apps") {
    throw new Error("The endpoint is not an AI2Apps node.");
  }
  if (!SUPPORTED_API_VERSIONS.has(body.api_version)) {
    throw new Error(`Unsupported AI2Apps API version: ${body.api_version || "missing"}.`);
  }
  if (body.status !== "ok") {
    throw new Error(`AI2Apps platform is not healthy: ${body.status || "unknown"}.`);
  }
  return {
    product: body.product,
    version: typeof body.version === "string" ? body.version : "unknown",
    apiVersion: body.api_version,
    databaseStatus: body.database?.status || "unknown",
    runtimeProvider: body.runtime?.provider || "unknown",
  };
}

async function probeNode(baseUrl, options = {}) {
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const timeoutMs = options.timeoutMs || 3000;
  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required.");
  }

  const normalizedUrl = normalizeNodeUrl(baseUrl);
  let publicHealthResponse;
  try {
    publicHealthResponse = await fetchWithTimeout(
      fetchImpl,
      endpoint(normalizedUrl, "health"),
      timeoutMs,
    );
  } catch (error) {
    return {
      phase: "unavailable",
      retryable: true,
      nodeUrl: normalizedUrl,
      message:
        error?.name === "AbortError"
          ? "AI2Apps node health check timed out."
          : `AI2Apps node is unavailable: ${error?.message || "connection failed"}`,
    };
  }

  const publicHealth = await jsonResponse(publicHealthResponse);
  if (publicHealthResponse.status === 503 || publicHealth?.status === "loading") {
    return {
      phase: "starting",
      retryable: true,
      nodeUrl: normalizedUrl,
      message: "AI2Apps node is still starting.",
    };
  }
  if (!publicHealthResponse.ok || publicHealth?.status !== "healthy") {
    return {
      phase: "unavailable",
      retryable: true,
      nodeUrl: normalizedUrl,
      message: `Node health check failed with HTTP ${publicHealthResponse.status}.`,
    };
  }

  let platformResponse;
  try {
    platformResponse = await fetchWithTimeout(
      fetchImpl,
      endpoint(normalizedUrl, "v1/platform/health"),
      timeoutMs,
    );
  } catch (error) {
    return {
      phase: "unavailable",
      retryable: true,
      nodeUrl: normalizedUrl,
      message: `AI2Apps platform check failed: ${error?.message || "connection failed"}`,
    };
  }

  if (platformResponse.status === 401 || platformResponse.status === 403) {
    return {
      phase: "ready",
      retryable: false,
      authRequired: true,
      productVerified: false,
      nodeUrl: normalizedUrl,
      message: "AI2Apps node is ready. Sign in to continue.",
    };
  }
  if (!platformResponse.ok) {
    return {
      phase: "unavailable",
      retryable: true,
      nodeUrl: normalizedUrl,
      message: `AI2Apps platform check failed with HTTP ${platformResponse.status}.`,
    };
  }

  try {
    const platform = validatePlatformHealth(await jsonResponse(platformResponse));
    if (platform.databaseStatus !== "ready") {
      return {
        phase: "starting",
        retryable: true,
        nodeUrl: normalizedUrl,
        productVerified: true,
        platform,
        message: `AI2Apps database is ${platform.databaseStatus}.`,
      };
    }
    return {
      phase: "ready",
      retryable: false,
      authRequired: false,
      productVerified: true,
      nodeUrl: normalizedUrl,
      platform,
      message: "AI2Apps node is ready.",
    };
  } catch (error) {
    return {
      phase: "incompatible",
      retryable: false,
      nodeUrl: normalizedUrl,
      message: error.message,
    };
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForNode(baseUrl, options = {}) {
  const attempts = options.attempts || 15;
  const intervalMs = options.intervalMs || 1000;
  let result;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    result = await probeNode(baseUrl, options);
    options.onAttempt?.(result, attempt, attempts);
    if (result.phase === "ready" || result.phase === "incompatible") {
      return result;
    }
    if (attempt < attempts) {
      await delay(intervalMs);
    }
  }
  return result;
}

module.exports = {
  DEFAULT_NODE_URL,
  configuredNodeOverride,
  configuredNodeUrl,
  endpoint,
  isLoopbackHostname,
  normalizeNodeUrl,
  probeNode,
  validatePlatformHealth,
  waitForNode,
};
