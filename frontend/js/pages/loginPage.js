import { login } from "../auth/authService.js";
import { renderIcon } from "../components/icons.js";
import { showToast } from "../components/toast.js";
import { escapeHtml } from "../components/ui.js";
import { CONFIG } from "../config.js";

export function renderLoginPage(root, { onLoginSuccess, initialNotice = "" }) {
  root.innerHTML = `
    <main class="auth-page">
      <section class="auth-card" aria-labelledby="auth-heading">
        <div class="auth-header">
          <div class="auth-logo">CMS</div>
          <h1 id="auth-heading" class="auth-title">${escapeHtml(CONFIG.APP_NAME)}</h1>
          <p class="auth-subtitle">Sign in with your institutional account</p>
        </div>

        <div id="auth-error-box" class="alert alert-danger ${initialNotice ? "" : "hidden"}" role="alert">
          ${renderIcon("alertCircle")}
          <span id="auth-error-text">${escapeHtml(initialNotice)}</span>
        </div>

        <form id="login-form" novalidate>
          <div class="form-group">
            <label class="form-label" for="login-email">Email Address</label>
            <input
              id="login-email"
              name="email"
              type="email"
              class="form-control"
              autocomplete="email"
              placeholder="name@college.edu"
              required
            />
            <span id="email-error" class="field-error hidden"></span>
          </div>

          <div class="form-group">
            <label class="form-label" for="login-password">Password</label>
            <div class="input-wrap">
              <input
                id="login-password"
                name="password"
                type="password"
                class="form-control"
                autocomplete="current-password"
                placeholder="Enter your password"
                required
              />
              <button
                id="toggle-password-btn"
                class="input-action"
                type="button"
                aria-label="Show password"
                aria-pressed="false"
              >
                ${renderIcon("eye")}
              </button>
            </div>
            <span id="password-error" class="field-error hidden"></span>
          </div>

          <button id="login-submit-btn" class="btn btn-primary btn-block" type="submit">
            <span id="login-btn-label">Sign In</span>
          </button>
        </form>

        <p class="auth-footer">
          Role access is automatically determined by your account.
        </p>
      </section>
    </main>
  `;

  const form = document.getElementById("login-form");
  const emailInput = document.getElementById("login-email");
  const passwordInput = document.getElementById("login-password");
  const toggleBtn = document.getElementById("toggle-password-btn");
  const submitBtn = document.getElementById("login-submit-btn");
  const errorBox = document.getElementById("auth-error-box");
  const errorText = document.getElementById("auth-error-text");
  const emailErr = document.getElementById("email-error");
  const passErr = document.getElementById("password-error");

  toggleBtn.addEventListener("click", () => {
    const isHidden = passwordInput.type === "password";
    passwordInput.type = isHidden ? "text" : "password";
    toggleBtn.setAttribute("aria-pressed", String(isHidden));
    toggleBtn.setAttribute(
      "aria-label",
      isHidden ? "Hide password" : "Show password"
    );
    toggleBtn.innerHTML = renderIcon(isHidden ? "eyeOff" : "eye");
  });

  function setFieldError(input, errorEl, message) {
    if (message) {
      input.setAttribute("aria-invalid", "true");
      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
    } else {
      input.setAttribute("aria-invalid", "false");
      errorEl.textContent = "";
      errorEl.classList.add("hidden");
    }
  }

  function setLoading(loading) {
    submitBtn.disabled = loading;
    submitBtn.innerHTML = loading
      ? '<span class="spinner" aria-hidden="true"></span><span>Signing in...</span>'
      : '<span id="login-btn-label">Sign In</span>';
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.classList.add("hidden");

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    let valid = true;
    if (!email || !email.includes("@")) {
      setFieldError(emailInput, emailErr, "Please enter a valid email address.");
      valid = false;
    } else {
      setFieldError(emailInput, emailErr, "");
    }

    if (!password) {
      setFieldError(passwordInput, passErr, "Please enter your password.");
      valid = false;
    } else {
      setFieldError(passwordInput, passErr, "");
    }

    if (!valid) {
      return;
    }

    setLoading(true);
    try {
      const user = await login(email, password);
      showToast(`Welcome back, ${user.full_name}`, "success");
      onLoginSuccess(user);
    } catch (err) {
      errorText.textContent = err.message || "Authentication failed.";
      errorBox.classList.remove("hidden");
    } finally {
      setLoading(false);
    }
  });
}
