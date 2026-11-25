import { renderDataTable } from "../components/dataTable.js";
import { renderStatusBadge, escapeHtml } from "../components/ui.js";
import { ROLE_NAVIGATION } from "../config.js";

export function renderRoleFoundationPage(container, { user, routeItem }) {
  const navItems = ROLE_NAVIGATION[user.role] || [];
  const sampleRows = navItems.map((item, idx) => ({
    index: idx + 1,
    module: item.label,
    routeId: `#/${user.role}/${item.id}`,
    status: item.id === "dashboard" ? "Ready" : "Foundation Shell",
  }));

  container.innerHTML = `
    <section class="stats-grid" aria-label="Session Overview">
      <div class="stat-card">
        <div class="text-muted">Authenticated Role</div>
        <div class="stat-value">${escapeHtml(user.role.toUpperCase())}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Account Status</div>
        <div class="stat-value">${user.is_active ? "Active" : "Inactive"}</div>
      </div>
      <div class="stat-card">
        <div class="text-muted">Available Modules</div>
        <div class="stat-value">${navItems.length}</div>
      </div>
    </section>

    <section class="card">
      <div class="card-header">
        <div>
          <h2 class="card-title">${escapeHtml(routeItem.label)}</h2>
          <p class="text-muted">
            Phase 4 Part 1 foundation view for <strong>${escapeHtml(user.full_name)}</strong>.
            Role-specific CRUD modules will be wired in Phase 4 Part 2.
          </p>
        </div>
        ${renderStatusBadge(user.role, "info")}
      </div>

      ${renderDataTable({
        columns: [
          { key: "index", label: "#" },
          { key: "module", label: "Navigation Module" },
          { key: "routeId", label: "Route" },
          {
            key: "status",
            label: "Phase Status",
            render: (row) =>
              renderStatusBadge(
                row.status,
                row.status === "Ready" ? "success" : "info"
              ),
          },
        ],
        rows: sampleRows,
      })}
    </section>
  `;
}
