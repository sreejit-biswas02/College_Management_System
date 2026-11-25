import { renderIcon } from "./icons.js";

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function renderLoading(message = "Loading...") {
  return `
    <div class="state-box" role="status">
      <div class="spinner" aria-hidden="true"></div>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

export function renderEmptyState(title, description = "") {
  return `
    <div class="state-box">
      ${renderIcon("clipboardList")}
      <strong>${escapeHtml(title)}</strong>
      ${description ? `<p class="text-muted">${escapeHtml(description)}</p>` : ""}
    </div>
  `;
}

export function renderErrorState(message, retryId = "") {
  return `
    <div class="state-box" role="alert">
      ${renderIcon("alertCircle")}
      <p class="text-danger">${escapeHtml(message)}</p>
      ${
        retryId
          ? `<button id="${escapeHtml(retryId)}" class="btn btn-outline btn-sm" type="button">Retry</button>`
          : ""
      }
    </div>
  `;
}

export function renderStatusBadge(label, variant = "info") {
  return `<span class="badge badge-${escapeHtml(variant)}">${escapeHtml(label)}</span>`;
}

export function renderSearchInput({
  id,
  placeholder = "Search...",
  value = "",
  ariaLabel = "Search",
}) {
  return `
    <div class="search-box">
      ${renderIcon("search", "search-icon")}
      <input
        id="${escapeHtml(id)}"
        type="search"
        class="form-control"
        placeholder="${escapeHtml(placeholder)}"
        value="${escapeHtml(value)}"
        aria-label="${escapeHtml(ariaLabel)}"
      />
    </div>
  `;
}

export function renderFormField({
  id,
  label,
  type = "text",
  value = "",
  placeholder = "",
  required = false,
  error = "",
}) {
  return `
    <div class="form-group">
      <label class="form-label" for="${escapeHtml(id)}">${escapeHtml(label)}</label>
      <input
        id="${escapeHtml(id)}"
        name="${escapeHtml(id)}"
        type="${escapeHtml(type)}"
        class="form-control"
        value="${escapeHtml(value)}"
        placeholder="${escapeHtml(placeholder)}"
        ${required ? "required" : ""}
        aria-invalid="${error ? "true" : "false"}"
      />
      ${error ? `<span class="field-error">${escapeHtml(error)}</span>` : ""}
    </div>
  `;
}
