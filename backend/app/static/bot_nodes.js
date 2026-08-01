const csrfToken = document.body.dataset.csrfToken;
const rows = document.getElementById("node-rows");
const operationRows = document.getElementById("operation-rows");
const notice = document.getElementById("fleet-notice");
const enrollmentDialog = document.getElementById("enrollment-dialog");
const editDialog = document.getElementById("edit-node-dialog");
const decommissionDialog = document.getElementById("decommission-dialog");
const confirmDialog = document.getElementById("confirm-node-dialog");
let nodesById = new Map();
let pendingConfirm = null;
let operationTimer = null;

const providerPresets = {
  deepseek: { name: "deepseek", base: "https://api.deepseek.com", model: "deepseek-v4-flash" },
  openai: { name: "openai-api", base: "https://api.openai.com/v1" },
  openrouter: { name: "openrouter", base: "https://openrouter.ai/api/v1" },
  cliproxyapi: { name: "cliproxyapi", base: "http://127.0.0.1:8317/v1" },
  custom: { name: "custom", base: "" },
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
      ...(options.method && options.method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join("; ") : payload.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function showNotice(message, success = false) {
  notice.textContent = message;
  notice.classList.toggle("notice-success", success);
  notice.hidden = false;
}

function statusClass(value) {
  if (["revoked", "failed"].includes(value)) return "danger";
  if (["draining", "queued", "running"].includes(value)) return "warning";
  return ["active", "online", "succeeded", "installed"].includes(value) ? "success" : "";
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
}

function actionButtons(node) {
  if (node.lifecycle_status === "revoked") return `<button class="button button-small button-secondary" data-action="edit" data-id="${node.id}">Sửa thiết lập</button><span class="status danger">Đã xóa kết nối</span>`;
  const lifecycle = node.lifecycle_status === "draining"
    ? `<button class="button button-small button-secondary" data-action="activate" data-id="${node.id}">Kích hoạt lại</button><button class="button button-small button-danger" data-action="decommission" data-id="${node.id}">Gỡ khỏi VPS</button>`
    : `<button class="button button-small button-secondary" data-action="drain" data-id="${node.id}">Drain</button>`;
  return `<button class="button button-small button-secondary" data-action="edit" data-id="${node.id}">Sửa thiết lập</button>${lifecycle}<button class="button button-small button-danger" data-action="revoke" data-id="${node.id}">Xóa kết nối</button>`;
}

function renderNodes(nodes) {
  nodesById = new Map(nodes.map((node) => [node.id, node]));
  document.getElementById("node-total").textContent = nodes.length;
  document.getElementById("node-online").textContent = nodes.filter((item) => item.status === "online" && item.lifecycle_status === "active").length;
  document.getElementById("node-draining").textContent = nodes.filter((item) => item.lifecycle_status === "draining").length;
  document.getElementById("node-durable").textContent = nodes.filter((item) => item.capabilities_json?.durable_outbox).length;
  document.getElementById("node-empty").hidden = nodes.length > 0;
  rows.innerHTML = nodes.map((node) => {
    const capabilities = Object.entries(node.capabilities_json || {}).filter(([, enabled]) => enabled === true).map(([name]) => `<span>${escapeHtml(name)}</span>`).join("") || "—";
    const host = node.host ? `${escapeHtml(node.ssh_user || "root")}@${escapeHtml(node.host)}` : "Chưa lưu host";
    return `<tr><td class="node-meta"><strong>${escapeHtml(node.display_name)}</strong><small>${escapeHtml(node.worker_key)}</small></td><td><span class="status ${statusClass(node.lifecycle_status)}">${escapeHtml(node.lifecycle_status)}</span><br><small>${escapeHtml(node.install_status)}</small></td><td><strong>${host}</strong><br><small>${escapeHtml(node.runtime_version || "—")}</small></td><td><div class="capability-list">${capabilities}</div></td><td>${escapeHtml(formatDate(node.last_seen_at))}</td><td><div class="row-actions">${actionButtons(node)}</div></td></tr>`;
  }).join("");
}

function renderOperations(operations) {
  document.getElementById("operation-empty").hidden = operations.length > 0;
  operationRows.innerHTML = operations.map((operation) => `<tr><td>${escapeHtml(operation.operation_type)}</td><td class="mono-text">${escapeHtml(operation.ssh_user)}@${escapeHtml(operation.host)}</td><td><span class="status ${statusClass(operation.status)}">${escapeHtml(operation.status)}</span></td><td>${escapeHtml(operation.message || "—")}</td><td>${escapeHtml(formatDate(operation.created_at))}</td></tr>`).join("");
  if (operations.some((item) => ["queued", "running"].includes(item.status))) {
    clearTimeout(operationTimer);
    operationTimer = setTimeout(loadAll, 3000);
  }
}

async function loadAll() {
  try {
    const [nodes, operations] = await Promise.all([api("/api/bot-nodes"), api("/api/bot-nodes/operations")]);
    renderNodes(nodes);
    renderOperations(operations);
    notice.hidden = true;
  } catch (error) { showNotice(error.message); }
}

function applyInstallPreset() {
  const preset = providerPresets[document.getElementById("install-provider-preset").value];
  document.getElementById("install-provider-name").value = preset.name;
  if (preset.base) document.getElementById("install-provider-base-url").value = preset.base;
  if (preset.model) document.getElementById("install-provider-model").value = preset.model;
}

function toggleReasoning(prefix) {
  const disabled = document.getElementById(`${prefix}-provider-thinking-mode`).value === "disabled";
  document.getElementById(`${prefix}-provider-reasoning-effort`).disabled = disabled;
}

document.getElementById("add-node-button").addEventListener("click", () => {
  document.getElementById("repo-url").value = document.body.dataset.defaultRepoUrl || "";
  document.getElementById("repo-branch").value = document.body.dataset.defaultRepoBranch || "main";
  enrollmentDialog.showModal();
});
document.getElementById("install-provider-preset").addEventListener("change", applyInstallPreset);
document.getElementById("install-provider-thinking-mode").addEventListener("change", () => toggleReasoning("install"));
document.getElementById("edit-provider-thinking-mode").addEventListener("change", () => toggleReasoning("edit"));
document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => enrollmentDialog.close()));
document.querySelectorAll("[data-close-edit]").forEach((button) => button.addEventListener("click", () => editDialog.close()));
document.querySelectorAll("[data-close-decommission]").forEach((button) => button.addEventListener("click", () => decommissionDialog.close()));
document.querySelectorAll("[data-close-confirm]").forEach((button) => button.addEventListener("click", () => confirmDialog.close()));
document.getElementById("refresh-nodes").addEventListener("click", loadAll);

document.getElementById("enrollment-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    const operation = await api("/api/bot-nodes/install", { method: "POST", body: JSON.stringify({
      host: document.getElementById("node-host").value.trim(),
      ssh_user: document.getElementById("node-ssh-user").value.trim(),
      ssh_password: document.getElementById("node-ssh-password").value,
      worker_key: document.getElementById("node-key").value.trim(),
      display_name: document.getElementById("node-name").value.trim(),
      repo_url: document.getElementById("repo-url").value.trim(),
      repo_branch: document.getElementById("repo-branch").value.trim(),
      provider_name: document.getElementById("install-provider-name").value.trim(),
      provider_base_url: document.getElementById("install-provider-base-url").value.trim(),
      provider_model: document.getElementById("install-provider-model").value.trim(),
      provider_thinking_mode: document.getElementById("install-provider-thinking-mode").value,
      provider_reasoning_effort: document.getElementById("install-provider-reasoning-effort").value,
      provider_api_key: document.getElementById("install-provider-api-key").value || null,
    }) });
    document.getElementById("node-ssh-password").value = "";
    document.getElementById("install-provider-api-key").value = "";
    enrollmentDialog.close();
    showNotice(`Đã bắt đầu cài ${operation.ssh_user}@${operation.host}. Theo dõi ở bảng thao tác.`, true);
    await loadAll();
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
});

async function openEdit(node) {
  document.getElementById("edit-node-id").value = node.id;
  document.getElementById("edit-node-name").value = node.display_name;
  document.getElementById("edit-node-key").value = node.worker_key;
  document.getElementById("edit-node-host").value = node.host || "";
  document.getElementById("edit-node-ssh-user").value = node.ssh_user || "root";
  const config = await api(`/api/ai-provider?worker_id=${encodeURIComponent(node.id)}`);
  document.getElementById("edit-provider-name").value = config.provider_name || "custom";
  document.getElementById("edit-provider-base-url").value = config.base_url || "";
  document.getElementById("edit-provider-model").value = config.model || "";
  document.getElementById("edit-provider-thinking-mode").value = config.thinking_mode || "auto";
  document.getElementById("edit-provider-reasoning-effort").value = config.reasoning_effort || "provider_default";
  toggleReasoning("edit");
  document.getElementById("edit-provider-api-key").value = "";
  editDialog.showModal();
}

document.getElementById("edit-node-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const workerId = document.getElementById("edit-node-id").value;
  try {
    const providerName = document.getElementById("edit-provider-name").value.trim();
    const providerBaseUrl = document.getElementById("edit-provider-base-url").value.trim();
    const providerModel = document.getElementById("edit-provider-model").value.trim();
    const providerApiKey = document.getElementById("edit-provider-api-key").value;
    if (providerName || providerBaseUrl || providerModel || providerApiKey) {
      if (!providerName || !providerBaseUrl || !providerModel) throw new Error("Hãy nhập đủ Provider name, Base URL và Model; hoặc để trống toàn bộ nhóm Hermes.");
    }
    await api(`/api/bot-nodes/${workerId}`, { method: "PATCH", body: JSON.stringify({ display_name: document.getElementById("edit-node-name").value.trim(), host: document.getElementById("edit-node-host").value.trim(), ssh_user: document.getElementById("edit-node-ssh-user").value.trim() }) });
    if (providerName || providerBaseUrl || providerModel || providerApiKey) await api("/api/ai-provider", { method: "PUT", body: JSON.stringify({ provider_type: "openai_compatible", provider_name: providerName, base_url: providerBaseUrl, model: providerModel, thinking_mode: document.getElementById("edit-provider-thinking-mode").value, reasoning_effort: document.getElementById("edit-provider-reasoning-effort").value, api_key: providerApiKey || null, execution_scope: "worker", worker_id: workerId }) });
    document.getElementById("edit-provider-api-key").value = "";
    editDialog.close();
    showNotice("Đã lưu thiết lập worker và Hermes.", true);
    await loadAll();
  } catch (error) { showNotice(error.message); editDialog.close(); }
});

document.getElementById("decommission-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const workerId = document.getElementById("decommission-node-id").value;
  try {
    const operation = await api(`/api/bot-nodes/${workerId}/decommission`, { method: "POST", body: JSON.stringify({ ssh_password: document.getElementById("decommission-password").value }) });
    document.getElementById("decommission-password").value = "";
    decommissionDialog.close();
    showNotice(`Đã bắt đầu gỡ service trên ${operation.host}.`, true);
    await loadAll();
  } catch (error) { showNotice(error.message); }
});

function openConfirm(action, node) {
  pendingConfirm = { action, node };
  document.getElementById("confirm-title").textContent = action === "revoke" ? "Xóa kết nối worker" : action === "drain" ? "Drain worker" : "Kích hoạt lại worker";
  document.getElementById("confirm-message").textContent = action === "revoke" ? `Credential của ${node.display_name} sẽ bị vô hiệu hóa; service/profile trên VPS không tự xóa.` : action === "drain" ? `${node.display_name} sẽ không nhận job mới nhưng hoàn tất job đã claim.` : `${node.display_name} sẽ được nhận job mới trở lại.`;
  document.getElementById("confirm-node-action").className = `button ${action === "activate" ? "button-primary" : "button-danger"}`;
  confirmDialog.showModal();
}

document.getElementById("confirm-node-action").addEventListener("click", async () => {
  if (!pendingConfirm) return;
  const { action, node } = pendingConfirm;
  try {
    const method = action === "revoke" ? "DELETE" : "POST";
    const path = action === "revoke" ? `/api/bot-nodes/${node.id}` : `/api/bot-nodes/${node.id}/${action}`;
    await api(path, { method });
    confirmDialog.close();
    await loadAll();
  } catch (error) { showNotice(error.message); confirmDialog.close(); }
});

rows.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const node = nodesById.get(button.dataset.id);
  if (!node) return;
  try {
    if (button.dataset.action === "edit") await openEdit(node);
    else if (button.dataset.action === "decommission") {
      document.getElementById("decommission-node-id").value = node.id;
      document.getElementById("decommission-target").textContent = `${node.ssh_user || "root"}@${node.host || "chưa có host"}`;
      decommissionDialog.showModal();
    } else openConfirm(button.dataset.action, node);
  } catch (error) { showNotice(error.message); }
});

toggleReasoning("install");
loadAll();
