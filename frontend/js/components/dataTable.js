import { escapeHtml, renderEmptyState } from "./ui.js";

export function renderDataTable({
  columns,
  rows,
  emptyTitle = "No records found",
  emptyDescription = "Try adjusting your filters or create a new entry.",
}) {
  if (!rows || rows.length === 0) {
    return renderEmptyState(emptyTitle, emptyDescription);
  }

  const headHtml = columns
    .map((col) => `<th scope="col">${escapeHtml(col.label)}</th>`)
    .join("");

  const bodyHtml = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const content = col.render ? col.render(row) : escapeHtml(row[col.key]);
          return `<td>${content}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  return `
    <div class="table-container">
      <table class="data-table">
        <thead><tr>${headHtml}</tr></thead>
        <tbody>${bodyHtml}</tbody>
      </table>
    </div>
  `;
}
