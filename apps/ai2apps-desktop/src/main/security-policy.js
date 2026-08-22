"use strict";

const EXTERNAL_PROTOCOLS = new Set(["https:", "http:", "mailto:"]);

function parseUrl(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function isTrustedNodeUrl(candidate, nodeUrl) {
  const parsedCandidate = parseUrl(candidate);
  const parsedNode = parseUrl(nodeUrl);
  if (!parsedCandidate || !parsedNode) {
    return false;
  }
  if (!["http:", "https:", "blob:"].includes(parsedCandidate.protocol)) {
    return false;
  }
  return parsedCandidate.origin === parsedNode.origin;
}

function isAllowedExternalUrl(candidate) {
  const parsed = parseUrl(candidate);
  return Boolean(parsed && EXTERNAL_PROTOCOLS.has(parsed.protocol));
}

function classifyNavigation(candidate, nodeUrl, bootstrapUrl) {
  if (candidate === "about:blank" || candidate === bootstrapUrl) {
    return "bootstrap";
  }
  if (isTrustedNodeUrl(candidate, nodeUrl)) {
    return "trusted-node";
  }
  if (isAllowedExternalUrl(candidate)) {
    return "external";
  }
  return "blocked";
}

function isTrustedIpcSender(candidate, nodeUrl, bootstrapUrl) {
  const classification = classifyNavigation(candidate, nodeUrl, bootstrapUrl);
  return classification === "bootstrap" || classification === "trusted-node";
}

module.exports = {
  classifyNavigation,
  isAllowedExternalUrl,
  isTrustedIpcSender,
  isTrustedNodeUrl,
};
