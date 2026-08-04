const state = { accounts: [], snapshots: [], schedules: [], jobs: [] };
const byId = (id) => document.getElementById(id);

const statusMeta = {
  queued: ["Đang chờ", "warning"], claimed: ["Worker đã nhận", "warning"], running: ["Đang thu thập", "warning"],
  succeeded: ["Đã thu thập", "success"], failed: ["Thất bại", "danger"], enabled: ["Đang bật", "success"], paused: ["Tạm dừng", ""],
  pending: ["Đang chờ", "warning"], sent: ["Đã gửi", "success"],
  not_configured: ["Thiếu bot token", "warning"], not_requested: ["Chỉ lưu web", ""],
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRF-Token"] = document.body.dataset.csrfToken;
  const response = await fetch(path, { ...options, credentials: "same-origin", headers });
  if (response.status === 401) {
    window.location.assign("/login");
    throw new Error("Phiên đăng nhập đã hết hạn.");
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showNotice(message = "", success = false) {
  const notice = byId("notice");
  notice.hidden = !message;
  notice.textContent = message;
  notice.classList.toggle("notice-success", success);
}

function badge(status) {
  const [label, tone] = statusMeta[status] || [status || "—", ""];
  return `<span class="status ${tone}">${escapeHtml(label)}</span>`;
}

function accountById(id) { return state.accounts.find((account) => account.id === id); }
function selectedAccountId() { return byId("account-filter").value || state.accounts[0]?.id || ""; }
function formatDate(value) { return value ? new Date(value).toLocaleString("vi-VN") : "—"; }
function formatRange(start, end) { return `${new Date(`${start}T00:00:00`).toLocaleDateString("vi-VN")} – ${new Date(`${end}T00:00:00`).toLocaleDateString("vi-VN")}`; }
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

async function loadReports({ quiet = false } = {}) {
  if (!quiet) showNotice();
  try {
    const [accounts, snapshots, schedules, jobs] = await Promise.all([
      api("/api/ad-accounts"), api("/api/report-snapshots?limit=200"), api("/api/report-schedules"), api("/api/report-jobs?limit=200"),
    ]);
    const previous = selectedAccountId();
    state.accounts = accounts;
    state.snapshots = snapshots;
    state.schedules = schedules;
    state.jobs = jobs;
    renderAccountSelectors(previous);
    render();
  } catch (error) {
    showNotice(error.message || "Không thể tải dữ liệu báo cáo.");
  }
}

function renderAccountSelectors(previous) {
  const options = state.accounts.length
    ? state.accounts.map((account) => `<option value="${escapeHtml(account.id)}">${escapeHtml(account.label)} · ${escapeHtml(account.meta_ad_account_id)}</option>`).join("")
    : '<option value="">Chưa có ad account</option>';
  for (const id of ["account-filter", "collect-account", "schedule-account"]) byId(id).innerHTML = options;
  if (previous && state.accounts.some((account) => account.id === previous)) byId("account-filter").value = previous;
  byId("collect-button").disabled = !state.accounts.length;
  byId("add-schedule-button").disabled = !state.accounts.length || !["owner", "admin"].includes(document.body.dataset.role);
}

function render() {
  const accountId = selectedAccountId();
  const account = accountById(accountId);
  const snapshots = state.snapshots.filter((item) => item.ad_account_id === accountId);
  const latest = snapshots[0];
  const totals = latest?.totals_json || {};
  byId("kpi-spend").textContent = formatMetric(totals.amount_spent, account?.currency);
  byId("kpi-results").textContent = formatMetric(totals.results);
  byId("kpi-cost").textContent = formatMetric(totals.cost_per_result, account?.currency);
  byId("kpi-collected").textContent = latest ? formatDate(latest.collected_at) : "Chưa có";

  byId("snapshots-empty").hidden = snapshots.length > 0;
  byId("snapshots-body").innerHTML = snapshots.map((snapshot) => {
    const itemTotals = snapshot.totals_json || {};
    const dataState = snapshot.metadata_json?.data_state || "unknown";
    return `<tr>
      <td>${escapeHtml(formatRange(snapshot.range_start, snapshot.range_end))}</td>
      <td>${escapeHtml(formatMetric(itemTotals.amount_spent, snapshot.currency))}</td>
      <td>${escapeHtml(formatMetric(itemTotals.results))}</td>
      <td>${escapeHtml(formatMetric(itemTotals.cost_per_result, snapshot.currency))}</td>
      <td>${escapeHtml(itemTotals.campaigns ?? snapshot.campaigns_json?.length ?? 0)}</td>
      <td>${escapeHtml(dataState)}</td>
      <td>${escapeHtml(formatDate(snapshot.collected_at))}</td>
    </tr>`;
  }).join("");

  byId("schedules-empty").hidden = state.schedules.length > 0;
  byId("schedules-body").innerHTML = state.schedules.map((schedule) => {
    const scheduleAccount = accountById(schedule.ad_account_id);
    const nextStatus = schedule.status === "enabled" ? "paused" : "enabled";
    const nextLabel = schedule.status === "enabled" ? "Tạm dừng" : "Bật lại";
    return `<tr>
      <td><strong>${escapeHtml(scheduleAccount?.label || "Ad account")}</strong><small class="cell-meta">${escapeHtml(schedule.timezone_name)}</small></td>
      <td>${escapeHtml(schedule.local_time)} hằng ngày</td>
      <td>${escapeHtml(schedule.lookback_days)} ngày</td>
      <td>${escapeHtml(maskChat(schedule.telegram_chat_id))}</td>
      <td>${escapeHtml(formatDate(schedule.next_run_at))}</td>
      <td>${badge(schedule.status)}</td>
      <td><div class="row-actions"><button class="button button-small button-secondary" data-schedule-id="${escapeHtml(schedule.id)}" data-next-status="${nextStatus}">${nextLabel}</button></div></td>
    </tr>`;
  }).join("");

  const jobs = state.jobs.filter((job) => !accountId || job.ad_account_id === accountId);
  byId("jobs-empty").hidden = jobs.length > 0;
  byId("jobs-body").innerHTML = jobs.map((job) => `<tr>
    <td>${escapeHtml(formatDate(job.requested_at))}</td>
    <td>${escapeHtml(accountById(job.ad_account_id)?.label || "Ad account")}</td>
    <td>${job.trigger === "scheduled" ? "Theo lịch" : "Thủ công"}</td>
    <td>${escapeHtml(formatRange(job.range_start, job.range_end))}</td>
    <td>${badge(job.status)}</td>
    <td>${badge(job.delivery_status)}</td>
    <td class="error-cell">${escapeHtml(job.last_error || job.result_json?.delivery?.error || "—")}</td>
  </tr>`).join("");
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
    showNotice("Đã tạo report job read-only. Worker đang chờ nhận job.", true);
    await loadReports({ quiet: true });
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
    showNotice("Đã tạo lịch báo cáo hằng ngày.", true);
    await loadReports({ quiet: true });
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function toggleSchedule(button) {
  button.disabled = true;
  try {
    await api(`/api/report-schedules/${button.dataset.scheduleId}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.nextStatus }) });
    await loadReports({ quiet: true });
  } catch (error) { showNotice(error.message); }
  finally { button.disabled = false; }
}

document.addEventListener("click", (event) => {
  const close = event.target.closest("[data-close]");
  if (close) byId(close.dataset.close).close();
  const scheduleToggle = event.target.closest("[data-schedule-id]");
  if (scheduleToggle) toggleSchedule(scheduleToggle);
});
byId("collect-button").addEventListener("click", openCollectDialog);
byId("add-schedule-button").addEventListener("click", () => { byId("schedule-account").value = selectedAccountId(); byId("schedule-dialog").showModal(); });
byId("account-filter").addEventListener("change", render);
byId("refresh-button").addEventListener("click", () => loadReports());
byId("collect-form").addEventListener("submit", createReportJob);
byId("schedule-form").addEventListener("submit", createSchedule);
setInterval(() => {
  if (state.jobs.some((job) => ["queued", "claimed", "running"].includes(job.status))) loadReports({ quiet: true });
}, 4000);

loadReports();
