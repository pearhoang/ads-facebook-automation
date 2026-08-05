(function () {
  "use strict";

  const csrfToken = document.body.dataset.csrfToken || "";
  const accountToggle = document.querySelector("[data-account-menu-toggle]");
  const accountMenu = document.getElementById("sidebar-account-menu");

  const globalSearch = document.querySelector("[data-global-search]");
  const searchableBodies = Array.from(document.querySelectorAll(".table-wrap tbody"));

  function normalizeSearchText(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("vi").trim();
  }

  function applyGlobalSearch() {
    if (!globalSearch) return;
    const query = normalizeSearchText(globalSearch.value);
    let visibleCount = 0;
    searchableBodies.forEach((body) => {
      Array.from(body.rows).forEach((row) => {
        const visible = !query || normalizeSearchText(row.textContent).includes(query);
        row.hidden = !visible;
        if (visible) visibleCount += 1;
      });
    });
    globalSearch.setAttribute("aria-label", query ? `Tìm kiếm trong trang, ${visibleCount} kết quả` : "Tìm kiếm trong trang");
  }

  if (globalSearch) {
    globalSearch.addEventListener("input", applyGlobalSearch);
    searchableBodies.forEach((body) => new MutationObserver(applyGlobalSearch).observe(body, { childList: true }));
    document.addEventListener("keydown", (event) => {
      const target = event.target;
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey || target?.matches("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      globalSearch.focus();
    });
  }

  const notificationToggle = document.querySelector("[data-notification-toggle]");
  const notificationPopover = document.querySelector("[data-notification-popover]");
  const notificationList = document.querySelector("[data-notification-list]");
  const notificationSummary = document.querySelector("[data-notification-summary]");
  const notificationDot = document.querySelector("[data-notification-dot]");
  const notificationSources = Array.from(document.querySelectorAll("[data-notification-label]"));

  function spriteIcon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `/static/ui-icons.svg#${name}`);
    svg.append(use);
    return svg;
  }

  document.querySelectorAll(".section-toolbar").forEach((toolbar) => {
    const copy = toolbar.querySelector(":scope > div:first-child");
    const heading = copy?.querySelector("h2")?.textContent || "";
    if (!copy || copy.classList.contains("section-heading")) return;
    const normalized = normalizeSearchText(heading);
    let iconName = "layout";
    let tone = "";
    if (normalized.includes("account") || normalized.includes("tai khoan")) iconName = "credit-card";
    else if (normalized.includes("resource")) { iconName = "blocks"; tone = "green"; }
    else if (normalized.includes("asset")) { iconName = "image"; tone = "green"; }
    else if (normalized.includes("duyet") || normalized.includes("lich")) { iconName = "clock"; tone = "amber"; }
    else if (normalized.includes("job") || normalized.includes("audit") || normalized.includes("kpi") || normalized.includes("thao tac")) { iconName = "activity"; tone = "purple"; }
    else if (normalized.includes("cong viec")) { iconName = "layout"; tone = "purple"; }
    else if (normalized.includes("provider") || normalized.includes("hermes")) iconName = "bot";
    else if (normalized.includes("bot") || normalized.includes("node")) iconName = "server";
    else if (normalized.includes("campaign")) { iconName = "layout"; tone = "purple"; }

    const cluster = document.createElement("div");
    cluster.className = "section-heading";
    const icon = document.createElement("span");
    icon.className = `section-icon${tone ? ` ${tone}` : ""}`;
    icon.append(spriteIcon(iconName));
    toolbar.insertBefore(cluster, copy);
    cluster.append(icon, copy);

    toolbar.querySelectorAll(":scope > .button").forEach((button) => {
      if (!button.querySelector("svg") && /^(Thêm|Tạo|Tải)/u.test(button.textContent.trim())) button.prepend(spriteIcon("plus"));
    });
  });

  function closeNotifications() {
    if (!notificationToggle || !notificationPopover) return;
    notificationPopover.hidden = true;
    notificationToggle.setAttribute("aria-expanded", "false");
  }

  function notificationIcon(tone) {
    return spriteIcon(tone === "danger" ? "circle-alert" : "clock");
  }

  function renderNotifications() {
    if (!notificationList || !notificationSummary || !notificationDot) return;
    const items = notificationSources.map((source) => {
      const value = Number.parseInt((source.querySelector(".metric-value")?.textContent || "0").replace(/[^0-9-]/g, ""), 10) || 0;
      return { value, label: source.dataset.notificationLabel || "mục cần xử lý", tone: source.dataset.notificationTone || "warning" };
    }).filter((item) => item.value > 0);

    notificationList.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "notification-empty";
      empty.textContent = "Không có cảnh báo cần xử lý trên trang này.";
      notificationList.append(empty);
      notificationSummary.textContent = "Không có cảnh báo";
      notificationDot.hidden = true;
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = `notification-item ${item.tone}`;
      const icon = document.createElement("span");
      icon.className = "notification-item-icon";
      icon.append(notificationIcon(item.tone));
      const copy = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `${item.value} ${item.label}`;
      const detail = document.createElement("span");
      detail.textContent = item.tone === "danger" ? "Cần kiểm tra và xử lý sớm." : "Đang chờ bạn kiểm tra.";
      copy.append(title, detail);
      row.append(icon, copy);
      notificationList.append(row);
    });
    notificationSummary.textContent = `${items.length} mục cần chú ý`;
    notificationDot.hidden = false;
  }

  if (notificationToggle && notificationPopover) {
    notificationToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = notificationPopover.hidden;
      notificationPopover.hidden = !willOpen;
      notificationToggle.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) renderNotifications();
    });
    notificationPopover.addEventListener("click", (event) => event.stopPropagation());
    notificationSources.forEach((source) => {
      const value = source.querySelector(".metric-value");
      if (value) new MutationObserver(renderNotifications).observe(value, { childList: true, characterData: true, subtree: true });
    });
    renderNotifications();
  }

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
    document.addEventListener("click", () => {
      closeAccountMenu();
      closeNotifications();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAccountMenu();
        closeNotifications();
      }
    });
  } else {
    document.addEventListener("click", closeNotifications);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeNotifications();
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
