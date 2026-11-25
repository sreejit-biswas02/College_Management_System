import { setUnauthorizedHandler } from "./api/client.js";
import { clearSession, restoreSession } from "./auth/authService.js";
import { renderLoading } from "./components/ui.js";
import { renderDashboardShell } from "./pages/dashboardShell.js";
import { renderLoginPage } from "./pages/loginPage.js";

const root = document.getElementById("app-root");

function showLogin(notice = "") {
  root.className = "";
  renderLoginPage(root, {
    initialNotice: notice,
    onLoginSuccess: (user) => showDashboard(user),
  });
}

function showDashboard(user) {
  renderDashboardShell(root, {
    user,
    onLogout: () => showLogin(),
  });
}

async function bootstrap() {
  setUnauthorizedHandler((message) => {
    clearSession();
    showLogin(message);
  });

  root.innerHTML = renderLoading("Restoring session...");
  const user = await restoreSession();
  if (user) {
    showDashboard(user);
  } else {
    showLogin();
  }
}

bootstrap();
