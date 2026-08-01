const csrfToken = document.body.dataset.csrfToken;
const workerSelect = document.getElementById("copilot-worker");
const conversationList = document.getElementById("conversation-list");
const conversationEmpty = document.getElementById("conversation-empty");
const messageList = document.getElementById("message-list");
const composer = document.getElementById("composer-form");
const composerInput = document.getElementById("composer-input");
const sendButton = document.getElementById("send-message");
const notice = document.getElementById("copilot-notice");

let conversations = [];
let currentConversation = null;
let activeJobId = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '\"': "&quot;" }[char]));
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
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).join("; ")
      : payload.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function showNotice(message, success = false) {
  notice.textContent = message;
  notice.classList.toggle("notice-success", success);
  notice.hidden = false;
}

function hideNotice() {
  notice.hidden = true;
}

function formatWhen(value) {
  if (!value) return "Vừa cập nhật";
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function sourceLabel(source) {
  return String(source || "hermes").toLowerCase().includes("telegram") ? "Telegram" : "Web";
}

function renderConversations() {
  conversationEmpty.hidden = conversations.length > 0;
  conversationList.innerHTML = conversations.map((conversation) => {
    const telegram = sourceLabel(conversation.source) === "Telegram";
    return `<button class="conversation-item ${currentConversation?.id === conversation.id ? "is-active" : ""}" type="button" data-conversation-id="${escapeHtml(conversation.id)}"><span class="conversation-icon ${telegram ? "telegram" : ""}">${telegram ? "TG" : conversation.profile.toUpperCase()}</span><span class="conversation-copy"><strong>${escapeHtml(conversation.title)}</strong><small>${escapeHtml(sourceLabel(conversation.source))} · ${escapeHtml(formatWhen(conversation.updated_at))}</small></span></button>`;
  }).join("");
}

function setChatHeader(conversation) {
  const badge = document.getElementById("chat-source");
  document.getElementById("chat-title").textContent = conversation?.title || "Chọn một cuộc trò chuyện";
  badge.textContent = conversation ? `${sourceLabel(conversation.source)} · Ads` : "Hermes";
  badge.classList.toggle("telegram", sourceLabel(conversation?.source) === "Telegram");
  composerInput.disabled = !conversation;
  sendButton.disabled = !conversation || Boolean(activeJobId);
}

function messageElement(message) {
  const article = document.createElement("article");
  const role = message.role === "user" ? "user" : "assistant";
  article.className = `message ${role}`;

  const avatar = document.createElement("span");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "Bạn" : "A";

  const body = document.createElement("div");
  body.className = "message-body";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = `${role === "user" ? "Bạn" : "Hermes"} · ${formatWhen(message.created_at)}`;
  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = message.content;
  body.append(meta, content);

  const shortcuts = Array.isArray(message.metadata_json?.shortcuts)
    ? message.metadata_json.shortcuts.slice(0, 2)
    : [];
  if (shortcuts.length) {
    const wrap = document.createElement("div");
    wrap.className = "message-shortcuts";
    shortcuts.forEach((shortcut) => {
      const label = typeof shortcut === "string" ? shortcut : shortcut.label;
      const prompt = typeof shortcut === "string" ? shortcut : (shortcut.prompt || shortcut.label);
      if (!label || !prompt) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "shortcut-chip";
      button.textContent = label;
      button.addEventListener("click", () => sendNaturalMessage(prompt));
      wrap.append(button);
    });
    if (wrap.childElementCount) body.append(wrap);
  }
  article.append(avatar, body);
  return article;
}

function renderMessages(messages) {
  messageList.innerHTML = "";
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "welcome-state";
    empty.innerHTML = `<span class="welcome-mark">A</span><h2>Bắt đầu theo cách của bạn</h2><p>Cứ mô tả mục tiêu, dữ liệu cần xem hoặc việc muốn thực hiện. Hermes sẽ hỏi lại nếu còn thiếu thông tin.</p>`;
    messageList.append(empty);
  } else {
    messages.forEach((message) => messageList.append(messageElement(message)));
  }
  messageList.scrollTop = messageList.scrollHeight;
}

async function loadConversations({ keepSelection = true } = {}) {
  if (!workerSelect.value) return;
  const query = new URLSearchParams({ worker_id: workerSelect.value, profile: "ads" });
  conversations = await api(`/api/ai-copilot/conversations?${query}`);
  if (keepSelection && currentConversation) {
    currentConversation = conversations.find((item) => item.id === currentConversation.id) || null;
  }
  renderConversations();
  if (!currentConversation && conversations.length) await openConversation(conversations[0].id);
  if (!conversations.length) {
    currentConversation = null;
    setChatHeader(null);
    renderMessages([]);
  }
}

async function openConversation(conversationId) {
  currentConversation = conversations.find((item) => item.id === conversationId) || null;
  if (!currentConversation) return;
  renderConversations();
  setChatHeader(currentConversation);
  const messages = await api(`/api/ai-copilot/conversations/${encodeURIComponent(conversationId)}/messages`);
  renderMessages(messages);
  composerInput.focus();
}

function setBusy(busy, text = "Hermes đang xử lý…") {
  activeJobId = busy ? activeJobId : null;
  document.getElementById("chat-status").textContent = busy ? "Đang xử lý" : "Sẵn sàng";
  document.getElementById("chat-status").className = `status ${busy ? "warning" : "success"}`;
  sendButton.disabled = busy || !currentConversation;
  const existing = document.getElementById("thinking-row");
  if (busy && !existing) {
    const row = document.createElement("div");
    row.id = "thinking-row";
    row.className = "thinking-row";
    row.textContent = text;
    messageList.append(row);
    messageList.scrollTop = messageList.scrollHeight;
  } else if (!busy && existing) existing.remove();
}

async function waitForJob(jobId, { showBusy = true, maxAttempts = 600 } = {}) {
  if (showBusy) {
    activeJobId = jobId;
    setBusy(true);
  }
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const job = await api(`/api/ai-copilot/jobs/${encodeURIComponent(jobId)}`);
    if (job.status === "succeeded") {
      if (showBusy) {
        activeJobId = null;
        setBusy(false);
      }
      return job;
    }
    if (job.status === "failed") {
      if (showBusy) {
        activeJobId = null;
        setBusy(false);
      }
      throw new Error(job.last_error || "Hermes không hoàn thành agent job.");
    }
  }
  if (showBusy) {
    activeJobId = null;
    setBusy(false);
  }
  throw new Error("Hermes phản hồi quá thời gian chờ.");
}

async function syncSessions({ quiet = false } = {}) {
  if (!workerSelect.value) return;
  const job = await api("/api/ai-copilot/sync", {
    method: "POST",
    body: JSON.stringify({ worker_id: workerSelect.value, profile: "ads" }),
  });
  if (!quiet) showNotice("Đang lấy session trực tiếp từ Hermes trên Bot VPS…", true);
  await waitForJob(job.id, { showBusy: false, maxAttempts: 45 });
  await loadConversations();
  if (!quiet) showNotice("Đã đồng bộ session Web và Telegram.", true);
}

async function createConversation() {
  if (!workerSelect.value) throw new Error("Chưa có Bot VPS đang hoạt động.");
  const conversation = await api("/api/ai-copilot/conversations", {
    method: "POST",
    body: JSON.stringify({
      worker_id: workerSelect.value,
      profile: "ads",
      title: "Ads Copilot mới",
    }),
  });
  await loadConversations({ keepSelection: false });
  await openConversation(conversation.id);
}

async function sendNaturalMessage(content) {
  const normalized = String(content || "").trim();
  if (!normalized || !currentConversation || activeJobId) return;
  composerInput.value = "";
  resizeComposer();
  try {
    const job = await api(`/api/ai-copilot/conversations/${encodeURIComponent(currentConversation.id)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content: normalized }),
    });
    const optimistic = await api(`/api/ai-copilot/conversations/${encodeURIComponent(currentConversation.id)}/messages`);
    renderMessages(optimistic);
    await waitForJob(job.id);
    await loadConversations();
    await openConversation(currentConversation.id);
    hideNotice();
  } catch (error) {
    showNotice(error.message);
  }
}

function resizeComposer() {
  composerInput.style.height = "auto";
  composerInput.style.height = `${Math.min(composerInput.scrollHeight, 150)}px`;
}

async function loadWorkers() {
  const workers = (await api("/api/bot-nodes")).filter((item) => item.lifecycle_status === "active");
  workerSelect.innerHTML = workers.map((worker) => `<option value="${escapeHtml(worker.id)}">${escapeHtml(worker.display_name)}</option>`).join("");
  if (!workers.length) {
    workerSelect.innerHTML = `<option value="">Chưa có Bot VPS</option>`;
    document.getElementById("sync-sessions").disabled = true;
    document.getElementById("new-conversation").disabled = true;
    return;
  }
  await loadConversations();
  syncSessions({ quiet: true }).catch((error) => showNotice(`Chưa đồng bộ được Hermes: ${error.message}`));
}

conversationList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-conversation-id]");
  if (button) openConversation(button.dataset.conversationId).catch((error) => showNotice(error.message));
});
document.getElementById("new-conversation").addEventListener("click", () => createConversation().catch((error) => showNotice(error.message)));
document.getElementById("sync-sessions").addEventListener("click", () => syncSessions().catch((error) => showNotice(error.message)));
workerSelect.addEventListener("change", () => { currentConversation = null; loadConversations().then(() => syncSessions({ quiet: true })).catch((error) => showNotice(error.message)); });
composer.addEventListener("submit", (event) => { event.preventDefault(); sendNaturalMessage(composerInput.value); });
composerInput.addEventListener("input", resizeComposer);
composerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});
document.querySelectorAll(".prompt-examples span").forEach((item) => item.addEventListener("click", () => {
  if (!currentConversation) return;
  composerInput.value = item.textContent;
  resizeComposer();
  composerInput.focus();
}));

loadWorkers().catch((error) => showNotice(error.message));
