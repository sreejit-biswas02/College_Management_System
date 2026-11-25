import { logout } from "../auth/authService.js";
import { renderNavbar } from "../components/navbar.js";
import { renderSidebar } from "../components/sidebar.js";
import { showToast } from "../components/toast.js";
import { ROLE_NAVIGATION, ROLES } from "../config.js";
import { renderAdminPage } from "./adminPages.js";
import { renderFacultyPage } from "./facultyPages.js";
import { renderStudentPage } from "./studentPages.js";

const shellState = {
  collapsed: false,
  mobileOpen: false,
  activeRoute: "dashboard",
};

export function renderDashboardShell(root, { user, onLogout }) {
  const navItems = ROLE_NAVIGATION[user.role] || [];
  const validIds = new Set(navItems.map((i) => i.id));
  if (!validIds.has(shellState.activeRoute)) {
    shellState.activeRoute = navItems[0]?.id || "dashboard";
  }

  const activeItem =
    navItems.find((i) => i.id === shellState.activeRoute) || {
      id: "dashboard",
      label: "Dashboard",
    };

  root.className = `role-${user.role}`;
  root.innerHTML = `
    <div class="app-shell">
      ${renderSidebar({
        user,
        activeRoute: shellState.activeRoute,
        collapsed: shellState.collapsed,
        mobileOpen: shellState.mobileOpen,
      })}
      <div class="main-area">
        ${renderNavbar({
          user,
          pageTitle: activeItem.label,
          breadcrumb: `${user.role.toUpperCase()} / ${activeItem.label}`,
        })}
        <main id="page-content" class="main-content"></main>
      </div>
    </div>
  `;

  const contentEl = document.getElementById("page-content");
  if (user.role === ROLES.ADMIN) {
    renderAdminPage(contentEl, activeItem.id);
  } else if (user.role === ROLES.FACULTY) {
    renderFacultyPage(contentEl, activeItem.id);
  } else {
    renderStudentPage(contentEl, activeItem.id);
  }

  function handleLogout() {
    logout();
    shellState.activeRoute = "dashboard";
    shellState.mobileOpen = false;
    showToast("You have been signed out.", "info");
    onLogout();
  }

  root.querySelectorAll("[data-route]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-route");
      if (!validIds.has(target)) {
        showToast("You do not have access to that section.", "error");
        return;
      }
      shellState.activeRoute = target;
      shellState.mobileOpen = false;
      renderDashboardShell(root, { user, onLogout });
    });
  });

  document.getElementById("sidebar-collapse-btn")?.addEventListener("click", () => {
    shellState.collapsed = !shellState.collapsed;
    renderDashboardShell(root, { user, onLogout });
  });

  document.getElementById("mobile-menu-btn")?.addEventListener("click", () => {
    shellState.mobileOpen = true;
    renderDashboardShell(root, { user, onLogout });
  });

  document.getElementById("sidebar-overlay")?.addEventListener("click", () => {
    shellState.mobileOpen = false;
    renderDashboardShell(root, { user, onLogout });
  });

  document.getElementById("topbar-notices-btn")?.addEventListener("click", () => {
    if (validIds.has("notices")) {
      shellState.activeRoute = "notices";
      renderDashboardShell(root, { user, onLogout });
    }
  });

  const profileBtn = document.getElementById("profile-menu-btn");
  const profileDropdown = document.getElementById("profile-dropdown");
  profileBtn?.addEventListener("click", () => {
    const isHidden = profileDropdown.classList.toggle("hidden");
    profileBtn.setAttribute("aria-expanded", String(!isHidden));
  });

  document.getElementById("sidebar-logout-btn")?.addEventListener("click", handleLogout);
  document.getElementById("dropdown-logout-btn")?.addEventListener("click", handleLogout);
}
