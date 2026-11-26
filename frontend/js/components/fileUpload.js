import { deleteFile, getFileDownload } from "../api/filesApi.js";
import { renderIcon } from "./icons.js";
import { showToast } from "./toast.js";
import { escapeHtml } from "./ui.js";

export const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"];

const VIEWABLE_MIME_TYPES = new Set([
  "application/pdf",
  "image/png",
  "image/jpeg",
  "text/plain",
]);

export function getFileTypeInfo(file) {
  const name = (file?.original_filename || "").toLowerCase();
  const mime = (file?.content_type || "").toLowerCase();
  if (mime === "application/pdf" || name.endsWith(".pdf")) {
    return { icon: "fileText", typeLabel: "PDF", viewable: true };
  }
  if (
    mime.startsWith("image/") ||
    name.endsWith(".png") ||
    name.endsWith(".jpg") ||
    name.endsWith(".jpeg")
  ) {
    return { icon: "fileText", typeLabel: "Image", viewable: true };
  }
  if (
    mime.includes("word") ||
    name.endsWith(".doc") ||
    name.endsWith(".docx")
  ) {
    return { icon: "fileText", typeLabel: "Word", viewable: false };
  }
  if (mime === "text/plain" || name.endsWith(".txt")) {
    return { icon: "fileText", typeLabel: "Text", viewable: true };
  }
  return {
    icon: "fileText",
    typeLabel: "File",
    viewable: VIEWABLE_MIME_TYPES.has(mime),
  };
}

export function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function validateClientFile(file, maxBytes) {
  if (!file) return "Please select a file.";
  if (file.size === 0) return "Selected file is empty.";
  if (file.size > maxBytes) {
    return `File exceeds ${Math.round(maxBytes / (1024 * 1024))} MB limit.`;
  }
  const lower = file.name.toLowerCase();
  const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  if (!hasValidExt) {
    return `Unsupported format. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
  }
  return null;
}

export function renderFileListHtml(files, { canDelete = false, compact = false } = {}) {
  if (!files || !files.length) {
    return '<span class="text-muted">No files attached.</span>';
  }
  return `
    <ul style="display:flex;flex-direction:column;gap:${compact ? "0.35rem" : "0.5rem"};list-style:none;padding:0;margin:0;">
      ${files
        .map((f) => {
          const info = getFileTypeInfo(f);
          return `
        <li style="display:flex;align-items:center;justify-content:space-between;gap:0.65rem;flex-wrap:wrap;padding:${compact ? "0.4rem 0.6rem" : "0.5rem 0.75rem"};border:1px solid var(--color-border);border-radius:6px;background:var(--color-surface);">
          <div style="display:flex;align-items:center;gap:0.45rem;min-width:0;">
            <span aria-hidden="true" style="display:inline-flex;color:var(--color-primary);flex-shrink:0;">${renderIcon(info.icon)}</span>
            <div style="min-width:0;">
              <button
                class="file-name-link"
                data-file-id="${f.id}"
                data-inline="${info.viewable ? "true" : "false"}"
                type="button"
                style="background:none;border:none;padding:0;color:var(--color-primary);font-weight:600;text-align:left;cursor:pointer;text-decoration:underline;word-break:break-word;"
              >${escapeHtml(f.original_filename)}</button>
              <div class="text-muted" style="font-size:0.75rem;">
                ${escapeHtml(info.typeLabel)} &bull; ${escapeHtml(formatBytes(f.file_size))}
              </div>
            </div>
          </div>
          <div style="display:flex;gap:0.35rem;flex-shrink:0;">
            ${
              info.viewable
                ? `<button class="btn btn-primary btn-sm file-view-btn" data-file-id="${f.id}" type="button">View</button>`
                : ""
            }
            <button class="btn btn-outline btn-sm file-dl-btn" data-file-id="${f.id}" type="button">Download</button>
            ${
              canDelete
                ? `<button class="btn btn-danger btn-sm file-del-btn" data-file-id="${f.id}" type="button">Delete</button>`
                : ""
            }
          </div>
        </li>`;
        })
        .join("")}
    </ul>
  `;
}

export function bindFileListActions(container, { onDeleted } = {}) {
  if (!container) return;

  async function openAuthorizedFile(triggerEl, inline) {
    triggerEl.disabled = true;
    try {
      const res = await getFileDownload(triggerEl.dataset.fileId, { inline });
      window.open(res.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      showToast(err.message || "File unavailable or access denied.", "error");
    } finally {
      triggerEl.disabled = false;
    }
  }

  container.querySelectorAll(".file-name-link").forEach((btn) => {
    btn.addEventListener("click", () =>
      openAuthorizedFile(btn, btn.dataset.inline === "true")
    );
  });

  container.querySelectorAll(".file-view-btn").forEach((btn) => {
    btn.addEventListener("click", () => openAuthorizedFile(btn, true));
  });

  container.querySelectorAll(".file-dl-btn").forEach((btn) => {
    btn.addEventListener("click", () => openAuthorizedFile(btn, false));
  });

  container.querySelectorAll(".file-del-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await deleteFile(btn.dataset.fileId);
        showToast("File deleted.", "success");
        if (onDeleted) await onDeleted();
      } catch (err) {
        showToast(err.message || "Delete failed.", "error");
        btn.disabled = false;
      }
    });
  });
}
