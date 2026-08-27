/* Mail.main — инициализация: STATE, события, старт. */
"use strict";

Mail.STATE = { mails: [], outbox: [], tab: "inbox", current: null, query: "", deleteArm: 0, owner: "" };

/* ── события ─────────────────────────────────────────── */
Mail.$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const addr = Mail.$("login-addr").value.trim();
  const r = await Mail.api("/api/login", { method: "POST", body: JSON.stringify({ address: addr, password: Mail.$("login-pass").value }) });
  if (r.ok) {
    Mail.$("login-pass").value = "";
    Mail.$("login-error").hidden = true;
    if (r.token) { Mail.STATE.token = r.token; localStorage.setItem("nm_token", r.token); }
    await Mail.loadStatus();
    await Mail.loadMails();
  } else {
    Mail.$("login-error").textContent = r.error === "unknown address" ? "Ящик с таким адресом не найден" : "Неверный пароль";
    Mail.$("login-error").hidden = false;
    Mail.$("login-pass").select();
  }
});

Mail.$("register-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const nsec = Mail.$("reg-nsec").value.trim();
  const label = Mail.$("reg-label").value.trim();
  const pass = Mail.$("reg-pass").value;
  const r = await Mail.api("/api/register", { method: "POST", body: JSON.stringify({ nsec, label, password: pass }) });
  if (r.ok) {
    Mail.$("register-error").textContent = "";
    Mail.$("register-error").hidden = true;
    Mail.$("register-view").hidden = true;
    Mail.$("login-view").hidden = false;
    Mail.$("login-addr").value = r.address;
    Mail.$("login-pass").value = "";
    Mail.$("login-pass").focus();
  } else {
    const msg = r.error === "already registered" ? "Этот ключ уже зарегистрирован — войди" :
                r.error === "invalid nsec" ? "Неверный nsec" :
                r.error === "password too short" ? "Пароль короче 6 символов" : "Ошибка регистрации";
    Mail.$("register-error").textContent = msg;
    Mail.$("register-error").hidden = false;
  }
});

Mail.$("btn-show-register").addEventListener("click", () => {
  Mail.$("login-view").hidden = true;
  Mail.$("register-view").hidden = false;
  Mail.$("reg-nsec").focus();
});
Mail.$("btn-show-reset").addEventListener("click", () => {
  Mail.$("login-view").hidden = true;
  Mail.$("reset-view").hidden = false;
});
Mail.$("btn-reset-back").addEventListener("click", () => {
  Mail.$("reset-view").hidden = true;
  Mail.$("login-view").hidden = false;
});
Mail.$("reset-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const r = await Mail.api("/api/reset-password", {
    method: "POST",
    body: JSON.stringify({
      address: Mail.$("reset-addr").value.trim(),
      nsec: Mail.$("reset-nsec").value.trim(),
      new_password: Mail.$("reset-pass").value,
    }),
  });
  if (r.ok) {
    Mail.$("reset-error").hidden = true;
    alert("Пароль сброшен. Войдите с новым паролем.");
    Mail.$("reset-view").hidden = true;
    Mail.$("login-view").hidden = false;
    Mail.$("login-addr").value = Mail.$("reset-addr").value.trim();
  } else {
    Mail.$("reset-error").textContent = r.error || "Ошибка";
    Mail.$("reset-error").hidden = false;
  }
});
Mail.$("btn-show-login").addEventListener("click", () => {
  Mail.$("register-view").hidden = true;
  Mail.$("login-view").hidden = false;
  Mail.$("login-addr").focus();
});

Mail.$("btn-logout").addEventListener("click", async () => {
  await Mail.api("/api/logout", { method: "POST" }).catch(() => {});
  Mail.STATE.token = "";
  localStorage.removeItem("nm_token");
  location.reload();
});

Mail.$("btn-compose").addEventListener("click", () => Mail.openComposer("Новое письмо"));
Mail.$("account-switch").addEventListener("change", (ev) => Mail.setAccount(ev.target.value));
Mail.$("btn-close").addEventListener("click", Mail.closeComposer);
Mail.$("btn-cancel").addEventListener("click", Mail.closeComposer);
Mail.$("compose-backdrop").addEventListener("click", (ev) => {
  if (ev.target === Mail.$("compose-backdrop")) Mail.closeComposer();
});
Mail.$("compose-form").addEventListener("submit", Mail.sendMail);

Mail.$("btn-reply").addEventListener("click", Mail.replyTo);
Mail.$("btn-back").addEventListener("click", Mail.backToList);
Mail.$("btn-delete").addEventListener("click", Mail.deleteMail);
Mail.$("btn-unread").addEventListener("click", Mail.toggleRead);
Mail.$("mail-address").addEventListener("click", Mail.copyAddress);

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && !Mail.$("compose-backdrop").hidden) Mail.closeComposer();
  if (ev.key === "Escape" && !Mail.$("help-backdrop").hidden) Mail.closeHelp();
});

/* ── инструкция ── */
Mail.openHelp = function () { Mail.$("help-backdrop").hidden = false; };
Mail.closeHelp = function () { Mail.$("help-backdrop").hidden = true; };
Mail.$("btn-help").addEventListener("click", Mail.openHelp);
Mail.$("btn-help-login").addEventListener("click", Mail.openHelp);
Mail.$("btn-help-close").addEventListener("click", Mail.closeHelp);
Mail.$("help-backdrop").addEventListener("click", (ev) => {
  if (ev.target === Mail.$("help-backdrop")) Mail.closeHelp();
});

Mail.$("search").addEventListener("input", () => {
  Mail.STATE.query = Mail.$("search").value.trim();
  Mail.renderList();
});

document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => Mail.switchTab(t.dataset.tab));
});

/* ── старт ── */
(async () => {
  await Mail.loadStatus();
  if (!Mail.$("main-view").hidden) await Mail.loadMails();
})();
