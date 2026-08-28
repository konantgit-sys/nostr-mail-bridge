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

/* Аватар: инициал + стабильный цвет по ключу (hash → hue). */
Mail.avatarOf = function (addr) {
  const key = (addr || "").split("@")[0] || "?";
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  const ch = (addr && addr[0] === "n") ? key[5] || "N" : (key[0] || "?").toUpperCase();
  return { ch, bg: `linear-gradient(135deg, hsl(${hue} 72% 58%), hsl(${(hue + 40) % 360} 72% 44%))` };
};
