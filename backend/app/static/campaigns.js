const csrfToken = document.body.dataset.csrfToken;
const byId = (id) => document.getElementById(id);

const state = { requests: [], adAccounts: [], selectedId: null };
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

function statusClass(status) {
  if (status === "completed") return "success";
  if (status === "failed" || status === "cancelled") return "error";
  if (status === "awaiting_user" || status === "recovering") return "warning";
  return "neutral";
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
  const filter = byId("status-filter").value;
  if (!filter) return state.requests;
  if (filter === "active") return state.requests.filter((item) => activeStatuses.has(item.status) || item.status === "recovering");
  return state.requests.filter((item) => item.status === filter);
}

function renderSummary() {
  byId("active-count").textContent = state.requests.filter((item) => activeStatuses.has(item.status)).length;
  byId("handoff-count").textContent = state.requests.filter((item) => item.status === "awaiting_user").length;
  byId("recovery-count").textContent = state.requests.filter((item) => item.status === "recovering" || item.recovery_count > 0).length;
  byId("completed-count").textContent = state.requests.filter((item) => item.status === "completed").length;
}

function renderTable() {
  const items = filteredRequests();
  byId("work-requests-empty").hidden = items.length > 0;
  byId("work-requests-body").innerHTML = items.map((item) => `
    <tr>
      <td><strong>${escapeHtml(item.title)}</strong><span class="cell-subtext">${escapeHtml(item.request_text.slice(0, 92))}${item.request_text.length > 92 ? "…" : ""}</span></td>
      <td><span class="source-label">${escapeHtml(item.source === "telegram" ? "Telegram" : "Hermes")}</span></td>
      <td>${escapeHtml(accountLabel(item.ad_account_id))}</td>
      <td><strong>${escapeHtml(stageLabels[item.stage] || item.stage)}</strong><span class="cell-subtext">${escapeHtml(item.progress_message)}</span></td>
      <td><span class="status-pill status-${statusClass(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span></td>
      <td>${escapeHtml(formatDate(item.updated_at))}</td>
      <td class="actions-cell"><button class="icon-button" type="button" data-view-work="${escapeHtml(item.id)}" aria-label="Xem tiến độ"><svg aria-hidden="true"><use href="/static/ui-icons.svg#arrow-up-right"></use></svg></button></td>
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
    byId("work-detail-status").innerHTML = `<span class="status-pill status-${statusClass(item.status)}">${escapeHtml(statusLabels[item.status] || item.status)}</span><span>${escapeHtml(stageLabels[item.stage] || item.stage)} · ${item.attempt_count} lần chạy · ${item.recovery_count} lần recovery</span>`;
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
  const close = event.target.closest("[data-close]");
  if (close) byId(close.dataset.close).close();
});

byId("status-filter").addEventListener("change", renderTable);
byId("refresh-button").addEventListener("click", () => loadPage("Đã đồng bộ tiến độ mới nhất."));

loadPage();
setInterval(() => {
  if (state.requests.some((item) => activeStatuses.has(item.status) || item.status === "recovering")) loadPage();
}, 8000);
