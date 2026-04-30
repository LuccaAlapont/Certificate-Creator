/** auth.js — login form + logout helper. */

(function () {
  const form    = document.getElementById("loginForm");
  const btnLogin = document.getElementById("btnLogin");
  const errorMsg = document.getElementById("errorMsg");

  if (!form) return; // not on the login page

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorMsg.textContent = "";
    btnLogin.disabled = true;
    btnLogin.textContent = "Entrando…";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok) {
        window.location.replace("/");
      } else {
        errorMsg.textContent = data.error || "Erro ao autenticar.";
      }
    } catch {
      errorMsg.textContent = "Erro de conexão com o servidor.";
    } finally {
      btnLogin.disabled = false;
      btnLogin.textContent = "Entrar";
    }
  });
})();

async function authLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.replace("/login");
}
