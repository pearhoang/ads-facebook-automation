const state = { accounts: [], workers: [], sessions: new Map(), selectedSessionId: null };
const byId = (id) => document.getElementById(id);

const statusMeta = {
  not_authenticated: ["Chưa đăng nhập", "warning"], authenticated: ["Đã đăng nhập", "success"], error: ["Có lỗi", "danger"],
  requested: ["Đã yêu cầu", "warning"], starting: ["Đang khởi động", "warning"], awaiting_user: ["Chờ người dùng", "warning"],
  ready: ["Sẵn sàng", "success"], closing: ["Đang đóng", "warning"], closed: ["Đã đóng", ""], failed: ["Thất bại", "danger"], expired: ["Hết hạn", "danger"],
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
  if (response.status === 204) return null;
  return response.json();
}

function showNotice(message = "") {
  const notice = byId("notice");
  notice.hidden = !message;
  notice.textContent = message;
}

function badge(status) {
  const [label, tone] = statusMeta[status] || [status || "—", ""];
  return `<span class="status ${tone}">${escapeHtml(label)}</span>`;
}

async function loadWorkspace() {
  showNotice();
  try {
    const [accounts, workers] = await Promise.all([api("/api/accounts"), api("/api/workers")]);
    state.accounts = accounts;
    state.workers = workers;
    const sessionPairs = await Promise.all(accounts.map(async (account) => [account.id, await api(`/api/accounts/${account.id}/browser-sessions/latest`)]));
    state.sessions = new Map(sessionPairs);
    render();
  } catch (error) {
    showNotice(error.message || "Không thể tải workspace.");
  }
}

function render() {
  const workerById = new Map(state.workers.map((worker) => [worker.id, worker]));
  byId("account-count").textContent = state.accounts.length;
  byId("worker-count").textContent = state.workers.filter((worker) => worker.status === "online").length;
  byId("verification-count").textContent = [...state.sessions.values()].filter((session) => session?.status === "awaiting_user").length;
  byId("failure-count").textContent = [...state.sessions.values()].filter((session) => session?.status === "failed").length;
  byId("empty-state").hidden = state.accounts.length > 0;

  byId("worker-select").innerHTML = state.workers.length
    ? state.workers.map((worker) => `<option value="${escapeHtml(worker.id)}">${escapeHtml(worker.display_name)}</option>`).join("")
    : '<option value="">Chưa có worker online</option>';

  byId("accounts-body").innerHTML = state.accounts.map((account) => {
    const worker = workerById.get(account.assigned_worker_id);
    const session = state.sessions.get(account.id);
    const active = session && ["requested", "starting", "awaiting_user", "ready", "closing"].includes(session.status);
    const primaryAction = active
      ? `<button class="button button-small button-secondary" data-session-id="${session.id}">Xem phiên</button>`
      : `<button class="button button-small button-primary" data-start-account="${account.id}">Mở phiên</button>`;
    return `<tr>
      <td class="account-name"><strong>${escapeHtml(account.label)}</strong><small>${escapeHtml(account.profile_key)}</small></td>
      <td>${escapeHtml(worker?.display_name || "Chưa gán")}</td>
      <td>${badge(account.status)}</td>
      <td>${session ? badge(session.status) : '<span class="status">Chưa có phiên</span>'}</td>
      <td><div class="row-actions">${primaryAction}</div></td>
    </tr>`;
  }).join("");
}

function openAccountDialog() {
  if (!state.workers.length) return showNotice("Worker chưa kết nối. Hãy kiểm tra worker service trước khi thêm tài khoản.");
  byId("account-dialog").showModal();
  byId("account-label").focus();
}

async function createAccount(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api("/api/accounts", { method: "POST", body: JSON.stringify({ label: byId("account-label").value.trim(), assigned_worker_id: byId("worker-select").value }) });
    byId("account-dialog").close();
    event.target.reset();
    await loadWorkspace();
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function startSession(accountId) {
  try {
    const session = await api(`/api/accounts/${accountId}/browser-sessions`, { method: "POST" });
    state.sessions.set(accountId, session);
    render();
    openSessionDialog(session.id);
  } catch (error) { showNotice(error.message); }
}

function sessionById(sessionId) {
  return [...state.sessions.values()].find((session) => session?.id === sessionId);
}

function renderSessionDialog(session) {
  const account = state.accounts.find((item) => item.id === session.account_id);
  const [label] = statusMeta[session.status] || [session.status];
  byId("session-title").textContent = account ? `Phiên đăng nhập · ${account.label}` : "Phiên đăng nhập";
  byId("session-description").textContent = session.status === "awaiting_user" ? "Chrome đã sẵn sàng. Mở noVNC để đăng nhập hoặc xử lý 2FA." : "Hệ thống đang đồng bộ trạng thái với worker.";
  byId("session-status").textContent = label;
  byId("session-expiry").textContent = new Date(session.expires_at).toLocaleString("vi-VN");
  byId("session-error").textContent = session.last_error || "Không có";
  byId("open-novnc-button").disabled = !session.novnc_url || !["awaiting_user", "ready"].includes(session.status);
  byId("confirm-session-button").disabled = !["awaiting_user", "ready"].includes(session.status);
  byId("close-session-button").disabled = ["closed", "expired"].includes(session.status);
}

async function refreshSelectedSession() {
  if (!state.selectedSessionId) return;
  try {
    const session = await api(`/api/browser-sessions/${state.selectedSessionId}`);
    state.sessions.set(session.account_id, session);
    renderSessionDialog(session);
    render();
  } catch (error) { showNotice(error.message); }
}

function openSessionDialog(sessionId) {
  state.selectedSessionId = sessionId;
  const session = sessionById(sessionId);
  if (session) renderSessionDialog(session);
  byId("session-dialog").showModal();
}

async function confirmSession() {
  try { await api(`/api/browser-sessions/${state.selectedSessionId}/confirm`, { method: "POST" }); await refreshSelectedSession(); }
  catch (error) { showNotice(error.message); }
}

async function closeSession() {
  try { await api(`/api/browser-sessions/${state.selectedSessionId}`, { method: "DELETE" }); await refreshSelectedSession(); }
  catch (error) { showNotice(error.message); }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#add-account-button, [data-open-account-dialog]")) openAccountDialog();
  if (event.target.closest("[data-close-dialog]")) byId("account-dialog").close();
  if (event.target.closest("[data-close-session-dialog]")) byId("session-dialog").close();
  const start = event.target.closest("[data-start-account]");
  if (start) startSession(start.dataset.startAccount);
  const inspect = event.target.closest("[data-session-id]");
  if (inspect) openSessionDialog(inspect.dataset.sessionId);
});

byId("account-form").addEventListener("submit", createAccount);
byId("refresh-button").addEventListener("click", loadWorkspace);
byId("confirm-session-button").addEventListener("click", confirmSession);
byId("close-session-button").addEventListener("click", closeSession);
byId("open-novnc-button").addEventListener("click", () => {
  const session = sessionById(state.selectedSessionId);
  if (session?.novnc_url) window.open(session.novnc_url, "_blank", "noopener");
});
byId("logout-button").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
    window.location.assign("/login");
  } catch (error) { showNotice(error.message); }
});

setInterval(() => {
  if (byId("session-dialog").open && state.selectedSessionId) refreshSelectedSession();
}, 3000);

loadWorkspace();
