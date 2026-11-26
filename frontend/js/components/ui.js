import { renderIcon } from "./icons.js";

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatIndianDate(isoDate) {
  if (!isoDate) return "—";
  const match = String(isoDate).trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return String(isoDate);
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

export function formatIndianDateTime(isoDateTime) {
  if (!isoDateTime) return "—";
  const dt = new Date(isoDateTime);
  if (Number.isNaN(dt.getTime())) return formatIndianDate(isoDateTime);
  return dt.toLocaleString("en-IN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function formatTime12h(timeStr) {
  if (!timeStr) return "—";
  const parts = String(timeStr).trim().split(":");
  if (parts.length < 2) return String(timeStr);
  const hour24 = Number(parts[0]);
  const minute = parts[1];
  if (Number.isNaN(hour24)) return String(timeStr);
  const period = hour24 >= 12 ? "PM" : "AM";
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12;
  return `${String(hour12).padStart(2, "0")}:${minute} ${period}`;
}

export function formatDayOfWeek(day) {
  if (!day) return "—";
  const s = String(day).trim().toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatOfferingLabel(offering, fallback = "Not assigned") {
  if (!offering || !offering.course) return fallback;
  const code = offering.course.code || "";
  const title = offering.course.title || "";
  const sec = offering.section ? ` (Sec ${offering.section})` : "";
  return `${code} — ${title}${sec}`.trim();
}

export function formatNoticeAudience(notice) {
  const targets = notice?.targets || [];
  if (!targets.length) return "All Users";
  return targets
    .map((t) => {
      const parts = [];
      if (t.target_role) {
        const r = String(t.target_role).toLowerCase();
        parts.push(r === "student" ? "Students" : r === "faculty" ? "Faculty" : r);
      }
      if (t.department) {
        parts.push(`${t.department.code} — ${t.department.name}`);
      } else if (t.department_id) {
        parts.push(`Dept #${t.department_id}`);
      }
      if (t.course_offering?.course) {
        parts.push(
          `${t.course_offering.course.code} (Sec ${t.course_offering.section})`
        );
      } else if (t.course_offering_id) {
        parts.push(`Offering #${t.course_offering_id}`);
      }
      return parts.join(" • ") || "All Users";
    })
    .join(", ");
}

export function formatTextOrMuted(value, fallback = "—") {
  if (value === null || value === undefined || String(value).trim() === "") {
    return `<span class="text-muted">${escapeHtml(fallback)}</span>`;
  }
  return escapeHtml(value);
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
