(function () {
  "use strict";

  const csrfToken = document.body.dataset.csrfToken || "";
  const accountToggle = document.querySelector("[data-account-menu-toggle]");
  const accountMenu = document.getElementById("sidebar-account-menu");

  function closeAccountMenu() {
    if (!accountMenu || !accountToggle) return;
    accountMenu.hidden = true;
    accountToggle.setAttribute("aria-expanded", "false");
  }

  if (accountToggle && accountMenu) {
    accountToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = accountMenu.hidden;
      accountMenu.hidden = !willOpen;
      accountToggle.setAttribute("aria-expanded", String(willOpen));
    });
    accountMenu.addEventListener("click", (event) => {
      event.stopPropagation();
      if (event.target.closest("button")) closeAccountMenu();
    });
    document.addEventListener("click", closeAccountMenu);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeAccountMenu();
    });
  }

  const logoutButton = document.querySelector("[data-global-logout]");
  if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
      logoutButton.disabled = true;
      try {
        const response = await fetch("/api/auth/logout", {
          method: "POST",
          credentials: "same-origin",
          headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
        });
        if (!response.ok && response.status !== 401) throw new Error(`HTTP ${response.status}`);
        window.location.assign("/login");
      } catch (_error) {
        logoutButton.disabled = false;
      }
    });
  }

  const valueDescriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  const enhancedSelects = new WeakMap();

  function optionLabel(select) {
    const option = select.options[select.selectedIndex];
    return option ? option.textContent.trim() : "Chưa có lựa chọn";
  }

  function positionMenu(button, menu) {
    const rect = button.getBoundingClientRect();
    const gap = 4;
    const viewportPadding = 12;
    const menuHeight = Math.min(menu.scrollHeight, 280);
    const roomBelow = window.innerHeight - rect.bottom - gap - viewportPadding;
    const roomAbove = rect.top - gap - viewportPadding;
    const openAbove = roomBelow < Math.min(menuHeight, 168) && roomAbove > roomBelow;
    const width = Math.min(rect.width, window.innerWidth - viewportPadding * 2);
    const left = Math.min(Math.max(viewportPadding, rect.left), window.innerWidth - width - viewportPadding);
    const top = openAbove ? Math.max(viewportPadding, rect.top - gap - menuHeight) : rect.bottom + gap;
    menu.style.width = `${Math.round(width)}px`;
    menu.style.maxHeight = "280px";
    menu.style.left = `${Math.round(left)}px`;
    menu.style.top = `${Math.round(top)}px`;
  }

  function syncSelect(select) {
    const state = enhancedSelects.get(select);
    if (!state) return;
    const selectedLabel = optionLabel(select);
    state.label.textContent = selectedLabel;
    state.button.setAttribute("aria-label", state.fieldName ? `${state.fieldName}: ${selectedLabel}` : selectedLabel);
    state.button.disabled = select.disabled;
  }

  function rebuildMenu(select) {
    const state = enhancedSelects.get(select);
    if (!state) return;
    state.menu.replaceChildren(...Array.from(select.options).map((option) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "ui-select-option";
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.selected));
      item.disabled = option.disabled;
      item.dataset.value = option.value;
      item.textContent = option.textContent;
      item.addEventListener("click", () => {
        select.value = option.value;
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncSelect(select);
        if (state.menu.matches(":popover-open")) state.menu.hidePopover();
        state.button.focus();
      });
      return item;
    }));
  }

  function enhanceSelect(select) {
    if (enhancedSelects.has(select) || select.multiple || select.size > 1) return;
    const wrapper = document.createElement("span");
    wrapper.className = "ui-select";
    select.before(wrapper);
    wrapper.append(select);
    select.classList.add("ui-select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "ui-select-trigger";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const label = document.createElement("span");
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("viewBox", "0 0 24 24");
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = '<path d="m6 9 6 6 6-6"/>';
    button.append(label, chevron);
    wrapper.append(button);

    const menu = document.createElement("div");
    menu.className = "ui-select-menu";
    menu.setAttribute("popover", "auto");
    menu.setAttribute("role", "listbox");
    document.body.append(menu);
    const fieldLabel = select.closest("label");
    const fieldName = fieldLabel
      ? Array.from(fieldLabel.childNodes).filter((node) => node.nodeType === 3).map((node) => node.textContent).join(" ").trim()
      : "";
    enhancedSelects.set(select, { wrapper, button, label, menu, fieldName });

    if (valueDescriptor) {
      Object.defineProperty(select, "value", {
        configurable: true,
        get() { return valueDescriptor.get.call(this); },
        set(value) {
          valueDescriptor.set.call(this, value);
          queueMicrotask(() => syncSelect(this));
        },
      });
    }

    rebuildMenu(select);
    syncSelect(select);
    select.addEventListener("change", () => syncSelect(select));
    new MutationObserver(() => {
      rebuildMenu(select);
      syncSelect(select);
    }).observe(select, { childList: true, subtree: true, attributes: true });

    button.addEventListener("click", () => {
      if (button.disabled) return;
      if (menu.matches(":popover-open")) {
        menu.hidePopover();
        return;
      }
      rebuildMenu(select);
      menu.showPopover();
      positionMenu(button, menu);
      button.setAttribute("aria-expanded", "true");
      const selected = menu.querySelector('[aria-selected="true"]');
      if (selected) selected.scrollIntoView({ block: "nearest" });
    });
    menu.addEventListener("toggle", (event) => {
      button.setAttribute("aria-expanded", String(event.newState === "open"));
    });
    button.addEventListener("keydown", (event) => {
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      if (!menu.matches(":popover-open")) button.click();
      const options = Array.from(menu.querySelectorAll(".ui-select-option:not(:disabled)"));
      const selectedIndex = options.findIndex((item) => item.getAttribute("aria-selected") === "true");
      const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : event.key === "ArrowUp" ? Math.max(0, selectedIndex - 1) : Math.min(options.length - 1, selectedIndex + 1);
      options[next]?.focus();
    });
    select.form?.addEventListener("reset", () => setTimeout(() => syncSelect(select)));
  }

  document.querySelectorAll("select").forEach(enhanceSelect);
  function forEachOpenSelect(callback) {
    document.querySelectorAll("select").forEach((select) => {
      const state = enhancedSelects.get(select);
      if (state?.menu.matches(":popover-open")) callback(state);
    });
  }
  window.addEventListener("resize", () => forEachOpenSelect((state) => positionMenu(state.button, state.menu)));
  window.addEventListener("scroll", () => forEachOpenSelect((state) => state.menu.hidePopover()), true);
  window.syncUiSelects = function () {
    document.querySelectorAll("select").forEach((select) => {
      if (!enhancedSelects.has(select)) enhanceSelect(select);
      rebuildMenu(select);
      syncSelect(select);
    });
  };
})();
