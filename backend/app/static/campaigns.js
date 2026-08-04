const state = {
  facebookAccounts: [],
  adAccounts: [],
  metaResources: [],
  creativeAssets: [],
  campaigns: [],
  approvals: [],
  auditEvents: [],
  executionJobs: [],
  objectiveSpecs: [],
  selectedApprovalId: null,
  selectedCampaignId: null,
  selectedJobId: null,
  selectedResourceId: null,
  editingAdAccountId: null,
  executionMode: "preflight",
};
const byId = (id) => document.getElementById(id);
const zeroDecimalCurrencies = new Set(["VND", "JPY", "KRW"]);
const resourceKindLabels = {
  page: "Facebook Page",
  instagram_account: "Instagram account",
  dataset: "Pixel/Dataset",
  instant_form: "Instant Form",
  app: "Ứng dụng",
};

const statusMeta = {
  active: ["Hoạt động", "success"],
  unverified: ["Chưa xác minh", "warning"],
  verified: ["Đã xác minh", "success"],
  ready: ["Sẵn sàng", "success"],
  draft: ["Draft", ""],
  pending_approval: ["Chờ duyệt", "warning"],
  approved: ["Đã duyệt nội bộ", "success"],
  rejected: ["Đã từ chối", "danger"],
  queued: ["Trong hàng chờ", "warning"],
  claimed: ["Worker đã nhận", "warning"],
  running: ["Đang thực thi", "warning"],
  succeeded: ["Đã hoàn thành", "success"],
  awaiting_user: ["Cần người dùng", "warning"],
  failed: ["Execution lỗi", "danger"],
};
const actionLabels = {
  "ad_account.created": "Đã thêm ad account",
  "ad_account.updated": "Đã cập nhật ad account",
  "meta_resource.created": "Đã thêm Meta resource",
  "meta_resource.verified": "Đã xác minh Meta resource",
  "creative_asset.created": "Đã tải creative asset",
  "campaign_draft.created": "Đã tạo campaign draft",
  "campaign_draft.updated": "Đã sửa campaign draft",
  "campaign_draft.submitted": "Đã gửi duyệt",
  "campaign_draft.approved": "Đã duyệt nội bộ",
  "campaign_draft.rejected": "Đã từ chối",
  "execution_job.queued": "Đã tạo execution job",
  "execution_job.retried": "Đã retry execution job",
  "execution_job.succeeded": "Execution hoàn thành",
  "execution_job.awaiting_user": "Execution cần người dùng",
  "execution_job.failed": "Execution lỗi",
};
const fieldStatusMeta = {
  applied: ["Đã áp dụng", "success"],
  already_set: ["Đã đúng", "success"],
  verified: ["Đã xác minh", "success"],
  skipped: ["Bỏ qua", ""],
  not_available: ["Chưa có control", "warning"],
  blocked: ["Thiếu dữ liệu", "danger"],
  failed: ["Không áp dụng được", "danger"],
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
    try {
      const body = await response.json();
      detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(" · ") : body.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function apiRaw(path, body, contentType) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": contentType,
      "X-CSRF-Token": document.body.dataset.csrfToken,
    },
    body,
  });
  if (response.status === 401) {
    window.location.assign("/login");
    throw new Error("Phiên đăng nhập đã hết hạn.");
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

function showNotice(message = "", tone = "error") {
  const notice = byId("notice");
  notice.hidden = !message;
  notice.textContent = message;
  notice.classList.toggle("notice-success", tone === "success");
  if (message) notice.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function badge(status) {
  const [label, tone] = statusMeta[status] || [status || "—", ""];
  return `<span class="status ${tone}">${escapeHtml(label)}</span>`;
}

function fieldBadge(status) {
  const [label, tone] = fieldStatusMeta[status] || [status || "—", ""];
  return `<span class="status ${tone}">${escapeHtml(label)}</span>`;
}

function money(minor, currency) {
  const divisor = zeroDecimalCurrencies.has(currency) ? 1 : 100;
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency, maximumFractionDigits: divisor === 1 ? 0 : 2 }).format(minor / divisor);
}

function dateTime(value) {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}

function fileSize(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function detailSummary(event) {
  const payload = event.payload_json || {};
  if (payload.label) return payload.label;
  if (payload.name) return payload.name;
  if (payload.note) return payload.note;
  if (payload.version) return `Version ${payload.version}`;
  return "—";
}

async function loadPage(successMessage = "") {
  showNotice();
  try {
    const [facebookAccounts, adAccounts, metaResources, creativeAssets, campaigns, approvals, auditEvents, executionJobs, objectiveSpecs] = await Promise.all([
      api("/api/accounts"),
      api("/api/ad-accounts"),
      api("/api/meta-resources"),
      api("/api/creative-assets"),
      api("/api/campaign-drafts"),
      api("/api/approval-requests?status=pending"),
      api("/api/audit-events?limit=30"),
      api("/api/execution-jobs?limit=100"),
      api("/api/objective-specs"),
    ]);
    Object.assign(state, { facebookAccounts, adAccounts, metaResources, creativeAssets, campaigns, approvals, auditEvents, executionJobs, objectiveSpecs });
    render();
    if (successMessage) showNotice(successMessage, "success");
  } catch (error) {
    showNotice(error.message || "Không thể tải dữ liệu campaign.");
  }
}

function render() {
  const facebookById = new Map(state.facebookAccounts.map((item) => [item.id, item]));
  const adAccountById = new Map(state.adAccounts.map((item) => [item.id, item]));
  const campaignById = new Map(state.campaigns.map((item) => [item.id, item]));
  byId("ad-account-count").textContent = state.adAccounts.length;
  byId("draft-count").textContent = state.campaigns.filter((item) => item.status === "draft").length;
  byId("pending-count").textContent = state.approvals.length;
  byId("approved-count").textContent = state.campaigns.filter((item) => item.status === "approved").length;

  byId("ad-accounts-empty").hidden = state.adAccounts.length > 0;
  byId("meta-resources-empty").hidden = state.metaResources.length > 0;
  byId("creative-assets-empty").hidden = state.creativeAssets.length > 0;
  byId("campaigns-empty").hidden = state.campaigns.length > 0;
  byId("approvals-empty").hidden = state.approvals.length > 0;
  byId("execution-jobs-empty").hidden = state.executionJobs.length > 0;
  byId("ad-accounts-body").innerHTML = state.adAccounts.map((account) => {
    const facebookAccount = facebookById.get(account.facebook_account_id);
    const accountLabel = escapeHtml(account.label);
    const accountId = escapeHtml(account.id);
    return `<tr><td class="account-name"><strong>${accountLabel}</strong><small>${escapeHtml(account.meta_ad_account_id)}</small></td><td>${escapeHtml(facebookAccount?.label || "Không xác định")}</td><td>${escapeHtml(account.currency)}</td><td>${escapeHtml(account.timezone_name)}</td><td>${badge(account.status)}</td><td><div class="row-actions"><button class="row-button" type="button" data-edit-ad-account="${accountId}" aria-label="Sửa ad account ${accountLabel}" title="Sửa ad account"><svg aria-hidden="true"><use href="/static/ui-icons.svg?v=meta-light-focus-4#pencil"></use></svg></button><button class="row-button" type="button" data-create-campaign-for-ad-account="${accountId}" aria-label="Tạo campaign với ad account ${accountLabel}" title="Tạo campaign"><svg aria-hidden="true"><use href="/static/ui-icons.svg?v=meta-light-focus-4#arrow-up-right"></use></svg></button></div></td></tr>`;
  }).join("");

  byId("meta-resources-body").innerHTML = state.metaResources.map((resource) => {
    const account = adAccountById.get(resource.ad_account_id);
    const action = resource.status === "verified"
      ? ""
      : `<button class="button button-small button-secondary" data-verify-resource="${escapeHtml(resource.id)}">Xác minh</button>`;
    return `<tr><td class="account-name"><strong>${escapeHtml(resource.label)}</strong><small>${escapeHtml(resource.id)}</small></td><td>${escapeHtml(resourceKindLabels[resource.kind] || resource.kind)}</td><td>${escapeHtml(account?.label || "Không xác định")}</td><td><span class="mono-text">${escapeHtml(resource.external_id || "—")}</span></td><td>${badge(resource.status)}</td><td><div class="row-actions">${action}</div></td></tr>`;
  }).join("");

  byId("creative-assets-body").innerHTML = state.creativeAssets.map((asset) => {
    const account = adAccountById.get(asset.ad_account_id);
    return `<tr><td class="account-name"><strong>${escapeHtml(asset.label)}</strong><small>${escapeHtml(asset.file_name)}</small></td><td>${escapeHtml(account?.label || "Không xác định")}</td><td>${escapeHtml(asset.content_type)}</td><td>${escapeHtml(fileSize(asset.byte_size))}</td><td><span class="mono-text digest-text" title="${escapeHtml(asset.sha256)}">${escapeHtml(asset.sha256.slice(0, 12))}…</span></td><td>${badge(asset.status)}</td></tr>`;
  }).join("");

  byId("campaigns-body").innerHTML = state.campaigns.map((campaign) => {
    const account = adAccountById.get(campaign.ad_account_id);
    let action = "";
    if (campaign.status === "draft") action = `<button class="button button-small button-primary" data-submit-campaign="${campaign.id}">Gửi duyệt</button>`;
    if (campaign.status === "approved") action = `<button class="button button-small button-secondary" data-preflight-campaign="${campaign.id}">Chạy preflight</button><button class="button button-small button-primary" data-build-draft-campaign="${campaign.id}">Tạo Meta draft</button>`;
    return `<tr><td class="account-name"><strong>${escapeHtml(campaign.name)}</strong><small>v${campaign.version}</small></td><td>${escapeHtml(account?.label || "Không xác định")}</td><td>${escapeHtml(campaign.objective)}</td><td>${escapeHtml(money(campaign.daily_budget_minor, campaign.currency))}</td><td>${badge(campaign.status)}</td><td><div class="row-actions">${action}</div></td></tr>`;
  }).join("");

  byId("approvals-body").innerHTML = state.approvals.map((approval) => {
    const campaign = campaignById.get(approval.campaign_draft_id);
    const snapshot = approval.snapshot_json;
    return `<tr><td>${escapeHtml(campaign?.name || snapshot.name)}</td><td>v${escapeHtml(snapshot.version)}</td><td>${escapeHtml(money(snapshot.daily_budget_minor, snapshot.currency))}</td><td>${escapeHtml(dateTime(approval.requested_at))}</td><td><div class="row-actions"><button class="button button-small button-secondary" data-review-approval="${approval.id}">Kiểm tra</button></div></td></tr>`;
  }).join("");

  byId("execution-jobs-body").innerHTML = state.executionJobs.map((job) => {
    const campaign = campaignById.get(job.campaign_draft_id);
    const readiness = job.result_json?.readiness || "Chưa có kết quả";
    const jobLabel = job.job_type === "draft_build" ? "Meta draft builder" : "Preflight read-only";
    return `<tr><td>${escapeHtml(campaign?.name || job.payload_json?.campaign_snapshot?.name || "Không xác định")}</td><td>${escapeHtml(jobLabel)}</td><td>${badge(job.status)}</td><td>${escapeHtml(readiness)}</td><td>${escapeHtml(job.attempt_count)}</td><td>${escapeHtml(dateTime(job.requested_at))}</td><td><div class="row-actions"><button class="button button-small button-secondary" data-view-job="${job.id}">Xem chi tiết</button></div></td></tr>`;
  }).join("");

  byId("audit-body").innerHTML = state.auditEvents.map((event) => `<tr><td>${escapeHtml(dateTime(event.created_at))}</td><td>${escapeHtml(actionLabels[event.action] || event.action)}</td><td><span class="mono-text">${escapeHtml(event.entity_type)}</span></td><td>${escapeHtml(detailSummary(event))}</td></tr>`).join("");

  byId("facebook-account-select").innerHTML = state.facebookAccounts.length
    ? state.facebookAccounts.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("")
    : '<option value="">Chưa có tài khoản Facebook</option>';
  byId("campaign-ad-account").innerHTML = state.adAccounts.length
    ? state.adAccounts.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${escapeHtml(item.currency)}</option>`).join("")
    : '<option value="">Chưa có ad account</option>';
  byId("resource-ad-account").innerHTML = byId("campaign-ad-account").innerHTML;
  byId("asset-ad-account").innerHTML = byId("campaign-ad-account").innerHTML;
  const selectedObjective = byId("campaign-objective").value || "sales";
  byId("campaign-objective").innerHTML = state.objectiveSpecs
    .map((spec) => `<option value="${escapeHtml(spec.key)}">${escapeHtml(spec.label)}</option>`)
    .join("");
  byId("campaign-objective").value = state.objectiveSpecs.some((spec) => spec.key === selectedObjective)
    ? selectedObjective
    : (state.objectiveSpecs[0]?.key || "");
  updateBudgetLabel();
  updateCampaignResourceOptions();
  updateObjectiveFields();
}

function resourceOptions(kind, placeholder) {
  const adAccountId = byId("campaign-ad-account").value;
  const items = state.metaResources.filter((item) => item.ad_account_id === adAccountId && item.kind === kind);
  return `<option value="">${escapeHtml(placeholder)}</option>` + items.map((item) => {
    const suffix = item.status === "verified" ? "" : " · chưa xác minh";
    return `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label + suffix)}</option>`;
  }).join("");
}

function updateCampaignResourceOptions() {
  const adAccountId = byId("campaign-ad-account").value;
  byId("campaign-page-resource").innerHTML = resourceOptions("page", "Chưa chọn Page");
  byId("campaign-dataset-resource").innerHTML = resourceOptions("dataset", "Chưa chọn Pixel/Dataset");
  byId("campaign-app-resource").innerHTML = resourceOptions("app", "Chưa chọn ứng dụng");
  byId("campaign-lead-form-resource").innerHTML = resourceOptions("instant_form", "Chưa chọn Instant Form");
  const assets = state.creativeAssets.filter((item) => item.ad_account_id === adAccountId && item.status === "ready");
  byId("campaign-asset").innerHTML = '<option value="">Chưa chọn ảnh/video</option>' + assets.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${escapeHtml(item.file_name)}</option>`).join("");
}

function openAdAccountDialog() {
  if (!state.facebookAccounts.length) return showNotice("Hãy thêm tài khoản Facebook trước khi tạo ad account.");
  state.editingAdAccountId = null;
  byId("ad-account-form").reset();
  byId("ad-account-timezone").value = "Asia/Ho_Chi_Minh";
  byId("ad-account-dialog-title").textContent = "Thêm ad account";
  byId("ad-account-dialog-description").textContent = "Thông tin quản lý nội bộ, chưa gọi Meta API.";
  byId("ad-account-submit-button").textContent = "Lưu ad account";
  byId("ad-account-edit-warning").hidden = true;
  byId("ad-account-dialog").showModal();
  byId("meta-ad-account-id").focus();
}

function openAdAccountEditDialog(adAccountId) {
  const account = state.adAccounts.find((item) => item.id === adAccountId);
  if (!account) return showNotice("Không tìm thấy ad account cần sửa.");
  state.editingAdAccountId = account.id;
  byId("facebook-account-select").value = account.facebook_account_id;
  byId("meta-ad-account-id").value = account.meta_ad_account_id;
  byId("ad-account-label").value = account.label;
  byId("ad-account-currency").value = account.currency;
  byId("ad-account-timezone").value = account.timezone_name;
  byId("ad-account-dialog-title").textContent = "Sửa ad account";
  byId("ad-account-dialog-description").textContent = "Cập nhật thông tin quản lý và giữ nguyên ranh giới dữ liệu đã liên kết.";
  byId("ad-account-submit-button").textContent = "Lưu thay đổi";
  byId("ad-account-edit-warning").hidden = false;
  byId("ad-account-dialog").showModal();
  byId("ad-account-label").focus();
  byId("ad-account-label").select();
}

function openResourceDialog() {
  if (!state.adAccounts.length) return showNotice("Hãy thêm ad account trước khi tạo Meta resource.");
  byId("resource-dialog").showModal();
  byId("resource-label").focus();
}

function openAssetDialog() {
  if (!state.adAccounts.length) return showNotice("Hãy thêm ad account trước khi tải creative asset.");
  byId("asset-dialog").showModal();
  byId("asset-label").focus();
}

function openCampaignDialog(adAccountId = null) {
  if (!state.adAccounts.length) return showNotice("Hãy thêm ad account trước khi tạo campaign draft.");
  if (adAccountId && state.adAccounts.some((item) => item.id === adAccountId)) {
    byId("campaign-ad-account").value = adAccountId;
    updateBudgetLabel();
    updateCampaignResourceOptions();
  }
  byId("campaign-dialog").showModal();
  byId("campaign-name").focus();
}

function updateBudgetLabel() {
  const account = state.adAccounts.find((item) => item.id === byId("campaign-ad-account").value);
  byId("budget-label").textContent = `Ngân sách mỗi ngày${account ? ` (${account.currency})` : ""}`;
}

function updateObjectiveFields() {
  const objective = byId("campaign-objective").value;
  const spec = state.objectiveSpecs.find((item) => item.key === objective);
  document.querySelectorAll("[data-objectives]").forEach((element) => {
    element.hidden = !element.dataset.objectives.split(/\s+/).includes(objective);
  });
  if (!spec) {
    byId("objective-summary").textContent = "Chưa tải được capability của objective.";
    return;
  }
  byId("campaign-conversion-location").value = spec.conversion_location_label;
  byId("campaign-performance-goal").value = spec.performance_goal_label;
  const setupCopy = spec.setup_mode === "manual"
    ? "Worker sẽ chọn nhánh thiết lập thủ công trước khi vào Campaign."
    : "Meta đi thẳng vào Campaign theo default path đã khảo sát.";
  byId("objective-summary").innerHTML = `<strong>${escapeHtml(spec.label)}</strong> · ${escapeHtml(setupCopy)} Default: ${escapeHtml(spec.conversion_location_label)} → ${escapeHtml(spec.performance_goal_label)}.`;
}

async function createAdAccount(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    const payload = {
      facebook_account_id: byId("facebook-account-select").value,
      meta_ad_account_id: byId("meta-ad-account-id").value.trim(),
      label: byId("ad-account-label").value.trim(),
      currency: byId("ad-account-currency").value,
      timezone_name: byId("ad-account-timezone").value.trim(),
    };
    const editing = Boolean(state.editingAdAccountId);
    await api(editing ? `/api/ad-accounts/${state.editingAdAccountId}` : "/api/ad-accounts", {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    byId("ad-account-dialog").close();
    event.target.reset();
    byId("ad-account-timezone").value = "Asia/Ho_Chi_Minh";
    state.editingAdAccountId = null;
    await loadPage(editing ? "Đã cập nhật ad account." : "Đã thêm ad account.");
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function createMetaResource(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api("/api/meta-resources", { method: "POST", body: JSON.stringify({
      ad_account_id: byId("resource-ad-account").value,
      kind: byId("resource-kind").value,
      label: byId("resource-label").value.trim(),
      external_id: byId("resource-external-id").value.trim() || null,
      metadata_json: {},
    }) });
    byId("resource-dialog").close();
    event.target.reset();
    await loadPage("Đã lưu resource ở trạng thái chưa xác minh.");
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

function openResourceVerification(resourceId) {
  const resource = state.metaResources.find((item) => item.id === resourceId);
  if (!resource) return;
  state.selectedResourceId = resourceId;
  byId("resource-verify-summary").textContent = `${resourceKindLabels[resource.kind] || resource.kind} · ${resource.label}`;
  byId("resource-verify-confirmation").value = "";
  byId("resource-verify-dialog").showModal();
  byId("resource-verify-confirmation").focus();
}

async function verifyMetaResource() {
  const resourceId = state.selectedResourceId;
  if (!resourceId) return;
  try {
    await api(`/api/meta-resources/${resourceId}/verify`, { method: "POST", body: JSON.stringify({ confirmation: byId("resource-verify-confirmation").value.trim() }) });
    byId("resource-verify-dialog").close();
    await loadPage("Đã đánh dấu resource là đã xác minh.");
  } catch (error) { showNotice(error.message); }
}

async function uploadCreativeAsset(event) {
  event.preventDefault();
  const submit = event.submitter;
  const file = byId("asset-file").files[0];
  if (!file) return showNotice("Hãy chọn file creative.");
  submit.disabled = true;
  byId("asset-upload-status").textContent = `Đang tải ${file.name} (${fileSize(file.size)})…`;
  try {
    const query = new URLSearchParams({
      ad_account_id: byId("asset-ad-account").value,
      label: byId("asset-label").value.trim(),
      file_name: file.name,
    });
    const suffix = file.name.split(".").pop()?.toLowerCase();
    const inferredType = {
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      png: "image/png",
      webp: "image/webp",
      mp4: "video/mp4",
      mov: "video/quicktime",
    }[suffix];
    await apiRaw(`/api/creative-assets?${query}`, file, file.type || inferredType || "application/octet-stream");
    byId("asset-dialog").close();
    event.target.reset();
    byId("asset-upload-status").textContent = "Giới hạn 250 MB. Hỗ trợ JPG, PNG, WEBP, MP4 và MOV.";
    await loadPage("Đã lưu creative asset và xác minh SHA-256.");
  } catch (error) {
    byId("asset-upload-status").textContent = "Upload chưa hoàn tất.";
    showNotice(error.message);
  } finally { submit.disabled = false; }
}

function localDateToIso(value) {
  return value ? new Date(value).toISOString() : null;
}

async function createCampaign(event) {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    const account = state.adAccounts.find((item) => item.id === byId("campaign-ad-account").value);
    const multiplier = zeroDecimalCurrencies.has(account.currency) ? 1 : 100;
    const dailyBudgetMinor = Math.round(Number(byId("campaign-budget").value) * multiplier);
    await api("/api/campaign-drafts", { method: "POST", body: JSON.stringify({
      ad_account_id: account.id,
      name: byId("campaign-name").value.trim(),
      objective: byId("campaign-objective").value,
      daily_budget_minor: dailyBudgetMinor,
      start_at: localDateToIso(byId("campaign-start").value),
      end_at: localDateToIso(byId("campaign-end").value),
      targeting_json: {
        note: byId("campaign-targeting").value.trim(),
        page_resource_id: byId("campaign-page-resource").value || null,
        countries: byId("campaign-countries").value.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
        age_min: Number(byId("campaign-age-min").value),
        age_max: Number(byId("campaign-age-max").value),
        placements: byId("campaign-placements").value,
        conversion_location: state.objectiveSpecs.find((item) => item.key === byId("campaign-objective").value)?.default_conversion_location || "",
        performance_goal: state.objectiveSpecs.find((item) => item.key === byId("campaign-objective").value)?.performance_goal || "",
        messaging_destination: byId("campaign-messaging-destination").value,
        app_resource_id: byId("campaign-app-resource").value || null,
        app_store_country: byId("campaign-app-store-country").value.trim().toUpperCase(),
        dataset_resource_id: byId("campaign-dataset-resource").value || null,
        conversion_event: byId("campaign-conversion-event").value.trim(),
      },
      creative_json: {
        note: byId("campaign-creative").value.trim(),
        primary_text: byId("campaign-primary-text").value.trim(),
        headline: byId("campaign-headline").value.trim(),
        destination_url: byId("campaign-destination-url").value.trim(),
        cta: byId("campaign-cta").value,
        lead_form_resource_id: byId("campaign-lead-form-resource").value || null,
        asset_id: byId("campaign-asset").value || null,
      },
    }) });
    byId("campaign-dialog").close();
    event.target.reset();
    await loadPage("Đã lưu campaign draft. Chưa có dữ liệu nào được gửi sang Meta.");
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

async function submitCampaign(campaignId) {
  const campaign = state.campaigns.find((item) => item.id === campaignId);
  if (!campaign || !window.confirm(`Gửi “${campaign.name}” vào hàng chờ duyệt?`)) return;
  try {
    await api(`/api/campaign-drafts/${campaignId}/submit`, { method: "POST", body: "{}" });
    await loadPage("Đã gửi campaign vào hàng chờ duyệt.");
  } catch (error) { showNotice(error.message); }
}

async function openExecutionPreview(campaignId, mode = "preflight") {
  try {
    const preview = await api(`/api/campaign-drafts/${campaignId}/execution-preview`);
    state.selectedCampaignId = campaignId;
    state.executionMode = mode;
    const isDraftBuild = mode === "draft_build";
    byId("execution-preview-facts").innerHTML = [
      ["Campaign", `${preview.campaign_name} · v${preview.campaign_version}`],
      ["Ad account", `${preview.ad_account_label} · ${preview.meta_ad_account_id}`],
      ["Facebook profile", `${preview.facebook_account_label} · ${preview.facebook_account_status}`],
      ["Worker", `${preview.worker_name} · ${preview.worker_status}`],
      ["Browser session", preview.active_browser_session ? "Đang hoạt động" : "Không có"],
      ["Phạm vi", isDraftBuild ? "Draft-only · có click · dừng trước Đăng" : "Read-only · không click · không publish"],
    ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
    byId("execution-dialog-title").textContent = isDraftBuild ? "Tạo Meta draft" : "Execution preview";
    byId("execution-dialog-description").textContent = isDraftBuild
      ? "Worker tạo mới Campaign, Ad Set và Ad từ đầu rồi dừng trước publish."
      : "Kiểm tra readiness trước khi đưa preflight cho worker.";
    const blockers = byId("execution-blockers");
    const activeBlockers = isDraftBuild ? preview.draft_blockers : preview.blockers;
    const warnings = isDraftBuild ? preview.draft_warnings : [];
    blockers.hidden = activeBlockers.length === 0 && warnings.length === 0;
    blockers.classList.toggle("execution-warnings", activeBlockers.length === 0 && warnings.length > 0);
    blockers.textContent = [...activeBlockers, ...warnings.map((item) => `Lưu ý: ${item}`)].join("\n");
    const confirmationText = isDraftBuild ? "TẠO DRAFT META" : "CHẠY PREFLIGHT";
    byId("execution-confirmation-label").firstChild.textContent = isDraftBuild ? "Xác nhận tạo draft" : "Xác nhận preflight";
    byId("execution-confirmation").value = "";
    byId("execution-confirmation").placeholder = `Nhập: ${confirmationText}`;
    byId("execution-safety-copy").innerHTML = isDraftBuild
      ? 'Worker được phép click/điền field nhưng contract luôn đặt <span class="mono-text">allow_publish=false</span>. Nút Đăng không bao giờ được click.'
      : 'Job chỉ điều hướng và đọc trạng thái. Contract đặt <span class="mono-text">allow_click=false</span> và <span class="mono-text">allow_publish=false</span>.';
    byId("queue-execution-button").disabled = isDraftBuild ? !preview.can_build_draft : !preview.can_run_preflight;
    byId("queue-execution-button").textContent = isDraftBuild ? "Tạo draft trên Meta" : "Đưa vào hàng chờ";
    byId("execution-dialog").showModal();
  } catch (error) { showNotice(error.message); }
}

async function queueExecution() {
  const confirmation = byId("execution-confirmation").value.trim();
  try {
    await api("/api/execution-jobs", { method: "POST", body: JSON.stringify({ campaign_id: state.selectedCampaignId, job_type: state.executionMode, confirmation }) });
    byId("execution-dialog").close();
    await loadPage(state.executionMode === "draft_build" ? "Đã đưa Meta draft builder vào hàng chờ worker." : "Đã đưa preflight read-only vào hàng chờ worker.");
  } catch (error) { showNotice(error.message); }
}

async function openJobResult(jobId) {
  try {
    const job = await api(`/api/execution-jobs/${jobId}`);
    const artifacts = await api(`/api/execution-jobs/${jobId}/artifacts`);
    state.selectedJobId = jobId;
    const result = job.result_json || {};
    const isDraftBuild = job.job_type === "draft_build";
    byId("job-result-title").textContent = isDraftBuild ? "Chi tiết Meta draft builder" : "Chi tiết preflight";
    byId("job-result-facts").innerHTML = [
      ["Trạng thái", statusMeta[job.status]?.[0] || job.status],
      ["Readiness", result.readiness || "Chưa có"],
      ["Bước dừng", result.phase || (isDraftBuild ? "Chưa chạy" : "Preflight")],
      ["Đã đăng nhập", result.authenticated == null ? "Chưa kiểm tra" : (result.authenticated ? "Có" : "Không")],
      ["Ads Manager", result.ads_manager_loaded == null ? "Chưa kiểm tra" : (result.ads_manager_loaded ? "Đã tải" : "Chưa tải")],
      ["Đúng ad account", result.ad_account_confirmed == null ? "Chưa kiểm tra" : (result.ad_account_confirmed ? "Có" : "Chưa xác nhận")],
      ["Trang hiện tại", result.current_url || "—"],
      ["Số lần chạy", job.attempt_count],
      ["Hoàn thành", dateTime(job.completed_at)],
    ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
    const error = byId("job-error");
    const blockerLines = Array.isArray(result.blockers) ? result.blockers : [];
    const errorLines = [...blockerLines, job.last_error].filter(Boolean);
    error.hidden = errorLines.length === 0;
    error.textContent = errorLines.join("\n");
    const fieldResults = Array.isArray(result.field_results) ? result.field_results : [];
    const fieldSection = byId("job-field-results");
    fieldSection.hidden = fieldResults.length === 0;
    byId("job-field-results-body").innerHTML = fieldResults.map((item) => `<tr><td>${escapeHtml(item.stage || "—")}</td><td><span class="mono-text">${escapeHtml(item.field_path || "—")}</span></td><td>${fieldBadge(item.status)}</td><td>${escapeHtml(item.detail || "—")}</td></tr>`).join("");
    const successfulFields = fieldResults.filter((item) => ["applied", "already_set", "verified"].includes(item.status)).length;
    byId("job-field-results-summary").textContent = fieldResults.length
      ? `${successfulFields}/${fieldResults.length} field đã áp dụng hoặc xác minh.`
      : "";
    const artifactLabels = { screenshot: "Screenshot", campaign_step: "Campaign", adset_step: "Ad Set", ad_step: "Ad", review_step: "Review", failure: "Lỗi" };
    byId("job-artifact-links").innerHTML = artifacts.map((item) => `<a class="button button-secondary" href="/api/execution-artifacts/${escapeHtml(item.id)}" target="_blank" rel="noopener">${escapeHtml(artifactLabels[item.kind] || item.kind)}</a>`).join("");
    const canRetry = ["failed", "awaiting_user"].includes(job.status) && ["owner", "admin"].includes(document.body.dataset.role);
    const canHandoff = job.status === "awaiting_user" && Boolean(result.current_url);
    byId("retry-confirmation-label").hidden = !canRetry;
    byId("retry-job-button").hidden = !canRetry;
    byId("handoff-job-button").hidden = !canHandoff;
    byId("retry-confirmation").value = "";
    byId("retry-confirmation").placeholder = `Nhập: ${isDraftBuild ? "TẠO DRAFT META" : "CHẠY PREFLIGHT"}`;
    byId("retry-job-button").textContent = isDraftBuild ? "Retry draft builder" : "Retry preflight";
    byId("job-result-dialog").showModal();
  } catch (error) { showNotice(error.message); }
}

async function retryJob() {
  try {
    await api(`/api/execution-jobs/${state.selectedJobId}/retry`, { method: "POST", body: JSON.stringify({ confirmation: byId("retry-confirmation").value.trim() }) });
    byId("job-result-dialog").close();
    await loadPage("Đã đưa execution job vào hàng chờ chạy lại.");
  } catch (error) { showNotice(error.message); }
}

async function openJobHandoff() {
  const job = state.executionJobs.find((item) => item.id === state.selectedJobId);
  const launchUrl = job?.result_json?.current_url;
  if (!job || !launchUrl) return showNotice("Job chưa có Ads Manager URL để bàn giao.");
  const handoffTab = window.open("about:blank", "_blank");
  try {
    const session = await api(`/api/accounts/${job.facebook_account_id}/browser-sessions`, {
      method: "POST",
      body: JSON.stringify({ launch_url: launchUrl }),
    });
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const current = await api(`/api/browser-sessions/${session.id}`);
      if (current.novnc_url && ["awaiting_user", "ready"].includes(current.status)) {
        if (handoffTab) handoffTab.location = current.novnc_url;
        byId("job-result-dialog").close();
        return showNotice("Đã mở noVNC tại đúng URL Meta draft. Xử lý xong hãy đóng phiên rồi retry job.", "success");
      }
      if (["failed", "closed", "expired"].includes(current.status)) {
        throw new Error(current.last_error || `Browser session ${current.status}.`);
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error("noVNC chưa sẵn sàng sau 40 giây.");
  } catch (error) {
    if (handoffTab) handoffTab.close();
    showNotice(error.message);
  }
}

function reviewApproval(approvalId) {
  const approval = state.approvals.find((item) => item.id === approvalId);
  if (!approval) return;
  state.selectedApprovalId = approvalId;
  const snapshot = approval.snapshot_json;
  const account = state.adAccounts.find((item) => item.id === snapshot.ad_account_id);
  byId("approval-facts").innerHTML = [
    ["Campaign", snapshot.name],
    ["Ad account", account?.label || snapshot.ad_account_id],
    ["Mục tiêu", snapshot.objective],
    ["Vị trí chuyển đổi", snapshot.targeting_json?.conversion_location || "Theo default objective"],
    ["Mục tiêu hiệu quả", snapshot.targeting_json?.performance_goal || "Theo default objective"],
    ["Ngân sách/ngày", money(snapshot.daily_budget_minor, snapshot.currency)],
    ["Lịch chạy", `${dateTime(snapshot.start_at)} → ${dateTime(snapshot.end_at)}`],
    ["Targeting", `${(snapshot.targeting_json?.countries || []).join(", ") || "Chưa chọn quốc gia"} · ${snapshot.targeting_json?.note || "Không có ghi chú"}`],
    ["Page Facebook", snapshot.targeting_json?.page_name || "Chưa chọn"],
    ["Creative", snapshot.creative_json?.headline || snapshot.creative_json?.note || "Chưa cấu hình"],
    ["Asset", snapshot.creative_json?.asset_snapshot?.label || "Chưa chọn"],
    ["Destination URL", snapshot.creative_json?.destination_url || "Chưa cấu hình"],
    ["Objective-specific", snapshot.targeting_json?.messaging_destination || snapshot.targeting_json?.app_name || snapshot.creative_json?.lead_form_name || snapshot.targeting_json?.conversion_event || "Không có"],
    ["Version", `v${snapshot.version}`],
  ].map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
  byId("decision-note").value = "";
  const canApprove = ["owner", "admin"].includes(document.body.dataset.role);
  byId("approve-button").disabled = !canApprove;
  byId("reject-button").disabled = !canApprove;
  byId("approval-dialog").showModal();
}

async function decideApproval(decision) {
  const note = byId("decision-note").value.trim();
  if (decision === "reject" && !note) return showNotice("Hãy nhập lý do từ chối.");
  const action = decision === "approve" ? "approve" : "reject";
  try {
    await api(`/api/approval-requests/${state.selectedApprovalId}/${action}`, { method: "POST", body: JSON.stringify({ note: note || null }) });
    byId("approval-dialog").close();
    await loadPage(decision === "approve" ? "Đã duyệt nội bộ. Campaign vẫn chưa được publish lên Meta." : "Đã từ chối campaign.");
  } catch (error) { showNotice(error.message); }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#add-ad-account-button, [data-open-ad-account]")) openAdAccountDialog();
  if (event.target.closest("#add-resource-button, [data-open-resource]")) openResourceDialog();
  if (event.target.closest("#add-asset-button, [data-open-asset]")) openAssetDialog();
  if (event.target.closest("#add-campaign-button, [data-open-campaign]")) openCampaignDialog();
  const close = event.target.closest("[data-close]");
  if (close) byId(close.dataset.close).close();
  const submit = event.target.closest("[data-submit-campaign]");
  if (submit) submitCampaign(submit.dataset.submitCampaign);
  const review = event.target.closest("[data-review-approval]");
  if (review) reviewApproval(review.dataset.reviewApproval);
  const preflight = event.target.closest("[data-preflight-campaign]");
  if (preflight) openExecutionPreview(preflight.dataset.preflightCampaign, "preflight");
  const draftBuild = event.target.closest("[data-build-draft-campaign]");
  if (draftBuild) openExecutionPreview(draftBuild.dataset.buildDraftCampaign, "draft_build");
  const job = event.target.closest("[data-view-job]");
  if (job) openJobResult(job.dataset.viewJob);
  const verifyResource = event.target.closest("[data-verify-resource]");
  if (verifyResource) openResourceVerification(verifyResource.dataset.verifyResource);
  const editAdAccount = event.target.closest("[data-edit-ad-account]");
  if (editAdAccount) openAdAccountEditDialog(editAdAccount.dataset.editAdAccount);
  const createCampaignForAdAccount = event.target.closest("[data-create-campaign-for-ad-account]");
  if (createCampaignForAdAccount) openCampaignDialog(createCampaignForAdAccount.dataset.createCampaignForAdAccount);
});

byId("ad-account-form").addEventListener("submit", createAdAccount);
byId("resource-form").addEventListener("submit", createMetaResource);
byId("asset-form").addEventListener("submit", uploadCreativeAsset);
byId("campaign-form").addEventListener("submit", createCampaign);
byId("campaign-ad-account").addEventListener("change", () => { updateBudgetLabel(); updateCampaignResourceOptions(); });
byId("campaign-objective").addEventListener("change", updateObjectiveFields);
byId("refresh-button").addEventListener("click", () => loadPage());
byId("approve-button").addEventListener("click", () => decideApproval("approve"));
byId("reject-button").addEventListener("click", () => decideApproval("reject"));
byId("queue-execution-button").addEventListener("click", queueExecution);
byId("retry-job-button").addEventListener("click", retryJob);
byId("handoff-job-button").addEventListener("click", openJobHandoff);
byId("confirm-resource-verify-button").addEventListener("click", verifyMetaResource);
loadPage();

setInterval(() => {
  if (state.executionJobs.some((job) => ["queued", "claimed", "running"].includes(job.status))) loadPage();
}, 5000);
