const csrfToken = document.body.dataset.csrfToken;
const byId = (id) => document.getElementById(id);

const state = { requests: [], adAccounts: [], selectedId: null, statusFilter: "" };
const activeStatuses = new Set(["planning", "awaiting_approval", "queued", "running"]);

const statusLabels = {
  planning: "Đang lập kế hoạch",
  awaiting_approval: "Chờ xác nhận",
  queued: "Đang chờ worker",
  running: "Đang thao tác Meta",
  recovering: "Đang tự phục hồi",
  awaiting_user: "Cần bạn xử lý",
  completed: "Hoàn tất tại Review",
  failed: "Chưa xử lý được",
  cancelled: "Đã hủy",
};

const stageLabels = {
  intent: "Hiểu yêu cầu",
  approval: "Action preview",
  preflight: "Kiểm tra profile",
  draft_build: "Campaign → Ad Set → Ad",
  recovery: "Tự phục hồi",
  handoff: "Login / 2FA / challenge",
  review: "Dừng tại Review",
  cancelled: "Đã hủy",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function money(value, currency = "VND") {
  if (!Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value));
}

function statusTone(status) {
  if (status === "completed") return "success";
  if (status === "failed" || status === "cancelled") return "danger";
  if (status === "awaiting_user" || status === "recovering") return "warning";
  return "neutral";
}

function statusBadge(status) {
  const tone = statusTone(status);
  const icon = { neutral: "activity", success: "badge-check", warning: "clock", danger: "circle-alert" }[tone];
  return `<span class="status work-status ${tone}">${icon ? `<svg aria-hidden="true"><use href="/static/ui-icons.svg#${icon}"></use></svg>` : ""}${escapeHtml(statusLabels[status] || status)}</span>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken, ...(options.headers || {}) },
  });
  if (response.status === 401) { window.location.href = "/login"; throw new Error("Phiên đăng nhập đã hết hạn."); }
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(payload?.detail || "Yêu cầu không thành công.");
  return payload;
}

function showNotice(message, kind = "error") {
  const notice = byId("notice");
  notice.textContent = message;
  notice.className = `notice page-notice notice-${kind}`;
  notice.hidden = false;
}

function accountLabel(id) {
  return state.adAccounts.find((item) => item.id === id)?.label || "Ad account đã lưu";
}

function filteredRequests() {
  const filter = state.statusFilter;
  if (!filter) return state.requests;
  if (filter === "active") return state.requests.filter((item) => activeStatuses.has(item.status) || item.status === "recovering");
  return state.requests.filter((item) => item.status === filter);
}

function filterCount(filter) {
  if (!filter) return state.requests.length;
  if (filter === "active") return state.requests.filter((item) => activeStatuses.has(item.status) || item.status === "recovering").length;
  return state.requests.filter((item) => item.status === filter).length;
}

function renderFilters() {
  document.querySelectorAll("[data-filter-count]").forEach((node) => {
    const filter = node.dataset.filterCount === "all" ? "" : node.dataset.filterCount;
    node.textContent = filterCount(filter);
  });
  document.querySelectorAll("[data-work-filter]").forEach((button) => {
    const selected = button.dataset.workFilter === state.statusFilter;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function progressIndex(item) {
  if (item.status === "completed") return 3;
  if (["draft_build", "preflight", "recovery", "handoff"].includes(item.stage) || item.status === "awaiting_user") return 2;
  if (item.stage === "approval" || item.status === "awaiting_approval") return 1;
  return 0;
}

function progressSteps(item) {
  const labels = ["Yêu cầu", "Kế hoạch", "Thực thi", "Review"];
  const current = progressIndex(item);
  const isTerminal = ["completed", "failed", "cancelled"].includes(item.status);
  return `<div class="work-progress" aria-label="Tiến trình: ${escapeHtml(stageLabels[item.stage] || item.stage)}">${labels.map((label, index) => {
    const stateName = index < current || item.status === "completed" ? "is-complete" : index === current && !isTerminal ? "is-current" : "";
    return `<span class="work-progress-step ${stateName}"><i aria-hidden="true"></i><b>${label}</b></span>`;
  }).join("<span class=\"work-progress-line\" aria-hidden=\"true\"></span>")}</div>`;
}

function renderSummary() {
  byId("active-count").textContent = state.requests.filter((item) => activeStatuses.has(item.status)).length;
  byId("handoff-count").textContent = state.requests.filter((item) => item.status === "awaiting_user").length;
  byId("recovery-count").textContent = state.requests.filter((item) => item.status === "recovering" || item.recovery_count > 0).length;
  byId("completed-count").textContent = state.requests.filter((item) => item.status === "completed").length;
}

function renderTable() {
  const items = filteredRequests();
  renderFilters();
  byId("work-requests-empty").hidden = items.length > 0;
  byId("work-requests-body").innerHTML = items.map((item) => `
    <tr>
      <td><strong class="work-request-title">${escapeHtml(item.title)}</strong><span class="cell-subtext">${escapeHtml(item.request_text.slice(0, 76))}${item.request_text.length > 76 ? "…" : ""}</span></td>
      <td><span class="source-label">${escapeHtml(item.source === "telegram" ? "Telegram" : "Hermes")}</span></td>
      <td>${escapeHtml(accountLabel(item.ad_account_id))}</td>
      <td><strong class="work-stage-title">${escapeHtml(stageLabels[item.stage] || item.stage)}</strong>${progressSteps(item)}</td>
      <td>${statusBadge(item.status)}</td>
      <td>${escapeHtml(formatDate(item.updated_at))}</td>
      <td class="actions-cell"><button class="row-button" type="button" data-view-work="${escapeHtml(item.id)}" aria-label="Xem tiến độ"><svg aria-hidden="true"><use href="/static/ui-icons.svg#arrow-up-right"></use></svg></button></td>
    </tr>`).join("");
}

function planFacts(plan = {}) {
  const targeting = plan.targeting_json || {};
  const creative = plan.creative_json || {};
  return [
    ["Mục tiêu", plan.objective || "—"],
    ["Ngân sách/ngày", money(plan.daily_budget_minor, plan.currency || "VND")],
    ["Page", targeting.page_snapshot?.label || targeting.page_name || "Chưa phân giải"],
    ["Khu vực", (targeting.countries || []).join(", ") || targeting.note || "Theo yêu cầu"],
    ["Media", creative.asset_snapshot?.file_name || (creative.telegram_media_asset_ids?.length ? `${creative.telegram_media_asset_ids.length} tệp từ Telegram` : "Chưa có")],
  ];
}

function factsHtml(items) {
  return items.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
}

async function openDetail(requestId) {
  try {
    const item = await api(`/api/ad-automation-requests/${requestId}`);
    state.selectedId = requestId;
    byId("work-detail-eyebrow").textContent = `${item.source === "telegram" ? "Telegram" : "Hermes"} · ${formatDate(item.requested_at)}`;
    byId("work-detail-title").textContent = item.title;
    byId("work-detail-progress").textContent = item.progress_message;
    byId("work-detail-status").innerHTML = `${statusBadge(item.status)}<span>${escapeHtml(stageLabels[item.stage] || item.stage)} · ${item.attempt_count} lần chạy · ${item.recovery_count} lần recovery</span>`;
    byId("work-detail-request").textContent = item.request_text;
    const resolution = item.resolution_json || {};
    byId("work-detail-resolution").innerHTML = factsHtml([
      ["Bot VPS", resolution.worker?.name || "—"],
      ["Facebook profile", resolution.facebook_account?.label || "—"],
      ["Ad account", resolution.ad_account?.label || accountLabel(item.ad_account_id)],
      ["Meta ad account ID", resolution.ad_account?.meta_ad_account_id || "—"],
    ]);
    byId("work-detail-plan").innerHTML = factsHtml(planFacts(item.plan_json));
    byId("work-detail-timeline").innerHTML = (item.events || []).map((event) => `
      <li><span class="timeline-marker"></span><div><strong>${escapeHtml(stageLabels[event.stage] || event.stage)}</strong><p>${escapeHtml(event.message)}</p><time>${escapeHtml(formatDate(event.created_at))} · ${escapeHtml(event.actor_type)}</time></div></li>`).join("") || "<li>Chưa có sự kiện.</li>";
    const error = byId("work-detail-error");
    error.hidden = !item.last_error;
    error.textContent = item.last_error || "";
    byId("work-detail-artifacts").innerHTML = (item.artifacts || []).map((artifact) => `<a class="button button-secondary button-small" href="/api/execution-artifacts/${escapeHtml(artifact.id)}" target="_blank" rel="noopener">Xem ${escapeHtml(artifact.kind)}</a>`).join("");
    byId("work-handoff-link").hidden = item.status !== "awaiting_user";
    byId("work-detail-dialog").showModal();
  } catch (error) { showNotice(error.message); }
}

async function loadPage(successMessage = "") {
  try {
    const [requests, accounts] = await Promise.all([api("/api/ad-automation-requests"), api("/api/ad-accounts")]);
    state.requests = requests;
    state.adAccounts = accounts;
    renderSummary();
    renderTable();
    byId("notice").hidden = !successMessage;
    if (successMessage) showNotice(successMessage, "success");
  } catch (error) { showNotice(error.message); }
}

document.addEventListener("click", (event) => {
  const view = event.target.closest("[data-view-work]");
  if (view) openDetail(view.dataset.viewWork);
  const filter = event.target.closest("[data-work-filter]");
  if (filter) {
    state.statusFilter = filter.dataset.workFilter;
    renderTable();
  }
  const close = event.target.closest("[data-close]");
  if (close) byId(close.dataset.close).close();
});

byId("refresh-button").addEventListener("click", () => loadPage("Đã đồng bộ tiến độ mới nhất."));
byId("queue-refresh-button").addEventListener("click", () => loadPage("Đã đồng bộ tiến độ mới nhất."));

loadPage();
setInterval(() => {
  if (state.requests.some((item) => activeStatuses.has(item.status) || item.status === "recovering")) loadPage();
}, 8000);
