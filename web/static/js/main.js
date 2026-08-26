/* Mail.main — инициализация: STATE, события, старт. */
"use strict";

Mail.STATE = { mails: [], outbox: [], tab: "inbox", current: null, query: "", deleteArm: 0 };

/* ── события ─────────────────────────────────────────── */
Mail.$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const r = await Mail.api("/api/login", { method: "POST", body: JSON.stringify({ password: Mail.$("login-pass").value }) });
  if (r.ok) {
    Mail.$("login-pass").value = "";
    Mail.$("login-error").hidden = true;
    await Mail.loadStatus();
    await Mail.loadMails();
  } else {
    Mail.$("login-error").textContent = "Неверный пароль";
    Mail.$("login-error").hidden = false;
    Mail.$("login-pass").select();
  }
});

Mail.$("btn-logout").addEventListener("click", async () => {
  await Mail.api("/api/logout", { method: "POST" }).catch(() => {});
  location.reload();
});

Mail.$("btn-compose").addEventListener("click", () => Mail.openComposer("Новое письмо"));
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
