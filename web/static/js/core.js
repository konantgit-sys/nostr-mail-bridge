/* Mail.core — namespace, хелперы: DOM, время, экранирование, тосты. */
"use strict";
window.Mail = window.Mail || {};

Mail.$ = (id) => document.getElementById(id);

Mail.esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

Mail.fmtDate = (ts) => {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

Mail.fmtAgo = (ts) => {
  if (!ts) return "";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return "только что";
  if (diff < 3600) return Math.floor(diff / 60) + " мин назад";
  if (diff < 86400) return Math.floor(diff / 3600) + " ч назад";
  if (diff < 172800) return "вчера";
  return new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" });
};

Mail.shortNpub = (npub) => {
  if (!npub) return "";
  return npub.length > 16 ? npub.slice(0, 10) + "…" + npub.slice(-6) : npub;
};

/* ── toast ─────────────────────────────────────────── */
let toastTimer = null;
Mail.showToast = (msg, kind = "ok") => {
  const t = Mail.$("toast");
  t.textContent = msg;
  t.dataset.kind = kind;
  t.classList.remove("toast-visible");
  void t.offsetWidth; /* рестарт анимации */
  t.classList.add("toast-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("toast-visible"), 2800);
};
