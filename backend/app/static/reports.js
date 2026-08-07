(function reportingModule() {
const state = {
  accounts: [],
  snapshots: [],
  schedules: [],
  jobPage: { items: [], page: 1, page_size: 10, total: 0, total_pages: 1 },
  page: 1,
  pageSize: 10,
};
const byId = (id) => document.getElementById(id);

const statusMeta = {
  queued: ["Đang chờ", "warning"], claimed: ["Worker đã nhận", "warning"], running: ["Đang thu thập", "warning"],
  succeeded: ["Đã thu thập", "success"], failed: ["Thất bại", "danger"], cancelled: ["Đã hủy", "danger"],
  enabled: ["Đang bật", "success"], paused: ["Tạm dừng", ""], pending: ["Đang chờ", "warning"],
  sent: ["Đã gửi", "success"], not_configured: ["Thiếu bot token", "warning"], not_requested: ["Chỉ lưu web", ""],
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRF-Token"] = document.body.dataset.csrfToken;
  const response = await fetch(path, { ...options, credentials: "same-origin", headers });
  if (response.status === 401) { window.location.assign("/login"); throw new Error("Phiên đăng nhập đã hết hạn."); }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showNotice(message = "", success = false) {
  if (message) window.AppToast.show(byId("notice"), message, { kind: success ? "success" : "error" });
}

function badge(status) {
  const [label, tone] = statusMeta[status] || [status || "—", ""];
  return `<span class="status ${tone}">${escapeHtml(label)}</span>`;
}

function accountById(id) { return state.accounts.find((account) => account.id === id); }
function selectedAccountId() { return byId("account-filter")?.value || state.accounts[0]?.id || ""; }
function formatDate(value) { return value ? new Date(value).toLocaleString("vi-VN") : "—"; }
function formatRange(start, end) {
  if (!start || !end) return "—";
  return `${new Date(`${start}T00:00:00`).toLocaleDateString("vi-VN")} – ${new Date(`${end}T00:00:00`).toLocaleDateString("vi-VN")}`;
}
function formatMetric(value, currency = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const formatted = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(Number(value));
  return currency ? `${formatted} ${currency}` : formatted;
}
function maskChat(value) {
  if (!value) return "Chỉ lưu web";
  const text = String(value);
  return text.length <= 6 ? "••••" : `${text.slice(0, 3)}•••${text.slice(-3)}`;
}

function renderAccountSelectors(previous = "") {
  const options = state.accounts.length
    ? state.accounts.map((account) => `<option value="${escapeHtml(account.id)}">${escapeHtml(account.label)} · ${escapeHtml(account.meta_ad_account_id)}</option>`).join("")
    : '<option value="">Chưa có ad account</option>';
  for (const id of ["account-filter", "collect-account", "schedule-account"]) byId(id).innerHTML = options;
  if (previous && state.accounts.some((account) => account.id === previous)) byId("account-filter").value = previous;
  byId("collect-button").disabled = !state.accounts.length;
  byId("add-schedule-button").disabled = !state.accounts.length || !["owner", "admin"].includes(document.body.dataset.role);
}

function renderLatestSnapshot() {
  const account = accountById(selectedAccountId());
  const latest = state.snapshots[0];
  const totals = latest?.totals_json || {};
  byId("kpi-spend").textContent = formatMetric(totals.amount_spent, account?.currency);
  byId("kpi-results").textContent = formatMetric(totals.results);
  byId("kpi-cost").textContent = formatMetric(totals.cost_per_result, account?.currency);
  byId("kpi-collected").textContent = latest ? formatDate(latest.collected_at) : "Chưa có";
  const campaignCount = latest ? (totals.campaigns ?? latest.campaigns_json?.length ?? 0) : 0;
  byId("kpi-context").textContent = latest
    ? `${account?.label || "Ad account"} · ${formatRange(latest.range_start, latest.range_end)} · ${campaignCount} campaign · ${latest.metadata_json?.data_state || "unknown"}`
    : `${account?.label || "Ad account"} chưa có snapshot KPI.`;
}

function renderSchedules() {
  byId("schedules-empty").hidden = state.schedules.length > 0;
  byId("schedules-body").innerHTML = state.schedules.map((schedule) => {
    const account = accountById(schedule.ad_account_id);
    const nextStatus = schedule.status === "enabled" ? "paused" : "enabled";
    const nextLabel = schedule.status === "enabled" ? "Tạm dừng" : "Bật lại";
    return `<tr>
      <td><strong>${escapeHtml(account?.label || "Ad account")}</strong><small class="cell-meta">${escapeHtml(schedule.timezone_name)}</small></td>
      <td>${escapeHtml(schedule.local_time)} hằng ngày</td><td>${escapeHtml(schedule.lookback_days)} ngày</td>
      <td>${escapeHtml(maskChat(schedule.telegram_chat_id))}</td><td>${escapeHtml(formatDate(schedule.next_run_at))}</td>
      <td>${badge(schedule.status)}</td><td><button class="button button-small button-secondary" data-schedule-id="${escapeHtml(schedule.id)}" data-next-status="${nextStatus}">${nextLabel}</button></td>
    </tr>`;
  }).join("");
}

function renderHistory() {
  const page = state.jobPage;
  byId("jobs-empty").hidden = page.items.length > 0;
  byId("jobs-body").innerHTML = page.items.map((job) => {
    const attention = job.last_error || job.result_json?.delivery?.error || (job.status === "failed" ? "Hermes cần kiểm tra lần chạy này" : "—");
    return `<tr>
      <td>${escapeHtml(formatDate(job.requested_at))}</td>
      <td>${job.trigger === "scheduled" ? "Theo lịch" : "Thủ công"}</td>
      <td>${escapeHtml(formatRange(job.range_start, job.range_end))}</td>
      <td>${badge(job.status)}</td><td>${badge(job.delivery_status)}</td>
      <td class="error-cell">${escapeHtml(attention)}</td>
    </tr>`;
  }).join("");
  byId("history-page-summary").textContent = `${page.total} lần thu thập`;
  byId("history-page-info").textContent = `${page.page} / ${page.total_pages}`;
  byId("history-prev").disabled = page.page <= 1;
  byId("history-next").disabled = page.page >= page.total_pages;
  byId("delete-history-page").disabled = !page.items.length || !["owner", "admin"].includes(document.body.dataset.role);
}

async function loadReportData({ reloadBase = false, successMessage = "" } = {}) {
  try {
    const previous = selectedAccountId();
    if (reloadBase || !state.accounts.length) {
      [state.accounts, state.schedules] = await Promise.all([api("/api/ad-accounts"), api("/api/report-schedules")]);
      renderAccountSelectors(previous);
    }
    const accountId = selectedAccountId();
    if (!accountId) {
      state.snapshots = [];
      state.jobPage = { items: [], page: 1, page_size: state.pageSize, total: 0, total_pages: 1 };
    } else {
      const params = new URLSearchParams({ ad_account_id: accountId, page: String(state.page), page_size: String(state.pageSize) });
      [state.snapshots, state.jobPage] = await Promise.all([
        api(`/api/report-snapshots?ad_account_id=${encodeURIComponent(accountId)}&limit=1`),
        api(`/api/report-jobs/page?${params}`),
      ]);
      state.page = state.jobPage.page;
    }
    renderLatestSnapshot();
    renderSchedules();
    renderHistory();
    if (successMessage) showNotice(successMessage, true);
  } catch (error) { showNotice(error.message || "Không thể tải dữ liệu vận hành."); }
}

function openCollectDialog() {
  byId("collect-account").value = selectedAccountId();
  byId("collect-confirmation").value = "";
  byId("collect-dialog").showModal();
  byId("collect-confirmation").focus();
}

async function createReportJob(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api("/api/report-jobs", { method: "POST", body: JSON.stringify({
      ad_account_id: byId("collect-account").value,
      lookback_days: Number(byId("collect-lookback").value),
      telegram_chat_id: byId("collect-chat-id").value.trim() || null,
      confirmation: byId("collect-confirmation").value.trim(),
    }) });
    byId("collect-dialog").close();
    state.page = 1;
    await loadReportData({ reloadBase: true, successMessage: "Đã giao worker thu thập KPI read-only." });
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function createSchedule(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api("/api/report-schedules", { method: "POST", body: JSON.stringify({
      ad_account_id: byId("schedule-account").value,
      local_time: byId("schedule-time").value,
      lookback_days: Number(byId("schedule-lookback").value),
      telegram_chat_id: byId("schedule-chat-id").value.trim() || null,
    }) });
    byId("schedule-dialog").close();
    await loadReportData({ reloadBase: true, successMessage: "Đã tạo lịch báo cáo hằng ngày." });
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function toggleSchedule(button) {
  button.disabled = true;
  try {
    await api(`/api/report-schedules/${button.dataset.scheduleId}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.nextStatus }) });
    await loadReportData({ reloadBase: true, successMessage: "Đã cập nhật lịch báo cáo." });
  } catch (error) { showNotice(error.message); }
  finally { button.disabled = false; }
}

async function deleteHistoryPage() {
  const page = state.jobPage;
  if (!page.items.length) return;
  if (!window.confirm(`Xóa các job đã kết thúc trên trang ${page.page}? Job đang chạy và snapshot mới nhất sẽ được giữ lại.`)) return;
  const params = new URLSearchParams({ ad_account_id: selectedAccountId(), page: String(page.page), page_size: String(state.pageSize) });
  try {
    const result = await api(`/api/report-jobs/page?${params}`, { method: "DELETE" });
    if (state.page > 1 && result.remaining <= (state.page - 1) * state.pageSize) state.page -= 1;
    const notes = [`Đã xóa ${result.deleted} mục`];
    if (result.retained_latest) notes.push(`giữ ${result.retained_latest} snapshot mới nhất`);
    if (result.skipped_active) notes.push(`bỏ qua ${result.skipped_active} job đang chạy`);
    await loadReportData({ successMessage: `${notes.join(", ")}.` });
  } catch (error) { showNotice(error.message); }
}

document.addEventListener("click", (event) => {
  const close = event.target.closest("[data-close]");
  if (close) byId(close.dataset.close).close();
  const scheduleToggle = event.target.closest("[data-schedule-id]");
  if (scheduleToggle) toggleSchedule(scheduleToggle);
});
byId("collect-button").addEventListener("click", openCollectDialog);
byId("add-schedule-button").addEventListener("click", () => { byId("schedule-account").value = selectedAccountId(); byId("schedule-dialog").showModal(); });
byId("account-filter").addEventListener("change", () => { state.page = 1; loadReportData(); });
byId("report-refresh-button").addEventListener("click", () => loadReportData({ reloadBase: true, successMessage: "Đã làm mới KPI và lịch báo cáo." }));
byId("report-page-refresh-button")?.addEventListener("click", () => loadReportData({ reloadBase: true, successMessage: "Đã làm mới KPI và lịch báo cáo." }));
byId("collect-form").addEventListener("submit", createReportJob);
byId("schedule-form").addEventListener("submit", createSchedule);
byId("history-prev").addEventListener("click", () => { if (state.page > 1) { state.page -= 1; loadReportData(); } });
byId("history-next").addEventListener("click", () => { if (state.page < state.jobPage.total_pages) { state.page += 1; loadReportData(); } });
byId("delete-history-page").addEventListener("click", deleteHistoryPage);

setInterval(() => {
  if (state.jobPage.items.some((job) => ["queued", "claimed", "running"].includes(job.status))) loadReportData();
}, 5000);

loadReportData({ reloadBase: true });
})();
