import { CONFIG, ROLE_NAVIGATION } from "../config.js";
import { renderIcon } from "./icons.js";
import { escapeHtml } from "./ui.js";

export function renderSidebar({ user, activeRoute, collapsed, mobileOpen }) {
  const items = ROLE_NAVIGATION[user.role] || [];
  const classes = [
    "sidebar",
    collapsed ? "collapsed" : "",
    mobileOpen ? "mobile-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const navHtml = items
    .map((item) => {
      const isActive = item.id === activeRoute;
      return `
        <button
          class="nav-item ${isActive ? "active" : ""}"
          data-route="${escapeHtml(item.id)}"
          type="button"
          aria-current="${isActive ? "page" : "false"}"
        >
          ${renderIcon(item.icon)}
          <span class="nav-label">${escapeHtml(item.label)}</span>
        </button>
      `;
    })
    .join("");

  return `
    <div id="sidebar-overlay" class="sidebar-overlay ${mobileOpen ? "active" : ""}"></div>
    <aside id="app-sidebar" class="${classes}" aria-label="Primary Navigation">
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <span class="brand-logo">CMS</span>
          <span class="brand-text">${escapeHtml(CONFIG.APP_NAME)}</span>
        </div>
        <button
          id="sidebar-collapse-btn"
          class="btn-icon desktop-only"
          type="button"
          aria-label="Toggle sidebar"
          title="Toggle sidebar"
        >
          ${renderIcon("chevronLeft")}
        </button>
      </div>
      <nav class="sidebar-nav">${navHtml}</nav>
      <div class="sidebar-footer">
        <button id="sidebar-logout-btn" class="nav-item" type="button">
          ${renderIcon("logOut")}
          <span class="nav-label">Sign Out</span>
        </button>
      </div>
    </aside>
  `;
}
