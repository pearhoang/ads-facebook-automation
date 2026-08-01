(() => {
  const dialog = document.getElementById("password-dialog");
  const form = document.getElementById("password-form");
  const status = document.getElementById("password-status");
  const submitButton = document.getElementById("password-submit");
  if (!dialog || !form || !status || !submitButton) return;

  const currentPassword = document.getElementById("current-password");
  const newPassword = document.getElementById("new-password");
  const confirmation = document.getElementById("new-password-confirmation");

  const clearSecrets = () => {
    currentPassword.value = "";
    newPassword.value = "";
    confirmation.value = "";
  };

  const showStatus = (message, kind) => {
    status.textContent = message;
    status.className = `password-status password-status-${kind}`;
    status.hidden = false;
  };

  document.querySelectorAll("[data-open-password-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      clearSecrets();
      status.hidden = true;
      status.textContent = "";
      dialog.showModal();
      currentPassword.focus();
    });
  });

  document.querySelectorAll("[data-close-password-dialog]").forEach((button) => {
    button.addEventListener("click", () => {
      clearSecrets();
      dialog.close();
    });
  });

  dialog.addEventListener("cancel", clearSecrets);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.hidden = true;
    if (newPassword.value !== confirmation.value) {
      showStatus("Xác nhận mật khẩu mới không khớp.", "error");
      confirmation.focus();
      return;
    }

    const payload = {
      current_password: currentPassword.value,
      new_password: newPassword.value,
      new_password_confirmation: confirmation.value,
    };
    submitButton.disabled = true;
    try {
      const response = await fetch("/api/auth/password", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": document.body.dataset.csrfToken || "",
        },
        body: JSON.stringify(payload),
      });
      clearSecrets();
      if (response.status === 401) {
        window.location.assign("/login");
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        showStatus(body.detail || "Không thể đổi mật khẩu. Hãy thử lại.", "error");
        currentPassword.focus();
        return;
      }
      showStatus("Đã đổi mật khẩu. Các phiên đăng nhập khác đã được đăng xuất.", "success");
    } catch (_error) {
      clearSecrets();
      showStatus("Không thể kết nối control-plane. Hãy thử lại.", "error");
    } finally {
      submitButton.disabled = false;
    }
  });
})();
