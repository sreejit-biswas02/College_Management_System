import { renderIcon } from "./icons.js";
import { escapeHtml, renderStatusBadge } from "./ui.js";

export function renderNavbar({ user, pageTitle, breadcrumb }) {
  return `
    <header class="topbar">
      <div class="topbar-left">
        <button
          id="mobile-menu-btn"
          class="btn-icon mobile-only"
          type="button"
          aria-label="Open navigation menu"
        >
          ${renderIcon("menu")}
        </button>
        <div class="topbar-title-group">
          <span class="breadcrumbs">${escapeHtml(breadcrumb)}</span>
          <h1 class="page-heading">${escapeHtml(pageTitle)}</h1>
        </div>
      </div>

      <div class="topbar-right">
        <button
          id="topbar-notices-btn"
          class="btn-icon"
          type="button"
          aria-label="View notices"
          title="Notices"
        >
          ${renderIcon("bell")}
        </button>

        <div class="dropdown">
          <button
            id="profile-menu-btn"
            class="profile-trigger"
            type="button"
            aria-haspopup="true"
            aria-expanded="false"
          >
            ${renderIcon("user")}
            <span>${escapeHtml(user.full_name)}</span>
            ${renderStatusBadge(user.role, "info")}
            ${renderIcon("chevronDown")}
          </button>
          <div id="profile-dropdown" class="dropdown-menu hidden" role="menu">
            <div style="padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--color-border); margin-bottom: 0.25rem;">
              <div style="font-weight: 600; font-size: 0.85rem;">${escapeHtml(user.full_name)}</div>
              <div class="text-muted" style="font-size: 0.75rem;">${escapeHtml(user.email)}</div>
            </div>
            <button id="dropdown-logout-btn" class="dropdown-item" type="button" role="menuitem">
              ${renderIcon("logOut")}
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  `;
}
