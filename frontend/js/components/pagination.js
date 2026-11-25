import { escapeHtml } from "./ui.js";

export function renderPagination({ page, pages, total, idPrefix = "pg" }) {
  const safePages = Math.max(pages || 1, 1);
  return `
    <div class="pagination" aria-label="Pagination">
      <span class="text-muted">Page ${escapeHtml(page)} of ${escapeHtml(safePages)} (${escapeHtml(total)} total)</span>
      <div class="pagination-controls">
        <button
          id="${escapeHtml(idPrefix)}-prev"
          class="btn btn-outline btn-sm"
          type="button"
          ${page <= 1 ? "disabled" : ""}
        >
          Previous
        </button>
        <button
          id="${escapeHtml(idPrefix)}-next"
          class="btn btn-outline btn-sm"
          type="button"
          ${page >= safePages ? "disabled" : ""}
        >
          Next
        </button>
      </div>
    </div>
  `;
}
