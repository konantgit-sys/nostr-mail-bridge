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
  const accs = s.accounts || [];
  const sel = Mail.$("account-switch");
  if (accs.length > 1) {
    sel.hidden = false;
    sel.innerHTML = accs.map((a) => `<option value="${Mail.esc(a.pubkey)}">${Mail.esc(a.label)}</option>`).join("");
    const saved = localStorage.getItem("mail_owner");
    Mail.STATE.owner = accs.some((a) => a.pubkey === saved) ? saved : (s.default_owner || accs[0].pubkey);
    sel.value = Mail.STATE.owner;
  } else if (accs.length === 1) {
    Mail.STATE.owner = accs[0].pubkey;
  } else {
    Mail.STATE.owner = "";
  }
  const cur = accs.find((a) => a.pubkey === Mail.STATE.owner) || accs[0] || {};
  Mail.$("mail-address").textContent = cur.address || s.address || "—";
  Mail.$("ln-addr").textContent = s.lightning || "—";
  Mail.$("empty-addr").textContent = cur.address || "";
  Mail.$("btn-logout").hidden = !s.ok;
  if (s.ok) Mail.showMain(); else Mail.showLogin();
  return s;
};

Mail.setAccount = async function (owner) {
  Mail.STATE.owner = owner;
  localStorage.setItem("mail_owner", owner);
  const s = await Mail.api("/api/status");
  const cur = (s.accounts || []).find((a) => a.pubkey === owner) || {};
  Mail.$("mail-address").textContent = cur.address || s.address || "—";
  Mail.$("empty-addr").textContent = cur.address || "";
  await Mail.loadMails();
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
