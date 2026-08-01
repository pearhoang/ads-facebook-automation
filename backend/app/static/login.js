const form = document.getElementById("login-form");
const errorBox = document.getElementById("login-error");
const submitButton = document.getElementById("login-button");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  submitButton.disabled = true;
  submitButton.textContent = "Đang đăng nhập…";
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.email.value.trim(),
        password: form.password.value,
      }),
    });
    if (!response.ok) {
      let message = "Không thể đăng nhập.";
      try { message = (await response.json()).detail || message; } catch (_) {}
      throw new Error(message);
    }
    window.location.assign("/");
  } catch (error) {
    errorBox.textContent = error.message || "Không thể đăng nhập.";
    errorBox.hidden = false;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Đăng nhập";
  }
});
