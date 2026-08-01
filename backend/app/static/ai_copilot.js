const csrfToken = document.body.dataset.csrfToken;
const workerSelect = document.getElementById("copilot-worker");
const conversationList = document.getElementById("conversation-list");
const conversationEmpty = document.getElementById("conversation-empty");
const messageList = document.getElementById("message-list");
const composer = document.getElementById("composer-form");
const composerInput = document.getElementById("composer-input");
const sendButton = document.getElementById("send-message");
const attachButton = document.getElementById("attach-file");
const attachmentInput = document.getElementById("attachment-input");
const attachmentQueue = document.getElementById("attachment-queue");
const commandPalette = document.getElementById("command-palette");
const notice = document.getElementById("copilot-notice");

let conversations = [];
let currentConversation = null;
let activeJobId = null;
let conversationLoadRequest = 0;
let conversationOpenRequest = 0;
let pendingAttachments = [];

const allowedAttachmentExtensions = new Set(["txt", "md", "csv", "json", "yaml", "yml"]);
const maxAttachmentBytes = 128 * 1024;
const maxAttachmentTotalBytes = 256 * 1024;
const webCommands = new Set(["/help", "/new", "/sync", "/status"]);

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

function appendInlineMarkdown(container, value) {
  const text = String(value || "");
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) container.append(document.createTextNode(text.slice(cursor, match.index)));
    const token = match[0];
    const node = document.createElement(token.startsWith("**") ? "strong" : "code");
    node.textContent = token.startsWith("**") ? token.slice(2, -2) : token.slice(1, -1);
    container.append(node);
    cursor = match.index + token.length;
  }
  if (cursor < text.length) container.append(document.createTextNode(text.slice(cursor)));
}

function markdownCells(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function renderMarkdown(container, value) {
  const lines = String(value || "").replace(/\r\n?/g, "\n").split("\n");
  const tableDivider = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }

    if (line.trim().startsWith("```")) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = codeLines.join("\n");
      pre.append(code);
      container.append(pre);
      continue;
    }

    if (index + 1 < lines.length && line.includes("|") && tableDivider.test(lines[index + 1])) {
      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      markdownCells(line).forEach((cell) => {
        const th = document.createElement("th");
        appendInlineMarkdown(th, cell);
        headRow.append(th);
      });
      head.append(headRow);
      table.append(head);
      const body = document.createElement("tbody");
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        const row = document.createElement("tr");
        markdownCells(lines[index]).forEach((cell) => {
          const td = document.createElement("td");
          appendInlineMarkdown(td, cell);
          row.append(td);
        });
        body.append(row);
        index += 1;
      }
      table.append(body);
      container.append(table);
      continue;
    }

    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (ordered || unordered) {
      const list = document.createElement(ordered ? "ol" : "ul");
      const matcher = ordered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
      while (index < lines.length) {
        const itemMatch = lines[index].match(matcher);
        if (!itemMatch) break;
        const item = document.createElement("li");
        appendInlineMarkdown(item, itemMatch[1]);
        list.append(item);
        index += 1;
      }
      container.append(list);
      continue;
    }

    const heading = line.match(/^\s*(#{1,4})\s+(.+)$/);
    if (heading) {
      const title = document.createElement(`h${Math.min(heading[1].length + 2, 6)}`);
      appendInlineMarkdown(title, heading[2]);
      container.append(title);
      index += 1;
      continue;
    }

    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, line);
    container.append(paragraph);
    index += 1;
  }
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
  attachButton.disabled = !conversation || Boolean(activeJobId);
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
  renderMarkdown(content, message.content);
  body.append(meta, content);

  const attachments = Array.isArray(message.metadata_json?.attachments)
    ? message.metadata_json.attachments
    : [];
  if (attachments.length) {
    const files = document.createElement("div");
    files.className = "message-attachments";
    attachments.forEach((attachment) => {
      const item = document.createElement("span");
      item.className = "message-attachment";
      item.textContent = `${attachment.name} · ${formatBytes(attachment.size_bytes)}`;
      files.append(item);
    });
    body.append(files);
  }

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
  const requestId = ++conversationLoadRequest;
  const workerId = workerSelect.value;
  const selectedId = keepSelection ? currentConversation?.id : null;
  const query = new URLSearchParams({ worker_id: workerId, profile: "ads" });
  const loaded = await api(`/api/ai-copilot/conversations?${query}`);
  if (requestId !== conversationLoadRequest || workerId !== workerSelect.value) return;
  conversations = loaded;
  if (selectedId) {
    currentConversation = conversations.find((item) => item.id === selectedId) || null;
  } else if (!keepSelection) {
    currentConversation = null;
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
  const requestId = ++conversationOpenRequest;
  currentConversation = conversations.find((item) => item.id === conversationId) || null;
  if (!currentConversation) return;
  renderConversations();
  setChatHeader(currentConversation);
  const messages = await api(`/api/ai-copilot/conversations/${encodeURIComponent(conversationId)}/messages`);
  if (requestId !== conversationOpenRequest || currentConversation?.id !== conversationId) return;
  renderMessages(messages);
  composerInput.focus({ preventScroll: true });
}

function setBusy(busy, text = "Hermes đang xử lý…") {
  activeJobId = busy ? activeJobId : null;
  document.getElementById("chat-status").textContent = busy ? "Đang xử lý" : "Sẵn sàng";
  document.getElementById("chat-status").className = `status ${busy ? "warning" : "success"}`;
  sendButton.disabled = busy || !currentConversation;
  attachButton.disabled = busy || !currentConversation;
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
  const workerId = workerSelect.value;
  const job = await api("/api/ai-copilot/sync", {
    method: "POST",
    body: JSON.stringify({ worker_id: workerId, profile: "ads" }),
  });
  if (!quiet) showNotice("Đang lấy session trực tiếp từ Hermes trên Bot VPS…", true);
  await waitForJob(job.id, { showBusy: false, maxAttempts: 45 });
  if (workerId !== workerSelect.value) return;
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

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  return `${Math.round(bytes / 1024)} KB`;
}

function renderPendingAttachments() {
  attachmentQueue.hidden = pendingAttachments.length === 0;
  attachmentQueue.innerHTML = pendingAttachments.map((attachment, index) => (
    `<span class="attachment-item"><span>${escapeHtml(attachment.name)} · ${escapeHtml(formatBytes(attachment.size))}</span><button type="button" data-remove-attachment="${index}" aria-label="Bỏ tệp ${escapeHtml(attachment.name)}">×</button></span>`
  )).join("");
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

async function addAttachments(fileList) {
  const files = Array.from(fileList || []);
  for (const file of files) {
    const extension = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    if (!allowedAttachmentExtensions.has(extension)) {
      showNotice(`Không hỗ trợ ${file.name}. Chỉ dùng TXT, MD, CSV, JSON hoặc YAML.`);
      continue;
    }
    if (!file.size || file.size > maxAttachmentBytes) {
      showNotice(`${file.name} phải có dung lượng từ 1 B đến 128 KB.`);
      continue;
    }
    if (pendingAttachments.some((item) => item.name === file.name && item.size === file.size)) continue;
    const nextTotal = pendingAttachments.reduce((sum, item) => sum + item.size, 0) + file.size;
    if (pendingAttachments.length >= 3 || nextTotal > maxAttachmentTotalBytes) {
      showNotice("Chỉ được đính kèm tối đa 3 tệp và tổng dung lượng 256 KB.");
      break;
    }
    pendingAttachments.push({
      name: file.name,
      media_type: file.type || "text/plain",
      size: file.size,
      content_base64: arrayBufferToBase64(await file.arrayBuffer()),
    });
  }
  attachmentInput.value = "";
  renderPendingAttachments();
}

function updateCommandPalette() {
  const value = composerInput.value.trimStart();
  const isCommandSearch = value.startsWith("/") && !value.includes(" ") && !value.includes("\n");
  let visible = 0;
  commandPalette.querySelectorAll("[data-command]").forEach((button) => {
    const matches = isCommandSearch && button.dataset.command.startsWith(value.toLowerCase());
    button.hidden = !matches;
    if (matches) visible += 1;
  });
  commandPalette.hidden = visible === 0;
}

async function handleWebCommand(content) {
  const command = content.split(/\s+/, 1)[0].toLowerCase();
  if (!webCommands.has(command)) {
    showNotice("Web Copilot không có lệnh này. Gõ /help để xem các shortcut đang hỗ trợ.");
    return true;
  }
  if (pendingAttachments.length) {
    showNotice("Hãy bỏ tệp đính kèm trước khi chạy slash shortcut.");
    return true;
  }
  composerInput.value = "";
  resizeComposer();
  updateCommandPalette();
  if (command === "/new") {
    await createConversation();
    showNotice("Đã tạo cuộc trò chuyện Web mới.", true);
  } else if (command === "/sync") {
    await syncSessions();
  } else if (command === "/status") {
    const workerName = workerSelect.options[workerSelect.selectedIndex]?.text || "Chưa có Bot VPS";
    const sessionName = currentConversation?.title || "Chưa chọn session";
    showNotice(`${workerName} · ${sessionName} · ${activeJobId ? "Hermes đang xử lý" : "Sẵn sàng"}`, true);
  } else {
    showNotice("Shortcut Web: /new tạo chat mới · /sync đồng bộ Telegram · /status xem session. Bạn vẫn có thể nhắn tự nhiên như bình thường.", true);
  }
  return true;
}

async function sendNaturalMessage(content) {
  const normalized = String(content || "").trim();
  if ((!normalized && !pendingAttachments.length) || !currentConversation || activeJobId) return;
  if (normalized.startsWith("/")) {
    await handleWebCommand(normalized);
    return;
  }
  const conversationId = currentConversation.id;
  try {
    const job = await api(`/api/ai-copilot/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content: normalized,
        attachments: pendingAttachments.map(({ name, media_type, content_base64 }) => ({ name, media_type, content_base64 })),
      }),
    });
    composerInput.value = "";
    pendingAttachments = [];
    resizeComposer();
    renderPendingAttachments();
    const optimistic = await api(`/api/ai-copilot/conversations/${encodeURIComponent(conversationId)}/messages`);
    if (currentConversation?.id === conversationId) renderMessages(optimistic);
    await waitForJob(job.id);
    await loadConversations();
    if (currentConversation?.id === conversationId) await openConversation(conversationId);
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
composerInput.addEventListener("input", () => { resizeComposer(); updateCommandPalette(); });
composerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});
attachButton.addEventListener("click", () => attachmentInput.click());
attachmentInput.addEventListener("change", () => addAttachments(attachmentInput.files).catch((error) => showNotice(error.message)));
attachmentQueue.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-attachment]");
  if (!button) return;
  pendingAttachments.splice(Number(button.dataset.removeAttachment), 1);
  renderPendingAttachments();
});
commandPalette.addEventListener("click", (event) => {
  const button = event.target.closest("[data-command]");
  if (!button) return;
  composerInput.value = button.dataset.command;
  updateCommandPalette();
  composerInput.focus({ preventScroll: true });
});
document.querySelectorAll(".prompt-examples span").forEach((item) => item.addEventListener("click", () => {
  if (!currentConversation) return;
  composerInput.value = item.textContent;
  resizeComposer();
  composerInput.focus();
}));

loadWorkers().catch((error) => showNotice(error.message));
