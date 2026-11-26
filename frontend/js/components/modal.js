import { renderIcon } from "./icons.js";
import { escapeHtml } from "./ui.js";

let activeOnClose = null;
let escapeListener = null;

export function closeModal() {
  document
    .querySelectorAll("body > .searchable-select-dropdown[data-ss-portal]")
    .forEach((el) => el.remove());
  if (escapeListener) {
    document.removeEventListener("keydown", escapeListener);
    escapeListener = null;
  }
  const cleanup = activeOnClose;
  activeOnClose = null;
  if (cleanup) {
    cleanup();
  }
  const root = document.getElementById("modal-root");
  if (root) {
    root.innerHTML = "";
  }
}

export function openModal({ title, bodyHtml, footerHtml = "", onClose = null }) {
  const root = document.getElementById("modal-root");
  if (!root) {
    return;
  }
  closeModal();
  activeOnClose = onClose;

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

  const backdropEl = root.querySelector(".modal-backdrop");
  const dialogEl = root.querySelector(".modal-dialog");

  function isInsideModalOrPortal(event) {
    const path = typeof event.composedPath === "function" ? event.composedPath() : [];
    const portals = Array.from(
      document.querySelectorAll("body > .searchable-select-dropdown[data-ss-portal]")
    );
    const target = event.target;

    if (dialogEl && (path.includes(dialogEl) || dialogEl.contains(target))) {
      return true;
    }
    return portals.some(
      (portal) => path.includes(portal) || portal.contains(target)
    );
  }

  let pointerStartedInside = false;
  backdropEl?.addEventListener("pointerdown", (e) => {
    pointerStartedInside = isInsideModalOrPortal(e);
  });
  backdropEl?.addEventListener("mousedown", (e) => {
    if (isInsideModalOrPortal(e)) {
      pointerStartedInside = true;
    }
  });

  root.querySelector("#modal-close-btn")?.addEventListener("click", closeModal);
  backdropEl?.addEventListener("click", (e) => {
    const inside = pointerStartedInside || isInsideModalOrPortal(e);
    pointerStartedInside = false;
    if (!inside) {
      closeModal();
    }
  });
  escapeListener = (e) => {
    if (e.key === "Escape") {
      const openDropdown = document.querySelector(
        "body > .searchable-select-dropdown[data-ss-portal]:not(.hidden)"
      );
      if (openDropdown) {
        return;
      }
      closeModal();
    }
  };
  document.addEventListener("keydown", escapeListener);
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
