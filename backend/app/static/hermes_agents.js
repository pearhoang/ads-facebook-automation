const csrfToken = document.body.dataset.csrfToken;
const notice = document.getElementById("provider-notice");
let currentConfig = null;
let workersById = new Map();

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '\"': "&quot;" }[char]));
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}), ...(options.method && options.method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}) } });
  if (!response.ok) { const payload = await response.json().catch(() => ({})); throw new Error(Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join("; ") : payload.detail || `HTTP ${response.status}`); }
  return response.json();
}

const presets = {
  deepseek: { name: "deepseek", base: "https://api.deepseek.com", model: "deepseek-v4-flash" },
  openai: { name: "openai-api", base: "https://api.openai.com/v1" },
  openrouter: { name: "openrouter", base: "https://openrouter.ai/api/v1" },
  "9router": { name: "9router", base: "" },
  cliproxyapi: { name: "cliproxyapi", base: "http://127.0.0.1:8317/v1" },
  custom: { name: "custom", base: "" },
};

function showNotice(message, success = false) { window.AppToast.show(notice, message, { kind: success ? "success" : "error" }); }
function setText(id, value) { document.getElementById(id).textContent = value || "—"; }
function renderSummary(config) {
  currentConfig = config;
  const status = document.getElementById("provider-status");
  status.textContent = config.configured ? "Đã cấu hình" : "Chưa cấu hình";
  status.className = `status ${config.configured ? "success" : ""}`;
  setText("summary-provider", config.provider_name);
  setText("summary-model", config.model);
  setText("summary-thinking", config.thinking_mode);
  setText("summary-reasoning", config.reasoning_effort);
  setText("summary-permission", config.agent_permission_mode === "experimental_full" ? "Experimental Full Access" : "Ads Safe");
  setText("summary-endpoint", config.base_url);
  setText("summary-key", config.api_key_masked);
  setText("summary-scope", config.execution_scope === "worker" ? "Bot VPS" : config.execution_scope);
  setText("summary-test", config.last_test_status ? `${config.last_test_status}${config.last_test_error ? ` · ${config.last_test_error}` : ""}` : null);
}

function renderCodexStatus(worker) {
  const codex = worker?.capabilities_json?.codex || { configured: false };
  const connected = codex.configured === true;
  const credentialPresent = codex.credential_present === true;
  const disconnected = codex.disconnected === true;
  const status = document.getElementById("codex-status");
  status.textContent = connected ? "Đã kết nối" : disconnected ? "Đã ngắt kết nối" : credentialPresent ? "Credential cần xử lý" : "Chưa kết nối";
  status.className = connected ? "text-success" : "";
  setText("codex-account", codex.email || codex.account_id);
  setText("codex-plan", codex.plan_type);
  const connectButton = document.getElementById("connect-codex-button");
  connectButton.textContent = connected ? "Đã kết nối" : "Kết nối Codex";
  connectButton.disabled = connected || !worker?.ssh_password_configured;
  document.getElementById("disconnect-codex-button").disabled = !(worker?.ssh_password_configured && (connected || credentialPresent));
  document.getElementById("rotate-dashboard-password-button").disabled = !worker?.ssh_password_configured;
}

async function refreshCodexWorker(workerId, expectedConnected) {
  let worker = workersById.get(workerId);
  for (let attempt = 0; attempt < 24; attempt += 1) {
    const workers = await api("/api/bot-nodes");
    workersById = new Map(workers.map((item) => [item.id, item]));
    worker = workersById.get(workerId);
    if ((worker?.capabilities_json?.codex?.configured === true) === expectedConnected) break;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  renderCodexStatus(worker);
  return worker;
}

async function load() {
  const workers = await api("/api/bot-nodes");
  workersById = new Map(workers.map((item) => [item.id, item]));
  const workerSelect = document.getElementById("provider-worker");
  const activeWorkers = workers.filter((item) => item.lifecycle_status === "active");
  workerSelect.innerHTML = activeWorkers.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.display_name)} · ${escapeHtml(item.worker_key)}</option>`).join("");
  const config = workerSelect.value ? await api(`/api/ai-provider?worker_id=${encodeURIComponent(workerSelect.value)}`) : { configured: false };
  if (config.configured) {
    document.getElementById("provider-name").value = config.provider_name || "custom";
    document.getElementById("provider-base-url").value = config.base_url || "";
    document.getElementById("provider-model").value = config.model || "";
    document.getElementById("provider-thinking-mode").value = config.thinking_mode || "auto";
    document.getElementById("provider-reasoning-effort").value = config.reasoning_effort || "provider_default";
    document.getElementById("provider-permission-mode").value = config.agent_permission_mode || "ads_safe";
    if (config.worker_id) workerSelect.value = config.worker_id;
  }
  renderSummary(config);
  renderCodexStatus(workersById.get(workerSelect.value));
}

async function loadSelectedWorkerConfig() {
  const workerId = document.getElementById("provider-worker").value;
  const config = workerId ? await api(`/api/ai-provider?worker_id=${encodeURIComponent(workerId)}`) : { configured: false };
  if (config.configured) {
    document.getElementById("provider-name").value = config.provider_name || "custom";
    document.getElementById("provider-base-url").value = config.base_url || "";
    document.getElementById("provider-model").value = config.model || "";
    document.getElementById("provider-thinking-mode").value = config.thinking_mode || "auto";
    document.getElementById("provider-reasoning-effort").value = config.reasoning_effort || "provider_default";
    document.getElementById("provider-permission-mode").value = config.agent_permission_mode || "ads_safe";
  } else {
    document.getElementById("provider-permission-mode").value = "ads_safe";
  }
  document.getElementById("provider-api-key").value = "";
  renderSummary(config);
  renderCodexStatus(workersById.get(workerId));
}

function toggleReasoning() {
  const disabled = document.getElementById("provider-thinking-mode").value === "disabled";
  const effort = document.getElementById("provider-reasoning-effort");
  effort.disabled = disabled;
  document.getElementById("reasoning-help").textContent = disabled
    ? "Thinking đang tắt; Hermes sẽ dùng reasoning_effort=none."
    : "DeepSeek V4 mặc định bật thinking ở mức High; Low/Medium được DeepSeek ánh xạ lên High.";
}

function togglePermissionWarning() {
  document.getElementById("permission-warning").hidden =
    document.getElementById("provider-permission-mode").value !== "experimental_full";
}

document.getElementById("provider-preset").addEventListener("change", (event) => {
  const preset = presets[event.target.value];
  document.getElementById("provider-name").value = preset.name;
  if (preset.base) document.getElementById("provider-base-url").value = preset.base;
  if (preset.model) document.getElementById("provider-model").value = preset.model;
});
document.getElementById("provider-thinking-mode").addEventListener("change", toggleReasoning);
document.getElementById("provider-permission-mode").addEventListener("change", togglePermissionWarning);
document.getElementById("provider-worker").addEventListener("change", () => loadSelectedWorkerConfig().then(togglePermissionWarning).catch((error) => showNotice(error.message)));

document.getElementById("provider-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const config = await api("/api/ai-provider", { method: "PUT", body: JSON.stringify({ provider_type: "openai_compatible", provider_name: document.getElementById("provider-name").value.trim(), base_url: document.getElementById("provider-base-url").value.trim(), model: document.getElementById("provider-model").value.trim(), thinking_mode: document.getElementById("provider-thinking-mode").value, reasoning_effort: document.getElementById("provider-reasoning-effort").value, agent_permission_mode: document.getElementById("provider-permission-mode").value, api_key: document.getElementById("provider-api-key").value.trim() || null, execution_scope: "worker", worker_id: document.getElementById("provider-worker").value }) });
    document.getElementById("provider-api-key").value = "";
    renderSummary(config);
    showNotice("Đã lưu. Worker sẽ đồng bộ Hermes trong tối đa một phút.", true);
  } catch (error) { showNotice(error.message); }
});

document.getElementById("test-provider").addEventListener("click", async () => {
  const workerId = document.getElementById("provider-worker").value;
  try { const config = await api(`/api/ai-provider/test?worker_id=${encodeURIComponent(workerId)}`, { method: "POST" }); renderSummary(config); showNotice(config.last_test_status === "passed" ? "Kết nối đạt." : config.last_test_error || "Đã gửi yêu cầu kiểm tra.", config.last_test_status === "passed"); }
  catch (error) { showNotice(error.message); }
});

const dashboardPasswordDialog = document.getElementById("dashboard-password-dialog");
const dashboardPasswordForm = document.getElementById("dashboard-password-form");
const dashboardPasswordNotice = document.getElementById("dashboard-password-notice");
const dashboardPasswordSubmit = document.getElementById("dashboard-password-submit");
const dashboardNewPassword = document.getElementById("dashboard-new-password");
const dashboardNewPasswordConfirmation = document.getElementById("dashboard-new-password-confirmation");

function clearDashboardSecrets() {
  dashboardNewPassword.value = "";
  dashboardNewPasswordConfirmation.value = "";
}

function showDashboardPasswordNotice(message, success = false) {
  dashboardPasswordNotice.textContent = message;
  dashboardPasswordNotice.classList.toggle("notice-success", success);
  dashboardPasswordNotice.hidden = false;
}

async function waitForWorkerOperation(operationId) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const operation = await api(`/api/bot-nodes/operations/${encodeURIComponent(operationId)}`);
    if (operation.status === "succeeded" || operation.status === "failed") return operation;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  throw new Error("Thao tác đang mất nhiều thời gian. Có thể theo dõi tiếp tại trang Bot VPS.");
}

async function waitForCodexOperation(operationId, onProgress) {
  let lastMessage = "";
  for (let attempt = 0; attempt < 900; attempt += 1) {
    const operation = await api(`/api/bot-nodes/operations/${encodeURIComponent(operationId)}`);
    if (operation.message && operation.message !== lastMessage) {
      lastMessage = operation.message;
      onProgress(operation);
    }
    if (operation.status === "succeeded" || operation.status === "failed") return operation;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
  throw new Error("Codex device login đã quá 15 phút. Hãy thử kết nối lại.");
}

document.getElementById("rotate-dashboard-password-button").addEventListener("click", () => {
  const workerId = document.getElementById("provider-worker").value;
  const worker = workersById.get(workerId);
  if (!workerId || !worker) {
    showNotice("Hãy chọn một Bot VPS trước khi đổi mật khẩu Dashboard.");
    return;
  }
  clearDashboardSecrets();
  dashboardPasswordNotice.hidden = true;
  document.getElementById("dashboard-password-target").textContent = `Bot VPS: ${worker.display_name} · ${worker.host || "chưa có host"}`;
  dashboardPasswordDialog.showModal();
  dashboardNewPassword.focus();
});

document.querySelectorAll("[data-close-dashboard-password]").forEach((button) => {
  button.addEventListener("click", () => {
    clearDashboardSecrets();
    dashboardPasswordDialog.close();
  });
});
dashboardPasswordDialog.addEventListener("cancel", clearDashboardSecrets);

dashboardPasswordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const workerId = document.getElementById("provider-worker").value;
  if (dashboardNewPassword.value !== dashboardNewPasswordConfirmation.value) {
    showDashboardPasswordNotice("Xác nhận mật khẩu Dashboard mới không khớp.");
    dashboardNewPasswordConfirmation.focus();
    return;
  }
  const payload = {
    new_password: dashboardNewPassword.value,
    new_password_confirmation: dashboardNewPasswordConfirmation.value,
  };
  dashboardPasswordSubmit.disabled = true;
  try {
    const operation = await api(`/api/bot-nodes/${encodeURIComponent(workerId)}/hermes-dashboard/password`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    clearDashboardSecrets();
    showDashboardPasswordNotice("Đang xoay password hash và khởi động lại riêng Hermes Dashboard…");
    const completed = await waitForWorkerOperation(operation.id);
    if (completed.status !== "succeeded") throw new Error(completed.message || "Không thể đổi mật khẩu Dashboard.");
    showDashboardPasswordNotice(completed.message || "Đã đổi mật khẩu Hermes Dashboard.", true);
  } catch (error) {
    clearDashboardSecrets();
    showDashboardPasswordNotice(error.message);
  } finally {
    dashboardPasswordSubmit.disabled = false;
  }
});

const codexLoginDialog = document.getElementById("codex-login-dialog");
const codexLoginForm = document.getElementById("codex-login-form");
const codexLoginNotice = document.getElementById("codex-login-notice");
const codexLoginSubmit = document.getElementById("codex-login-submit");

function showCodexLoginNotice(message, success = false) {
  codexLoginNotice.replaceChildren();
  const url = message.match(/https:\/\/[^\s]+/)?.[0]?.replace(/[.,);\]]+$/, "");
  const code = message.match(/(?:Mã|Code):\s*([A-Z0-9]{4}-[A-Z0-9]{4,5})/i)?.[1]?.toUpperCase();
  const summary = message
    .split("\n")
    .filter((line) => !/^Mở:\s*/i.test(line) && !/^(?:Mã|Code):\s*/i.test(line))
    .join("\n");
  const text = document.createElement("span");
  text.textContent = summary;
  codexLoginNotice.append(text);
  if (code) {
    const codeBlock = document.createElement("div");
    codeBlock.className = "codex-device-code";
    const codeLabel = document.createElement("span");
    codeLabel.textContent = "Mã xác thực";
    const codeValue = document.createElement("code");
    codeValue.textContent = code;
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "button button-secondary codex-copy-code";
    copyButton.textContent = "Sao chép mã";
    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code);
        copyButton.textContent = "Đã sao chép";
      } catch (_) {
        window.getSelection()?.selectAllChildren(codeValue);
        copyButton.textContent = "Hãy sao chép mã đã chọn";
      }
    });
    codeBlock.append(codeLabel, codeValue, copyButton);
    codexLoginNotice.append(codeBlock);
  }
  if (url) {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Mở trang xác thực Codex";
    codexLoginNotice.append(link);
  }
  codexLoginNotice.classList.toggle("notice-success", success);
  codexLoginNotice.hidden = false;
}

document.getElementById("connect-codex-button").addEventListener("click", () => {
  const workerId = document.getElementById("provider-worker").value;
  const worker = workersById.get(workerId);
  if (!workerId || !worker) {
    showNotice("Hãy chọn một Bot VPS trước khi kết nối Codex.");
    return;
  }
  if (!worker.ssh_password_configured) {
    showNotice("Bot VPS chưa lưu SSH password. Hãy mở Bot VPS → Sửa thiết lập và lưu password một lần.");
    return;
  }
  codexLoginNotice.hidden = true;
  document.getElementById("codex-login-target").textContent = `Bot VPS: ${worker.display_name} · ${worker.host || "chưa có host"}`;
  codexLoginDialog.showModal();
});

document.querySelectorAll("[data-close-codex-login]").forEach((button) => {
  button.addEventListener("click", () => {
    codexLoginDialog.close();
  });
});

codexLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const workerId = document.getElementById("provider-worker").value;
  codexLoginSubmit.disabled = true;
  try {
    const operation = await api(`/api/bot-nodes/${encodeURIComponent(workerId)}/codex/device-login`, {
      method: "POST",
    });
    showCodexLoginNotice("Đang chuẩn bị Codex CLI và tạo mã xác thực…");
    const completed = await waitForCodexOperation(operation.id, (progress) => showCodexLoginNotice(progress.message || "Đang chờ xác thực…"));
    if (completed.status !== "succeeded") throw new Error(completed.message || "Không thể kết nối Codex.");
    showCodexLoginNotice(completed.message || "Đã kết nối Codex.", true);
    await refreshCodexWorker(workerId, true);
  } catch (error) {
    showCodexLoginNotice(error.message);
  } finally {
    codexLoginSubmit.disabled = false;
  }
});

const codexDisconnectDialog = document.getElementById("codex-disconnect-dialog");
const codexDisconnectForm = document.getElementById("codex-disconnect-form");
const codexDisconnectNotice = document.getElementById("codex-disconnect-notice");
const codexDisconnectSubmit = document.getElementById("codex-disconnect-submit");

document.getElementById("disconnect-codex-button").addEventListener("click", () => {
  const workerId = document.getElementById("provider-worker").value;
  const worker = workersById.get(workerId);
  if (!workerId || !worker) {
    showNotice("Hãy chọn một Bot VPS trước khi ngắt kết nối Codex.");
    return;
  }
  if (!worker.ssh_password_configured) {
    showNotice("Bot VPS chưa lưu SSH password. Hãy mở Bot VPS → Sửa thiết lập và lưu password một lần.");
    return;
  }
  codexDisconnectNotice.hidden = true;
  document.getElementById("codex-disconnect-target").textContent = `Bot VPS: ${worker.display_name} · ${worker.host || "chưa có host"}`;
  codexDisconnectDialog.showModal();
});

document.querySelectorAll("[data-close-codex-disconnect]").forEach((button) => {
  button.addEventListener("click", () => {
    codexDisconnectDialog.close();
  });
});

codexDisconnectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const workerId = document.getElementById("provider-worker").value;
  codexDisconnectSubmit.disabled = true;
  try {
    const operation = await api(`/api/bot-nodes/${encodeURIComponent(workerId)}/codex/disconnect`, {
      method: "POST",
    });
    codexDisconnectNotice.textContent = "Đang xóa credential Codex trên Bot VPS…";
    codexDisconnectNotice.hidden = false;
    const completed = await waitForWorkerOperation(operation.id);
    if (completed.status !== "succeeded") throw new Error(completed.message || "Không thể ngắt kết nối Codex.");
    await refreshCodexWorker(workerId, false);
    codexDisconnectDialog.close();
    showNotice(completed.message || "Đã ngắt kết nối Codex.", true);
  } catch (error) {
    codexDisconnectNotice.textContent = error.message;
    codexDisconnectNotice.hidden = false;
  } finally {
    codexDisconnectSubmit.disabled = false;
  }
});

load().then(() => { toggleReasoning(); togglePermissionWarning(); }).catch((error) => showNotice(error.message));
