import { escapeHtml } from "./ui.js";

export function renderSearchableSelectField({
  id,
  name,
  label,
  placeholder = "Search...",
  required = false,
  helperText = "",
}) {
  return `
    <div class="form-group">
      <label class="form-label" for="${escapeHtml(id)}-input">${escapeHtml(label)}</label>
      <div class="searchable-select" data-ss-id="${escapeHtml(id)}">
        <input
          type="hidden"
          id="${escapeHtml(id)}"
          name="${escapeHtml(name)}"
          ${required ? "required" : ""}
        />
        <div class="searchable-select-control">
          <input
            id="${escapeHtml(id)}-input"
            type="text"
            class="form-control searchable-select-input"
            placeholder="${escapeHtml(placeholder)}"
            autocomplete="off"
            role="combobox"
            aria-expanded="false"
            aria-autocomplete="list"
            aria-controls="${escapeHtml(id)}-listbox"
          />
          <button
            id="${escapeHtml(id)}-clear"
            type="button"
            class="searchable-select-clear hidden"
            aria-label="Clear ${escapeHtml(label)}"
          >&times;</button>
        </div>
        <div
          id="${escapeHtml(id)}-listbox"
          class="searchable-select-dropdown hidden"
          role="listbox"
        ></div>
      </div>
      ${helperText ? `<small class="text-muted">${escapeHtml(helperText)}</small>` : ""}
      <span id="${escapeHtml(id)}-error" class="field-error hidden"></span>
    </div>
  `;
}

export function initSearchableSelect({
  id,
  fetchOptions,
  mapOption,
  emptyMessage = "No matching records found.",
  loadErrorMessage = "Unable to load options.",
  debounceMs = 200,
  pageSize = 20,
  onChange = null,
}) {
  const hiddenEl = document.getElementById(id);
  const inputEl = document.getElementById(`${id}-input`);
  const clearBtn = document.getElementById(`${id}-clear`);
  const listboxEl = document.getElementById(`${id}-listbox`);
  const errorEl = document.getElementById(`${id}-error`);
  const rootEl = hiddenEl?.closest(".searchable-select");

  if (!hiddenEl || !inputEl || !listboxEl) {
    return null;
  }

  let options = [];
  let currentPage = 1;
  let totalPages = 1;
  let totalItems = 0;
  let currentQuery = "";
  let isOpen = false;
  let isLoading = false;
  let loadError = "";
  let activeIndex = -1;
  let selectedOption = null;
  let debounceTimer = null;
  let requestSeq = 0;

  function setError(message = "") {
    if (!errorEl) return;
    if (message) {
      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
      inputEl.setAttribute("aria-invalid", "true");
    } else {
      errorEl.textContent = "";
      errorEl.classList.add("hidden");
      inputEl.setAttribute("aria-invalid", "false");
    }
  }

  function updateClearVisibility() {
    if (!clearBtn) return;
    if (hiddenEl.value || inputEl.value) {
      clearBtn.classList.remove("hidden");
    } else {
      clearBtn.classList.add("hidden");
    }
  }

  function positionDropdown() {
    if (!isOpen || !document.body.contains(inputEl)) {
      return;
    }
    const rect = inputEl.getBoundingClientRect();
    const gap = 4;
    const viewportMargin = 12;
    const spaceBelow = window.innerHeight - rect.bottom - gap - viewportMargin;
    const spaceAbove = rect.top - gap - viewportMargin;
    const flipAbove = spaceBelow < 180 && spaceAbove > spaceBelow;
    const maxHeight = Math.max(
      120,
      Math.min(260, flipAbove ? spaceAbove : spaceBelow)
    );

    listboxEl.style.left = `${Math.max(8, rect.left)}px`;
    listboxEl.style.width = `${Math.min(rect.width, window.innerWidth - 16)}px`;
    listboxEl.style.maxHeight = `${maxHeight}px`;

    if (flipAbove) {
      listboxEl.style.top = "auto";
      listboxEl.style.bottom = `${window.innerHeight - rect.top + gap}px`;
    } else {
      listboxEl.style.bottom = "auto";
      listboxEl.style.top = `${rect.bottom + gap}px`;
    }
  }

  function openDropdown() {
    isOpen = true;
    if (listboxEl.parentElement !== document.body) {
      listboxEl.setAttribute("data-ss-portal", id);
      document.body.appendChild(listboxEl);
    }
    listboxEl.classList.remove("hidden");
    inputEl.setAttribute("aria-expanded", "true");
    positionDropdown();
  }

  function closeDropdown() {
    isOpen = false;
    activeIndex = -1;
    listboxEl.classList.add("hidden");
    inputEl.setAttribute("aria-expanded", "false");
  }

  function selectOption(opt) {
    selectedOption = opt;
    hiddenEl.value = opt.value;
    inputEl.value = opt.description ? `${opt.label}` : opt.label;
    setError("");
    updateClearVisibility();
    closeDropdown();
    if (onChange) {
      onChange(opt.value, opt.raw ?? opt);
    }
  }

  function clear() {
    selectedOption = null;
    hiddenEl.value = "";
    inputEl.value = "";
    setError("");
    updateClearVisibility();
    if (onChange) {
      onChange(null, null);
    }
  }

  function renderDropdown() {
    positionDropdown();
    if (isLoading && options.length === 0) {
      listboxEl.innerHTML = `<div class="searchable-select-state">Loading...</div>`;
      return;
    }

    if (loadError) {
      listboxEl.innerHTML = `
        <div class="searchable-select-state searchable-select-error">
          <span>${escapeHtml(loadError)}</span>
          <button type="button" class="btn btn-outline btn-sm ss-retry-btn">Retry</button>
        </div>
      `;
      listboxEl.querySelector(".ss-retry-btn")?.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
      listboxEl.querySelector(".ss-retry-btn")?.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        loadPage(1, currentQuery, false);
      });
      return;
    }

    if (options.length === 0) {
      listboxEl.innerHTML = `<div class="searchable-select-state">${escapeHtml(emptyMessage)}</div>`;
      return;
    }

    const itemsHtml = options
      .map((opt, idx) => {
        const isSelected = hiddenEl.value === opt.value;
        const isActive = idx === activeIndex;
        return `
          <button
            type="button"
            class="searchable-select-option${isSelected ? " is-selected" : ""}${isActive ? " is-active" : ""}"
            role="option"
            aria-selected="${isSelected ? "true" : "false"}"
            data-ss-index="${idx}"
          >
            <span class="searchable-select-option-label">${escapeHtml(opt.label)}</span>
            ${
              opt.description
                ? `<span class="searchable-select-option-desc">${escapeHtml(opt.description)}</span>`
                : ""
            }
          </button>
        `;
      })
      .join("");

    const footerHtml =
      currentPage < totalPages
        ? `
          <div class="searchable-select-footer">
            <button type="button" class="btn btn-outline btn-sm ss-load-more-btn" ${isLoading ? "disabled" : ""}>
              ${isLoading ? "Loading..." : `Load more (${options.length} of ${totalItems})`}
            </button>
          </div>
        `
        : "";

    listboxEl.innerHTML = `${itemsHtml}${footerHtml}`;

    listboxEl.querySelectorAll(".searchable-select-option").forEach((btn) => {
      btn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const idx = Number(btn.dataset.ssIndex);
        if (options[idx]) {
          selectOption(options[idx]);
        }
      });
    });

    const loadMoreBtn = listboxEl.querySelector(".ss-load-more-btn");
    loadMoreBtn?.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    loadMoreBtn?.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    loadMoreBtn?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      loadPage(currentPage + 1, currentQuery, true);
    });
  }

  async function loadPage(page = 1, search = "", append = false) {
    const seq = ++requestSeq;
    isLoading = true;
    loadError = "";
    currentQuery = search;
    if (!append) {
      options = [];
      activeIndex = -1;
    }
    if (isOpen) {
      renderDropdown();
    }
    try {
      const res = await fetchOptions({ search: search.trim(), page, pageSize });
      if (seq !== requestSeq) return;
      const mapped = (res.items || []).map((item) => ({
        ...mapOption(item),
        raw: item,
      }));
      options = append ? [...options, ...mapped] : mapped;
      currentPage = res.page || page;
      totalPages = res.pages || 1;
      totalItems = res.total ?? options.length;
    } catch (err) {
      if (seq !== requestSeq) return;
      loadError = err.message || loadErrorMessage;
    } finally {
      if (seq === requestSeq) {
        isLoading = false;
        if (isOpen) {
          renderDropdown();
        }
      }
    }
  }

  function handleFocus() {
    openDropdown();
    if (options.length === 0 && !isLoading) {
      loadPage(1, selectedOption ? "" : inputEl.value, false);
    } else {
      renderDropdown();
    }
  }

  function handleInput() {
    if (selectedOption && inputEl.value !== selectedOption.label) {
      selectedOption = null;
      hiddenEl.value = "";
    }
    setError("");
    updateClearVisibility();
    openDropdown();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      loadPage(1, inputEl.value, false);
    }, debounceMs);
  }

  function handleKeydown(e) {
    if (!isOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      openDropdown();
      if (options.length === 0 && !isLoading) {
        loadPage(1, inputEl.value, false);
      } else {
        renderDropdown();
      }
      return;
    }
    if (!isOpen) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (options.length > 0) {
        activeIndex = (activeIndex + 1) % options.length;
        renderDropdown();
        listboxEl
          .querySelector(`[data-ss-index="${activeIndex}"]`)
          ?.scrollIntoView({ block: "nearest" });
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (options.length > 0) {
        activeIndex = activeIndex <= 0 ? options.length - 1 : activeIndex - 1;
        renderDropdown();
        listboxEl
          .querySelector(`[data-ss-index="${activeIndex}"]`)
          ?.scrollIntoView({ block: "nearest" });
      }
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && options[activeIndex]) {
        e.preventDefault();
        selectOption(options[activeIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeDropdown();
    }
  }

  function handleDocumentClick(e) {
    if (!document.body.contains(inputEl)) {
      destroy();
      return;
    }
    if (
      rootEl &&
      !rootEl.contains(e.target) &&
      !listboxEl.contains(e.target)
    ) {
      closeDropdown();
    }
  }

  function handleViewportChange() {
    if (!document.body.contains(inputEl)) {
      destroy();
      return;
    }
    if (isOpen) {
      positionDropdown();
    }
  }

  function destroy() {
    clearTimeout(debounceTimer);
    document.removeEventListener("click", handleDocumentClick);
    window.removeEventListener("resize", handleViewportChange);
    window.removeEventListener("scroll", handleViewportChange, true);
    listboxEl.remove();
  }

  inputEl.addEventListener("focus", handleFocus);
  inputEl.addEventListener("input", handleInput);
  inputEl.addEventListener("keydown", handleKeydown);
  clearBtn?.addEventListener("click", () => {
    clear();
    inputEl.focus();
    openDropdown();
    loadPage(1, "", false);
  });
  document.addEventListener("click", handleDocumentClick);
  window.addEventListener("resize", handleViewportChange);
  window.addEventListener("scroll", handleViewportChange, true);

  return {
    getValue: () => hiddenEl.value,
    setValue: (opt) => {
      if (!opt) {
        clear();
      } else {
        selectOption(opt);
      }
    },
    clear,
    reload: () => loadPage(1, inputEl.value, false),
    setError,
    destroy,
  };
}
