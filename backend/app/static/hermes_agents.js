const csrfToken = document.body.dataset.csrfToken;
const notice = document.getElementById("provider-notice");
let currentConfig = null;

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

function showNotice(message, success = false) { notice.textContent = message; notice.classList.toggle("notice-success", success); notice.hidden = false; }
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

async function load() {
  const workers = await api("/api/bot-nodes");
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

load().then(() => { toggleReasoning(); togglePermissionWarning(); }).catch((error) => showNotice(error.message));
