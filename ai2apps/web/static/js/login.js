(function () {
  "use strict";

  var root = document.getElementById("account-login");
  if (!root) return;

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
    ? "Sign in with an account authorized for this device"
    : "Sign in or register to set up the Core user";
  deviceName.value = (navigator.platform || "Mac") + " · AI2Apps";

  function showError(message) {
    errorBox.textContent = message || "Something went wrong";
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  function setLoading(value) {
    submitButton.disabled = value;
    submitButton.textContent = value
      ? "Please wait…"
      : mode === "login" ? "Sign in" : "Create account";
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
    throw new Error(message(result.data, "This account is not authorized for this Local instance"));
  }

  loginMode.addEventListener("click", function () { setMode("login"); });
  registerMode.addEventListener("click", function () { setMode("register"); });

  accountStage.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();
    setLoading(true);
    email = emailInput.value.trim();
    password = passwordInput.value;
    try {
      if (mode === "register") {
        var registration = await json("/v1/platform/cloud/auth/register", {
          method: "POST",
          body: JSON.stringify({
            displayName: displayName.value.trim(), email: email, password: password,
          }),
        });
        if (!registration.response.ok) {
          throw new Error(message(registration.data, "Registration failed"));
        }
        verifyEmail.textContent = email;
        setStage("verify");
        return;
      }
      var login = await json("/v1/platform/cloud/auth/login", {
        method: "POST", body: JSON.stringify({ email: email, password: password }),
      });
      if (!login.response.ok) throw new Error(message(login.data, "Sign in failed"));
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
        throw new Error(message(verification.data, "Verification failed"));
      }
      var login = await json("/v1/platform/cloud/auth/login", {
        method: "POST", body: JSON.stringify({ email: email, password: password }),
      });
      if (!login.response.ok) throw new Error(message(login.data, "Sign in failed"));
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
    if (!result.response.ok) showError(message(result.data, "Could not resend code"));
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
      if (!result.response.ok) throw new Error(message(result.data, "Core binding failed"));
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
})();
