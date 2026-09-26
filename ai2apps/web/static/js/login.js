(function () {
  "use strict";

  var root = document.getElementById("account-login");
  if (!root) return;

  var t = window.t;

  var installationBound = root.dataset.installationBound === "true";
  var mode = "login";
  var email = "";
  var password = "";
  var accountStage = document.getElementById("account-stage");
  var verifyStage = document.getElementById("verify-stage");
  var bindStage = document.getElementById("bind-stage");
  var loginMode = document.getElementById("login-mode");
  var registerMode = document.getElementById("register-mode");
  var displayName = document.getElementById("display-name");
  var emailInput = document.getElementById("email");
  var passwordInput = document.getElementById("password");
  var submitButton = document.getElementById("account-submit");
  var errorBox = document.getElementById("login-error");
  var verifyEmail = document.getElementById("verify-email");
  var verificationCode = document.getElementById("verification-code");
  var deviceName = document.getElementById("device-name");

  document.getElementById("login-subtitle").textContent = installationBound
    ? t("login.account.bound_subtitle")
    : t("login.account.setup_subtitle");
  deviceName.value = "Mac";

  function showError(message) {
    errorBox.textContent = message || t("login.account.error");
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  function validPassword(value) {
    var bytes = new TextEncoder().encode(String(value || "")).length;
    return bytes >= 8 && bytes <= 128;
  }

  function setLoading(value) {
    submitButton.disabled = value;
    submitButton.textContent = value
      ? t("login.account.waiting")
      : mode === "login" ? t("login.account.sign_in") : t("login.account.register");
    verifyStage.querySelector("button").disabled = value;
    document.getElementById("bind-core").disabled = value;
  }

  function setStage(stage) {
    accountStage.hidden = stage !== "account";
    verifyStage.hidden = stage !== "verify";
    bindStage.hidden = stage !== "bind";
  }

  function setMode(nextMode) {
    mode = nextMode;
    clearError();
    displayName.hidden = mode !== "register";
    displayName.required = mode === "register";
    loginMode.className = "rounded-lg py-2 text-sm font-semibold " +
      (mode === "login" ? "bg-white shadow-sm" : "text-neutral-500");
    registerMode.className = "rounded-lg py-2 text-sm font-semibold " +
      (mode === "register" ? "bg-white shadow-sm" : "text-neutral-500");
    setLoading(false);
  }

  function message(data, fallback) {
    return data?.error?.message || data?.detail?.message || data?.detail ||
      data?.message || fallback;
  }

  function code(data) {
    return data?.error?.code || data?.detail?.code || data?.code || "";
  }

  async function json(url, options) {
    options = options || {};
    var response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    var data = {};
    try { data = await response.json(); } catch (_) {}
    return { response: response, data: data };
  }

  async function loadDefaultDeviceName() {
    var initialValue = deviceName.value;
    try {
      var result = await json("/v1/platform/client/bootstrap");
      var candidate = String(result.data?.device_name || "").trim();
      if (result.response.ok && candidate && deviceName.value === initialValue) {
        deviceName.value = candidate;
      }
    } catch (_) { /* Keep the editable fallback when hardware lookup fails. */ }
  }

  function finish() {
    var requested = new URLSearchParams(location.search).get("redirect");
    location.href = requested && requested.startsWith("/") &&
      !requested.startsWith("//") ? requested : "/admin/dashboard";
  }

  async function activate() {
    var result = await json("/v1/platform/auth/cloud-member/activate", {
      method: "POST", body: "{}",
    });
    if (result.response.ok) return finish();
    var resultCode = code(result.data).toLowerCase();
    if (!installationBound &&
        (resultCode.includes("installation_not_bound") || result.response.status === 409)) {
      setStage("bind");
      return;
    }
    throw new Error(message(result.data, t("login.account.unauthorized")));
  }

  loginMode.addEventListener("click", function () { setMode("login"); });
  registerMode.addEventListener("click", function () { setMode("register"); });

  accountStage.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();
    email = emailInput.value.trim();
    password = passwordInput.value;
    if (!validPassword(password)) {
      showError(t("login.account.password_error"));
      return;
    }
    setLoading(true);
    try {
      if (mode === "register") {
        var registration = await json("/v1/platform/cloud/auth/register", {
          method: "POST",
          body: JSON.stringify({
            displayName: displayName.value.trim(), email: email, password: password,
          }),
        });
        if (!registration.response.ok) {
          throw new Error(message(registration.data, t("login.account.register_error")));
        }
        verifyEmail.textContent = email;
        setStage("verify");
        return;
      }
      var login = await json("/v1/platform/cloud/auth/login", {
        method: "POST", body: JSON.stringify({ email: email, password: password }),
      });
      if (!login.response.ok) throw new Error(message(login.data, t("login.account.login_error")));
      await activate();
    } catch (error) {
      showError(error.message);
    } finally {
      setLoading(false);
    }
  });

  verifyStage.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();
    setLoading(true);
    try {
      var verification = await json("/v1/platform/cloud/auth/email/verify", {
        method: "POST",
        body: JSON.stringify({ email: email, code: verificationCode.value.trim() }),
      });
      if (!verification.response.ok) {
        throw new Error(message(verification.data, t("login.account.verify_error")));
      }
      var login = await json("/v1/platform/cloud/auth/login", {
        method: "POST", body: JSON.stringify({ email: email, password: password }),
      });
      if (!login.response.ok) throw new Error(message(login.data, t("login.account.login_error")));
      await activate();
    } catch (error) {
      showError(error.message);
    } finally {
      setLoading(false);
    }
  });

  document.getElementById("resend-code").addEventListener("click", async function () {
    clearError();
    var result = await json("/v1/platform/cloud/auth/email/resend", {
      method: "POST", body: JSON.stringify({ email: email }),
    });
    if (!result.response.ok) showError(message(result.data, t("login.account.resend_error")));
  });

  document.getElementById("bind-core").addEventListener("click", async function () {
    clearError();
    setLoading(true);
    try {
      var result = await json("/v1/platform/auth/core/bootstrap", {
        method: "POST",
        body: JSON.stringify({
          displayName: deviceName.value.trim(),
          ownerPassword: password,
        }),
      });
      if (!result.response.ok) throw new Error(message(result.data, t("login.account.bind_error")));
      finish();
    } catch (error) {
      showError(error.message);
    } finally {
      setLoading(false);
    }
  });

  document.getElementById("reset-login").addEventListener("click", function () {
    password = "";
    passwordInput.value = "";
    clearError();
    setStage("account");
  });

  setMode("login");
  setStage("account");
  loadDefaultDeviceName();
})();
