/* Mail.api — транспорт: fetch с авторизацией, views, статус, авто-обновление. */
"use strict";

Mail.api = async function (path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* 204/empty */ }
  if (res.status === 401 || data.error === "auth") { Mail.showLogin(); throw new Error("auth"); }
  return data;
};

Mail.showLogin = function () {
  Mail.$("login-view").hidden = false;
  Mail.$("main-view").hidden = true;
  Mail.stopRefresh();
};

Mail.showMain = function () {
  Mail.$("login-view").hidden = true;
  Mail.$("main-view").hidden = false;
  Mail.startRefresh();
};

Mail.loadStatus = async function () {
  const s = await Mail.api("/api/status");
  Mail.$("mail-address").textContent = s.address || "—";
  Mail.$("ln-addr").textContent = s.lightning || "—";
  Mail.$("empty-addr").textContent = s.address || "";
  Mail.$("btn-logout").hidden = !s.ok;
  if (s.ok) Mail.showMain(); else Mail.showLogin();
  return s;
};

Mail.copyAddress = async function () {
  const addr = Mail.$("mail-address").textContent;
  if (!addr || addr === "—") return;
  try {
    await navigator.clipboard.writeText(addr);
    Mail.showToast("Адрес скопирован 📋");
  } catch (_) {
    Mail.showToast(addr, "ok");
  }
};

/* ── авто-обновление (30с, только входящие на виду) ── */
let refreshTimer = null;
Mail.startRefresh = function () {
  Mail.stopRefresh();
  refreshTimer = setInterval(() => {
    if (document.hidden) return;
    if (Mail.STATE.tab === "inbox" && !Mail.$("list-view").hidden) Mail.loadMails();
  }, 30000);
};
Mail.stopRefresh = function () {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
};
