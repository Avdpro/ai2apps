"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const { packager } = require("@electron/packager");
const packageInfo = require("../package.json");

function findDeveloperIdIdentity() {
  if (process.env.AI2APPS_CODESIGN_IDENTITY) {
    return process.env.AI2APPS_CODESIGN_IDENTITY;
  }
  const identities = execFileSync(
    "security",
    ["find-identity", "-v", "-p", "codesigning"],
    { encoding: "utf8" },
  );
  const match = identities.match(/"(Developer ID Application: [^"]+)"/);
  return match ? match[1] : null;
}

async function main() {
  if (process.platform !== "darwin") {
    throw new Error("The macOS Client package must be built on macOS.");
  }

  const root = path.resolve(__dirname, "..");
  const output = path.join(root, "out");
  const signingIdentity = findDeveloperIdIdentity();
  if (signingIdentity) {
    console.log(`Using code-signing identity: ${signingIdentity}`);
  } else {
    console.warn("No Developer ID Application identity found; using an ad-hoc development signature.");
  }
  const paths = await packager({
    dir: root,
    out: output,
    name: "AI2Apps",
    executableName: "AI2Apps",
    appBundleId: "com.ai2apps.desktop",
    appCategoryType: "public.app-category.productivity",
    appVersion: "0.1.0",
    buildVersion: "1",
    electronVersion: packageInfo.devDependencies.electron,
    platform: "darwin",
    arch: process.arch,
    asar: true,
    overwrite: true,
    prune: true,
    ...(signingIdentity
      ? { osxSign: { identity: signingIdentity, continueOnError: false } }
      : {}),
    extendInfo: {
      CFBundleDisplayName: "AI2Apps",
      LSMinimumSystemVersion: "13.0",
      NSHighResolutionCapable: true,
    },
    ignore: [
      /^\/out(?:\/|$)/,
      /^\/tests(?:\/|$)/,
      /^\/scripts(?:\/|$)/,
      /^\/README\.md$/,
      /^\/\.gitignore$/,
    ],
  });

  const bundleDirectory = paths[0];
  const appPath = path.join(bundleDirectory, "AI2Apps.app");
  if (!signingIdentity) {
    execFileSync(
      "codesign",
      ["--force", "--deep", "--sign", "-", "--timestamp=none", appPath],
      { stdio: "inherit" },
    );
  }
  execFileSync("codesign", ["--verify", "--deep", "--strict", "--verbose=2", appPath], {
    stdio: "inherit",
  });

  const dmgPath = path.join(
    output,
    `AI2Apps-${packageInfo.version}-macos-${process.arch}.dmg`,
  );
  try {
    fs.unlinkSync(dmgPath);
  } catch (error) {
    if (error.code !== "ENOENT") {
      throw error;
    }
  }
  execFileSync(
    "hdiutil",
    ["create", "-volname", "AI2Apps", "-srcfolder", appPath, "-ov", "-format", "UDZO", dmgPath],
    { stdio: "inherit" },
  );

  if (signingIdentity) {
    execFileSync(
      "codesign",
      ["--force", "--sign", signingIdentity, "--timestamp", dmgPath],
      { stdio: "inherit" },
    );
    execFileSync("codesign", ["--verify", "--strict", "--verbose=2", dmgPath], {
      stdio: "inherit",
    });
  }

  console.log(`Packaged ${signingIdentity ? "Developer ID-signed" : "ad-hoc signed"} Client: ${appPath}`);
  console.log(`Created ${signingIdentity ? "Developer ID-signed" : "development"} installer: ${dmgPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
