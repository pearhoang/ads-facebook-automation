(function accountRoutingModule() {
const csrfToken = document.body.dataset.csrfToken;
const byId = (id) => document.getElementById(id);
const state = { facebookAccounts: [], adAccounts: [], resources: [], editingId: null, verifyingId: null, removal: null };

const resourceLabels = { page: "Facebook Page", instagram_account: "Instagram", dataset: "Pixel/Dataset", instant_form: "Instant Form", app: "Ứng dụng" };

function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char])); }

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken, ...(options.headers || {}) } });
  if (response.status === 401) { window.location.href = "/login"; throw new Error("Phiên đăng nhập đã hết hạn."); }
  const payload = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error(payload?.detail || "Yêu cầu không thành công.");
  return payload;
}

function showNotice(message, kind = "error") { window.AppToast.show(byId("notice"), message, { kind }); }
function facebookLabel(id) { return state.facebookAccounts.find((item) => item.id === id)?.label || "—"; }
function accountLabel(id) { return state.adAccounts.find((item) => item.id === id)?.label || "—"; }

function render() {
  if (byId("ad-account-count")) byId("ad-account-count").textContent = state.adAccounts.length;
  if (byId("resource-count")) byId("resource-count").textContent = state.resources.length;
  if (byId("verified-count")) byId("verified-count").textContent = state.resources.filter((item) => item.status === "verified").length;
  if (byId("unverified-count")) byId("unverified-count").textContent = state.resources.filter((item) => item.status !== "verified").length;
  byId("ad-accounts-empty").hidden = state.adAccounts.length > 0;
  byId("resources-empty").hidden = state.resources.length > 0;
  byId("ad-accounts-body").innerHTML = state.adAccounts.map((item) => `
    <tr><td><strong>${escapeHtml(item.label)}</strong></td><td>${escapeHtml(facebookLabel(item.facebook_account_id))}</td><td class="mono-text">${escapeHtml(item.meta_ad_account_id)}</td><td>${escapeHtml(item.currency)}</td><td>${escapeHtml(item.timezone_name)}</td><td><span class="status-pill status-${item.status === "active" ? "success" : "neutral"}">${escapeHtml(item.status)}</span></td><td class="actions-cell"><div class="row-actions"><button class="row-button" type="button" data-edit-ad-account="${escapeHtml(item.id)}" aria-label="Sửa ad account" title="Sửa ad account"><svg aria-hidden="true"><use href="/static/ui-icons.svg#pencil"></use></svg></button><button class="row-button" type="button" data-remove-ad-account="${escapeHtml(item.id)}" aria-label="Gỡ ad account" title="Gỡ ad account"><svg aria-hidden="true"><use href="/static/ui-icons.svg#trash"></use></svg></button></div></td></tr>`).join("");
  byId("resources-body").innerHTML = state.resources.map((item) => `
    <tr><td><strong>${escapeHtml(item.label)}</strong></td><td>${escapeHtml(resourceLabels[item.kind] || item.kind)}</td><td>${escapeHtml(accountLabel(item.ad_account_id))}</td><td class="mono-text">${escapeHtml(item.external_id || "—")}</td><td><span class="status-pill status-${item.status === "verified" ? "success" : "warning"}">${item.status === "verified" ? "Đã xác minh" : "Chưa xác minh"}</span></td><td class="actions-cell"><div class="row-actions">${item.status === "verified" ? "" : `<button class="button button-secondary button-small" type="button" data-verify-resource="${escapeHtml(item.id)}">Xác minh</button>`}<button class="row-button" type="button" data-remove-resource="${escapeHtml(item.id)}" aria-label="Xóa resource" title="Xóa resource"><svg aria-hidden="true"><use href="/static/ui-icons.svg#trash"></use></svg></button></div></td></tr>`).join("");
  const accountOptions = state.adAccounts.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("");
  byId("resource-ad-account").innerHTML = accountOptions;
}

async function loadPage(successMessage = "") {
  try {
    const [facebookAccounts, adAccounts, resources] = await Promise.all([api("/api/accounts"), api("/api/ad-accounts"), api("/api/meta-resources")]);
    state.facebookAccounts = facebookAccounts; state.adAccounts = adAccounts; state.resources = resources; render();
    if (successMessage) showNotice(successMessage, "success"); else window.AppToast.hide(byId("notice"), true);
  } catch (error) { showNotice(error.message); }
}

function openAdAccount(id = null) {
  if (!state.facebookAccounts.length) return showNotice("Hãy thêm và đăng nhập Facebook profile trước.");
  state.editingId = id;
  const item = id ? state.adAccounts.find((entry) => entry.id === id) : null;
  byId("ad-account-dialog-title").textContent = item ? "Sửa ad account" : "Thêm ad account";
  byId("facebook-account-select").innerHTML = state.facebookAccounts.map((entry) => `<option value="${escapeHtml(entry.id)}">${escapeHtml(entry.label)}</option>`).join("");
  byId("facebook-account-select").value = item?.facebook_account_id || state.facebookAccounts[0].id;
  byId("meta-ad-account-id").value = item?.meta_ad_account_id || "";
  byId("ad-account-label").value = item?.label || "";
  byId("ad-account-currency").value = item?.currency || "VND";
  byId("ad-account-timezone").value = item?.timezone_name || "Asia/Ho_Chi_Minh";
  ["facebook-account-select", "meta-ad-account-id", "ad-account-currency", "ad-account-timezone"].forEach((field) => { byId(field).disabled = Boolean(item); });
  byId("ad-account-edit-warning").hidden = !item;
  byId("ad-account-dialog").showModal();
}

async function saveAdAccount(event) {
  event.preventDefault();
  const payload = state.editingId ? { label: byId("ad-account-label").value.trim() } : {
    facebook_account_id: byId("facebook-account-select").value,
    meta_ad_account_id: byId("meta-ad-account-id").value.trim(),
    label: byId("ad-account-label").value.trim(),
    currency: byId("ad-account-currency").value,
    timezone_name: byId("ad-account-timezone").value.trim(),
  };
  try {
    await api(state.editingId ? `/api/ad-accounts/${state.editingId}` : "/api/ad-accounts", { method: state.editingId ? "PATCH" : "POST", body: JSON.stringify(payload) });
    byId("ad-account-dialog").close(); await loadPage("Đã cập nhật ad account.");
  } catch (error) { showNotice(error.message); }
}

function openResource() {
  if (!state.adAccounts.length) return showNotice("Hãy thêm ad account trước.");
  byId("resource-form").reset();
  byId("resource-ad-account").innerHTML = state.adAccounts.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("");
  byId("resource-dialog").showModal();
}

async function saveResource(event) {
  event.preventDefault();
  try {
    await api("/api/meta-resources", { method: "POST", body: JSON.stringify({ ad_account_id: byId("resource-ad-account").value, kind: byId("resource-kind").value, label: byId("resource-label").value.trim(), external_id: byId("resource-external-id").value.trim() || null, metadata_json: {} }) });
    byId("resource-dialog").close(); await loadPage("Đã lưu resource. Hãy xác minh sau khi đối chiếu Meta.");
  } catch (error) { showNotice(error.message); }
}

function openVerify(id) {
  const item = state.resources.find((entry) => entry.id === id); if (!item) return;
  state.verifyingId = id; byId("resource-verify-summary").textContent = `${resourceLabels[item.kind] || item.kind} · ${item.label}`; byId("resource-verify-confirmation").value = ""; byId("resource-verify-dialog").showModal();
}

async function verifyResource() {
  try {
    await api(`/api/meta-resources/${state.verifyingId}/verify`, { method: "POST", body: JSON.stringify({ confirmation: byId("resource-verify-confirmation").value.trim() }) });
    byId("resource-verify-dialog").close(); await loadPage("Đã xác minh resource cho agent sử dụng.");
  } catch (error) { showNotice(error.message); }
}

function openRemoval(kind, id) {
  const catalog = {
    facebook_profile: {
      item: state.facebookAccounts.find((entry) => entry.id === id),
      title: "Gỡ Facebook profile",
      confirm: "Gỡ profile",
      message: (item) => `Profile “${item.label}” sẽ bị gỡ khỏi workspace và Chrome cookie/profile trên Bot VPS sẽ được xóa. Hãy gỡ các ad account liên quan và đóng browser session trước.`,
      path: `/api/accounts/${id}`,
      success: "Đã gỡ Facebook profile và xóa browser profile trên Bot VPS.",
    },
    ad_account: {
      item: state.adAccounts.find((entry) => entry.id === id),
      title: "Gỡ ad account",
      confirm: "Gỡ ad account",
      message: (item) => `Ad account “${item.label}” sẽ không còn được Hermes chọn để chạy hoặc báo cáo. Snapshot và audit cũ vẫn được giữ lại. Lịch báo cáo đang bật sẽ được dừng.`,
      path: `/api/ad-accounts/${id}`,
      success: "Đã gỡ ad account khỏi định tuyến của Hermes.",
    },
    resource: {
      item: state.resources.find((entry) => entry.id === id),
      title: "Xóa Meta resource",
      confirm: "Xóa resource",
      message: (item) => `Resource “${item.label}” sẽ bị xóa khỏi registry. Hermes sẽ không thể chọn resource này cho yêu cầu mới.`,
      path: `/api/meta-resources/${id}`,
      success: "Đã xóa Meta resource.",
    },
  };
  const target = catalog[kind];
  if (!target?.item) return;
  state.removal = target;
  byId("setup-remove-title").textContent = target.title;
  byId("setup-remove-message").textContent = target.message(target.item);
  byId("confirm-setup-remove").textContent = target.confirm;
  byId("setup-remove-dialog").showModal();
}

async function confirmRemoval() {
  const target = state.removal;
  if (!target) return;
  const submit = byId("confirm-setup-remove");
  submit.disabled = true;
  try {
    await api(target.path, { method: "DELETE" });
    byId("setup-remove-dialog").close();
    state.removal = null;
    await loadPage(target.success);
    window.dispatchEvent(new Event("account-routing:changed"));
  } catch (error) { showNotice(error.message); }
  finally { submit.disabled = false; }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#add-ad-account-button, [data-open-ad-account]")) openAdAccount();
  if (event.target.closest("#add-resource-button, [data-open-resource]")) openResource();
  const edit = event.target.closest("[data-edit-ad-account]"); if (edit) openAdAccount(edit.dataset.editAdAccount);
  const verify = event.target.closest("[data-verify-resource]"); if (verify) openVerify(verify.dataset.verifyResource);
  const facebookProfile = event.target.closest("[data-remove-facebook-profile]"); if (facebookProfile) openRemoval("facebook_profile", facebookProfile.dataset.removeFacebookProfile);
  const adAccount = event.target.closest("[data-remove-ad-account]"); if (adAccount) openRemoval("ad_account", adAccount.dataset.removeAdAccount);
  const resource = event.target.closest("[data-remove-resource]"); if (resource) openRemoval("resource", resource.dataset.removeResource);
  const close = event.target.closest("[data-close]"); if (close) byId(close.dataset.close).close();
});

byId("ad-account-form").addEventListener("submit", saveAdAccount);
byId("resource-form").addEventListener("submit", saveResource);
byId("confirm-resource-verify-button").addEventListener("click", verifyResource);
byId("confirm-setup-remove").addEventListener("click", confirmRemoval);
byId("ad-account-refresh-button").addEventListener("click", () => loadPage("Đã làm mới account và resource."));
loadPage();
})();
