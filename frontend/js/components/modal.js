import { renderIcon } from "./icons.js";
import { escapeHtml } from "./ui.js";

export function closeModal() {
  const root = document.getElementById("modal-root");
  if (root) {
    root.innerHTML = "";
  }
}

export function openModal({ title, bodyHtml, footerHtml = "" }) {
  const root = document.getElementById("modal-root");
  if (!root) {
    return;
  }

  root.innerHTML = `
    <div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-dialog">
        <div class="modal-header">
          <h3 id="modal-title" class="card-title">${escapeHtml(title)}</h3>
          <button id="modal-close-btn" class="btn-icon" type="button" aria-label="Close modal">
            ${renderIcon("x")}
          </button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
      </div>
    </div>
  `;

  root.querySelector("#modal-close-btn")?.addEventListener("click", closeModal);
  root.querySelector(".modal-backdrop")?.addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) {
      closeModal();
    }
  });
}

export function confirmDialog({ title, message, confirmLabel = "Confirm", onConfirm }) {
  openModal({
    title,
    bodyHtml: `<p>${escapeHtml(message)}</p>`,
    footerHtml: `
      <button id="confirm-cancel-btn" class="btn btn-outline" type="button">Cancel</button>
      <button id="confirm-ok-btn" class="btn btn-primary" type="button">${escapeHtml(confirmLabel)}</button>
    `,
  });

  document.getElementById("confirm-cancel-btn")?.addEventListener("click", closeModal);
  document.getElementById("confirm-ok-btn")?.addEventListener("click", async () => {
    closeModal();
    if (onConfirm) {
      await onConfirm();
    }
  });
}
