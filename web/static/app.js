/* Nostr Mail — фронтенд-логика v2 (2026-08-26)
   Поиск, удаление, прочитано/непрочитано, авто-обновление,
   копирование адреса, валидация, stagger-анимации, Esc. */
"use strict";

const $ = (id) => document.getElementById(id);
const STATE = { mails: [], outbox: [], tab: "inbox", current: null, query: "", refreshTimer: null, deleteArm: 0 };

/* ── api ─────────────────────────────────────────────── */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* 204/empty */ }
  if (res.status === 401) { showLogin(); throw new Error("auth"); }
  return data;
}

/* ── views ───────────────────────────────────────────── */
function showLogin() {
  $("login-view").hidden = false;
  $("main-view").hidden = true;
  stopRefresh();
}

function showMain() {
  $("login-view").hidden = true;
  $("main-view").hidden = false;
  startRefresh();
}

/* ── toast ───────────────────────────────────────────── */
let toastTimer = null;
function showToast(msg, kind = "ok") {
  const t = $("toast");
  t.textContent = msg;
  t.dataset.kind = kind;
  t.classList.remove("toast-visible");
  void t.offsetWidth; /* рестарт анимации */
  t.classList.add("toast-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("toast-visible"), 2800);
}

/* ── формат времени ──────────────────────────────────── */
function fmtDate(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function fmtAgo(ts) {
  if (!ts) return "";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "только что";
  if (diff < 3600) return Math.floor(diff / 60) + " мин назад";
  if (diff < 86400) return Math.floor(diff / 3600) + " ч назад";
  if (diff < 172800) return "вчера";
  return new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

function shortNpub(npub) {
  if (!npub) return "";
  return npub.length > 16 ? npub.slice(0, 10) + "…" + npub.slice(-6) : npub;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ── загрузка статуса/писем ──────────────────────────── */
async function loadStatus() {
  const s = await api("/api/status");
  $("mail-address").textContent = s.address || "—";
  $("ln-addr").textContent = s.lightning || "—";
  $("empty-addr").textContent = s.address || "";
  $("btn-logout").hidden = !s.ok;
  if (s.ok) showMain(); else showLogin();
  return s;
}

async function loadMails() {
  try {
    const d = await api("/api/mails");
    STATE.mails = d.mails || [];
  } catch (_) { return; }
  if (STATE.tab === "inbox") renderList();
}

async function loadOutbox() {
  try {
    const d = await api("/api/outbox");
    STATE.outbox = d.outbox || [];
  } catch (_) { return; }
  if (STATE.tab === "outbox") renderList();
}

function visibleItems() {
  if (STATE.tab === "outbox") {
    return STATE.outbox.filter((m) => {
      if (!STATE.query) return true;
      const q = STATE.query.toLowerCase();
      return (m.subject || "").toLowerCase().includes(q) || (m.body || "").toLowerCase().includes(q) || (m.to || "").toLowerCase().includes(q);
    });
  }
  return STATE.mails.filter((m) => {
    if (!STATE.query) return true;
    const q = STATE.query.toLowerCase();
    return (m.subject || "").toLowerCase().includes(q) || (m.body || "").toLowerCase().includes(q) || (m.from || "").toLowerCase().includes(q);
  });
}

/* ── рендер списка ───────────────────────────────────── */
function renderList() {
  const list = $("mail-list");
  const emptyInbox = $("empty-inbox");
  const emptySearch = $("empty-search");
  const isOutbox = STATE.tab === "outbox";

  /* бейдж непрочитанных — только для входящих */
  const unread = STATE.mails.filter((m) => !m.is_read).length;
  $("inbox-count").textContent = unread;
  $("inbox-count").hidden = !unread;

  const items = visibleItems();
  emptySearch.hidden = true;
  emptyInbox.hidden = true;
  if (!items.length) {
    list.innerHTML = "";
    if (STATE.query) emptySearch.hidden = false;
    else if (!isOutbox) emptyInbox.hidden = false;
    else {
      emptyInbox.querySelector("p").innerHTML = "Пока ничего не отправлено.<br>Напишите первое письмо Крайтеру!";
      emptyInbox.hidden = false;
    }
    return;
  }

  list.innerHTML = "";
  const frag = document.createDocumentFragment();
  items.forEach((m, i) => {
    const el = document.createElement("div");
    const isUnread = isOutbox ? false : !m.is_read;
    el.className = "mail-item" + (isUnread ? " unread" : "");
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
    el.style.transitionDelay = Math.min(i * 45, 400) + "ms";
    const who = isOutbox ? (m.to || "—") : (m.from || "—");
    const when = isOutbox ? m.sent_at : m.received_at;
    el.innerHTML =
      `<div class="mail-item-top">
         <span class="mail-item-from">${esc(shortNpub(who))}${isUnread ? '<span class="unread-dot" aria-hidden="true"></span>' : ""}</span>
         <span class="mail-item-date">${fmtAgo(when)}</span>
       </div>
       <div class="mail-item-subject">${esc(m.subject || "(без темы)")}</div>`;
    el.addEventListener("click", () => openMail(m.id, isOutbox));
    frag.appendChild(el);
  });
  list.appendChild(frag);

  requestAnimationFrame(() => {
    list.querySelectorAll(".mail-item").forEach((el, i) => {
      el.style.transition =
        "opacity 240ms var(--ease-out), transform 240ms var(--ease-out)";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    });
  });
}

/* ── открытие письма ─────────────────────────────────── */
async function openMail(id, isOutbox = false) {
  if (isOutbox) {
    const m = STATE.outbox.find((x) => x.id === id);
    if (!m) return;
    STATE.current = { ...m, isOutbox: true, is_read: true, to: m.to };
    $("list-view").hidden = true;
    $("detail-view").hidden = false;
    renderDetail();
    return;
  }
  const d = await api("/api/mails/" + id);
  if (!d.ok) return;
  STATE.current = d.mail;
  $("list-view").hidden = true;
  $("detail-view").hidden = false;
  renderDetail();
  /* обновить статус в списке (письмо прочитано) */
  const item = STATE.mails.find((m) => m.id === id);
  if (item) item.is_read = true;
  $("inbox-count").textContent = STATE.mails.filter((m) => !m.is_read).length;
  $("inbox-count").hidden = !$("inbox-count").textContent;
}

function renderDetail() {
  const m = STATE.current;
  const card = $("mail-card");
  card.style.opacity = "0";
  card.style.transform = "translateY(10px)";
  const who = m.isOutbox ? (m.to || "—") : (m.from || "—");
  const when = m.isOutbox ? fmtDate(m.sent_at) : fmtDate(m.received_at);
  card.innerHTML =
    `<div class="mail-card-head">
       <div class="mail-avatar">${esc((m.isOutbox ? "→" : (m.from || "?"))[0].toUpperCase())}</div>
       <div class="mail-card-meta">
         <h2>${esc(m.subject || "(без темы)")}</h2>
         <div class="mail-meta">
           <div><b>${m.isOutbox ? "Кому:" : "От:"}</b> <span class="mono">${esc(who)}</span></div>
           ${m.isOutbox ? "" : `<div><b>Кому:</b> <span class="mono">${esc(m.to || "—")}</span></div>`}
           <div><b>Когда:</b> ${when}</div>
         </div>
       </div>
     </div>
     <div class="mail-body">${esc(m.body)}</div>`;
  requestAnimationFrame(() => {
    card.style.transition = "opacity 240ms var(--ease-out), transform 240ms var(--ease-out)";
    card.style.opacity = "1";
    card.style.transform = "translateY(0)";
  });
  $("btn-unread").textContent = m.isOutbox ? "" : (m.is_read ? "Не прочитано" : "Прочитано");
  $("btn-unread").hidden = !!m.isOutbox;
}

/* ── композер ────────────────────────────────────────── */
function openComposer(title, to = "", subject = "", replyTo = "") {
  $("compose-title").textContent = title;
  $("compose-to").value = to;
  $("compose-subject").value = subject;
  $("compose-body").value = "";
  $("compose-form").dataset.replyTo = replyTo || "";
  $("compose-error").hidden = true;
  const bd = $("compose-backdrop");
  const form = $("compose-form");
  form.classList.remove("compose-in");
  bd.hidden = false;
  bd.style.opacity = "0";
  requestAnimationFrame(() => {
    bd.style.transition = "opacity 180ms var(--ease-out)";
    bd.style.opacity = "1";
    form.classList.add("compose-in");
  });
  setTimeout(() => $("compose-to").focus(), 120);
}

function closeComposer() {
  $("compose-backdrop").hidden = true;
}

/* ── отправка ────────────────────────────────────────── */
async function sendMail(ev) {
  ev.preventDefault();
  const btn = $("btn-send");
  const to = $("compose-to").value.trim();
  const subject = $("compose-subject").value.trim();
  const body = $("compose-body").value.trim();
  const err = $("compose-error");

  /* валидация */
  if (!to) { err.textContent = "Укажите адресата (npub или npub@домен)"; err.hidden = false; $("compose-to").focus(); return; }
  if (!/^(npub1[a-z0-9]{58,62})(@[^\s@]+)?$/i.test(to)) { err.textContent = "Адрес должен быть npub1… (или npub1…@домен)"; err.hidden = false; $("compose-to").focus(); return; }
  if (!subject) { err.textContent = "Укажите тему письма"; err.hidden = false; $("compose-subject").focus(); return; }
  if (!body) { err.textContent = "Напишите текст письма"; err.hidden = false; $("compose-body").focus(); return; }

  btn.disabled = true;
  btn.textContent = "Отправка…";
  err.hidden = true;
  try {
    const r = await api("/api/send", {
      method: "POST",
      body: JSON.stringify({ to_npub: to, subject, body, in_reply_to: $("compose-form").dataset.replyTo || "" }),
    });
    if (!r.ok) throw new Error(r.error || "ошибка");
    closeComposer();
    showToast(r.published ? `Отправлено на ${r.published} релеев ✅` : "Письмо записано в исходящие ✅");
    STATE.tab = "outbox";
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === "outbox"));
    await loadOutbox();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Отправить";
  }
}

/* ── удаление (2 клика) ──────────────────────────────── */
async function deleteMail() {
  const btn = $("btn-delete");
  const now = Date.now();
  if (now - STATE.deleteArm > 3000) {
    STATE.deleteArm = now;
    btn.textContent = "Точно удалить?";
    btn.classList.add("armed");
    showToast("Нажмите ещё раз для подтверждения", "warn");
    setTimeout(() => { btn.textContent = "Удалить"; btn.classList.remove("armed"); }, 3000);
    return;
  }
  const r = await api("/api/mails/" + STATE.current.id, { method: "DELETE" });
  STATE.deleteArm = 0;
  btn.textContent = "Удалить";
  btn.classList.remove("armed");
  if (!r.ok) { showToast(r.error || "Ошибка удаления", "err"); return; }
  STATE.mails = STATE.mails.filter((m) => m.id !== STATE.current.id);
  showToast("Письмо удалено");
  backToList();
}

/* ── прочитано/непрочитано ───────────────────────────── */
async function toggleRead() {
  const m = STATE.current;
  if (!m || m.isOutbox) return;
  const target = !m.is_read;
  const r = await api(`/api/mails/${m.id}/read`, { method: "POST", body: JSON.stringify({ read: target }) });
  if (!r.ok) { showToast(r.error || "Ошибка", "err"); return; }
  m.is_read = target;
  $("btn-unread").textContent = target ? "Не прочитано" : "Прочитано";
  const item = STATE.mails.find((x) => x.id === m.id);
  if (item) item.is_read = target;
  showToast(target ? "Отмечено прочитанным" : "Отмечено непрочитанным");
  renderList();
}

/* ── назад ───────────────────────────────────────────── */
function backToList() {
  $("detail-view").hidden = true;
  $("list-view").hidden = false;
  STATE.current = null;
  STATE.deleteArm = 0;
  const btn = $("btn-delete");
  btn.textContent = "Удалить";
  btn.classList.remove("armed");
  renderList();
}

/* ── копирование адреса ──────────────────────────────── */
async function copyAddress() {
  const addr = $("mail-address").textContent;
  if (!addr || addr === "—") return;
  try {
    await navigator.clipboard.writeText(addr);
    showToast("Адрес скопирован 📋");
  } catch (_) {
    showToast(addr, "ok");
  }
}

/* ── авто-обновление ─────────────────────────────────── */
function startRefresh() {
  stopRefresh();
  STATE.refreshTimer = setInterval(() => {
    if (document.hidden) return;
    if (STATE.tab === "inbox" && $("list-view").hidden === false) loadMails();
  }, 30000);
}
function stopRefresh() {
  if (STATE.refreshTimer) { clearInterval(STATE.refreshTimer); STATE.refreshTimer = null; }
}

/* ── события ─────────────────────────────────────────── */
$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const r = await api("/api/login", { method: "POST", body: JSON.stringify({ password: $("login-pass").value }) });
  if (r.ok) {
    $("login-pass").value = "";
    $("login-error").hidden = true;
    await loadStatus();
    await loadMails();
  } else {
    $("login-error").textContent = "Неверный пароль";
    $("login-error").hidden = false;
    $("login-pass").select();
  }
});

$("btn-logout").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" }).catch(() => {});
  location.reload();
});

$("btn-compose").addEventListener("click", () => openComposer("Новое письмо"));
$("btn-close").addEventListener("click", closeComposer);
$("btn-cancel").addEventListener("click", closeComposer);
$("compose-backdrop").addEventListener("click", (ev) => {
  if (ev.target === $("compose-backdrop")) closeComposer();
});
$("compose-form").addEventListener("submit", sendMail);

$("btn-reply").addEventListener("click", () => {
  if (!STATE.current) return;
  const m = STATE.current;
  const to = m.isOutbox ? "" : m.from;
  const subject = (m.subject || "").startsWith("Re:") ? m.subject : "Re: " + (m.subject || "");
  openComposer("Ответ", to || "", subject, m.isOutbox ? "" : m.message_id);
});

$("btn-back").addEventListener("click", backToList);
$("btn-delete").addEventListener("click", deleteMail);
$("btn-unread").addEventListener("click", toggleRead);
$("mail-address").addEventListener("click", copyAddress);

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && !$("compose-backdrop").hidden) closeComposer();
});

$("search").addEventListener("input", () => {
  STATE.query = $("search").value.trim();
  renderList();
});

document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", async () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    STATE.tab = t.dataset.tab;
    $("search").value = "";
    STATE.query = "";
    if (STATE.tab === "outbox") await loadOutbox();
    else await loadMails();
  });
});

/* ── старт ── */
(async () => {
  await loadStatus();
  if (!$("main-view").hidden) await loadMails();
})();
