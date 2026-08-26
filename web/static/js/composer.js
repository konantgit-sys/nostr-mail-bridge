/* Mail.composer — открытие/закрытие композера, валидация, отправка. */
"use strict";

Mail.openComposer = function (title, to = "", subject = "", replyTo = "") {
  Mail.$("compose-title").textContent = title;
  Mail.$("compose-to").value = to;
  Mail.$("compose-subject").value = subject;
  Mail.$("compose-body").value = "";
  Mail.$("compose-form").dataset.replyTo = replyTo || "";
  Mail.$("compose-error").hidden = true;
  const bd = Mail.$("compose-backdrop");
  const form = Mail.$("compose-form");
  form.classList.remove("compose-in");
  bd.hidden = false;
  bd.style.opacity = "0";
  requestAnimationFrame(() => {
    bd.style.transition = "opacity 180ms var(--ease-out)";
    bd.style.opacity = "1";
    form.classList.add("compose-in");
  });
  setTimeout(() => Mail.$("compose-to").focus(), 120);
};

Mail.closeComposer = function () {
  Mail.$("compose-backdrop").hidden = true;
};

Mail.sendMail = async function (ev) {
  ev.preventDefault();
  const btn = Mail.$("btn-send");
  const to = Mail.$("compose-to").value.trim();
  const subject = Mail.$("compose-subject").value.trim();
  const body = Mail.$("compose-body").value.trim();
  const err = Mail.$("compose-error");

  /* валидация */
  if (!to) { err.textContent = "Укажите адресата (npub или npub@домен)"; err.hidden = false; Mail.$("compose-to").focus(); return; }
  if (!/^(npub1[a-z0-9]{58,62})(@[^\s@]+)?$/i.test(to)) { err.textContent = "Адрес должен быть npub1… (или npub1…@домен)"; err.hidden = false; Mail.$("compose-to").focus(); return; }
  if (!subject) { err.textContent = "Укажите тему письма"; err.hidden = false; Mail.$("compose-subject").focus(); return; }
  if (!body) { err.textContent = "Напишите текст письма"; err.hidden = false; Mail.$("compose-body").focus(); return; }

  btn.disabled = true;
  btn.textContent = "Отправка…";
  err.hidden = true;
  try {
    const r = await Mail.api("/api/send", {
      method: "POST",
      body: JSON.stringify({ to_npub: to, subject, body, in_reply_to: Mail.$("compose-form").dataset.replyTo || "" }),
    });
    if (!r.ok) throw new Error(r.error || "ошибка");
    Mail.closeComposer();
    Mail.showToast(r.published ? `Отправлено на ${r.published} релеев ✅` : "Письмо записано в исходящие ✅");
    await Mail.switchTab("outbox");
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Отправить";
  }
};

Mail.replyTo = function () {
  if (!Mail.STATE.current) return;
  const m = Mail.STATE.current;
  const to = m.isOutbox ? "" : m.from;
  const subject = (m.subject || "").startsWith("Re:") ? m.subject : "Re: " + (m.subject || "");
  Mail.openComposer("Ответ", to || "", subject, m.isOutbox ? "" : m.message_id);
};
