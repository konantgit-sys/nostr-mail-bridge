/* Mail.inbox — загрузка и рендер списка (входящие/исходящие), поиск, вкладки. */
"use strict";

Mail.loadMails = async function () {
  try {
    const d = await Mail.api("/api/mails?owner=" + encodeURIComponent(Mail.STATE.owner || ""));
    Mail.STATE.mails = d.mails || [];
  } catch (_) { return; }
  if (Mail.STATE.tab === "inbox") Mail.renderList();
};

Mail.loadOutbox = async function () {
  try {
    const d = await Mail.api("/api/outbox?owner=" + encodeURIComponent(Mail.STATE.owner || ""));
    Mail.STATE.outbox = d.outbox || [];
  } catch (_) { return; }
  if (Mail.STATE.tab === "outbox") Mail.renderList();
};

Mail.visibleItems = function () {
  if (Mail.STATE.tab === "outbox") {
    return Mail.STATE.outbox.filter((m) => {
      if (!Mail.STATE.query) return true;
      const q = Mail.STATE.query.toLowerCase();
      return (m.subject || "").toLowerCase().includes(q) || (m.body || "").toLowerCase().includes(q) || (m.to || "").toLowerCase().includes(q);
    });
  }
  return Mail.STATE.mails.filter((m) => {
    if (!Mail.STATE.query) return true;
    const q = Mail.STATE.query.toLowerCase();
    return (m.subject || "").toLowerCase().includes(q) || (m.body || "").toLowerCase().includes(q) || (m.from || "").toLowerCase().includes(q);
  });
};

Mail.renderList = function () {
  const list = Mail.$("mail-list");
  const emptyInbox = Mail.$("empty-inbox");
  const emptySearch = Mail.$("empty-search");
  const isOutbox = Mail.STATE.tab === "outbox";

  const unread = Mail.STATE.mails.filter((m) => !m.is_read).length;
  Mail.$("inbox-count").textContent = unread;
  Mail.$("inbox-count").hidden = !unread;

  const items = Mail.visibleItems();
  emptySearch.hidden = true;
  emptyInbox.hidden = true;
  if (!items.length) {
    list.innerHTML = "";
    if (Mail.STATE.query) emptySearch.hidden = false;
    else if (!isOutbox) emptyInbox.hidden = false;
    else {
      emptyInbox.querySelector("p").innerHTML = "Пока ничего не отправлено.<br>Напишите первое письмо!";
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
    const av = Mail.avatarOf(who);
    el.innerHTML =
      `<div class="avatar" style="background:${av.bg}" aria-hidden="true">${av.ch}</div>
       <div class="mail-item-main">
         <div class="mail-item-top">
           <span class="mail-item-from">${Mail.esc(Mail.shortNpub(who))}${isUnread ? '<span class="unread-dot" aria-hidden="true"></span>' : ""}</span>
           <span class="mail-item-date">${Mail.fmtAgo(when)}</span>
         </div>
         <div class="mail-item-subject">${Mail.esc(m.subject || "(без темы)")}</div>
       </div>`;
    el.addEventListener("click", () => Mail.openMail(m.id, isOutbox));
    frag.appendChild(el);
  });
  list.appendChild(frag);

  requestAnimationFrame(() => {
    list.querySelectorAll(".mail-item").forEach((el) => {
      el.style.transition = "opacity 240ms var(--ease-out), transform 240ms var(--ease-out)";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    });
  });
};

/* вкладки */
Mail.switchTab = async function (tabName) {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === tabName));
  Mail.STATE.tab = tabName;
  Mail.$("search").value = "";
  Mail.STATE.query = "";
  if (tabName === "outbox") await Mail.loadOutbox();
  else await Mail.loadMails();
};
