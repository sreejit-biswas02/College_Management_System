import { deleteFile, getFileDownload } from "../api/filesApi.js";
import { showToast } from "./toast.js";
import { escapeHtml } from "./ui.js";

export const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"];

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

export function renderFileListHtml(files, { canDelete = false } = {}) {
  if (!files || !files.length) {
    return '<p class="text-muted">No files attached.</p>';
  }
  return `
    <ul style="display:flex;flex-direction:column;gap:0.5rem;">
      ${files
        .map(
          (f) => `
        <li style="display:flex;align-items:center;justify-content:space-between;gap:0.75rem;padding:0.5rem 0.75rem;border:1px solid var(--color-border);border-radius:6px;">
          <div>
            <strong>${escapeHtml(f.original_filename)}</strong>
            <span class="text-muted">(${escapeHtml(formatBytes(f.file_size))})</span>
          </div>
          <div style="display:flex;gap:0.4rem;">
            <button class="btn btn-outline btn-sm file-dl-btn" data-file-id="${f.id}" type="button">Download</button>
            ${
              canDelete
                ? `<button class="btn btn-danger btn-sm file-del-btn" data-file-id="${f.id}" type="button">Delete</button>`
                : ""
            }
          </div>
        </li>`
        )
        .join("")}
    </ul>
  `;
}

export function bindFileListActions(container, { onDeleted } = {}) {
  container.querySelectorAll(".file-dl-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const res = await getFileDownload(btn.dataset.fileId);
        window.open(res.download_url, "_blank", "noopener,noreferrer");
      } catch (err) {
        showToast(err.message || "Download failed.", "error");
      } finally {
        btn.disabled = false;
      }
    });
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
