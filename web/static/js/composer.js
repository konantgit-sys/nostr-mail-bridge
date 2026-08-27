/* Mail.composer — открытие/закрытие композера, валидация, отправка. */
"use strict";

Mail.openComposer = function (title, to = "", subject = "", replyTo = "", body = "") {
  Mail.$("compose-title").textContent = title;
  Mail.$("compose-to").value = to;
  Mail.$("compose-subject").value = subject;
  Mail.$("compose-body").value = "";
  Mail.$("compose-form").dataset.replyTo = replyTo || "";
  Mail.$("compose-body").value = body || "";
  Mail.$("compose-error").hidden = true;
  const bd = Mail.$("compose-backdrop");
  const form = Mail.$("compose-form");
  form.classList.remove("compose-in");
  bd.hidden = false;
  form.classList.add("compose-in");
  setTimeout(() => Mail.$("compose-to").focus(), 120);
};

Mail.closeComposer = function () {
  Mail.$("compose-backdrop").hidden = true;
  Mail.STATE.attach = [];
  renderAttachments();
};

/* ── вложения ─────────────────────────────────────────── */
Mail.STATE.attach = [];  // [{file, name, size, mime, dataUrl}]

function fmtSize(n) {
  if (n < 1024) return n + " Б";
  if (n < 1048576) return (n / 1024).toFixed(1) + " КБ";
  return (n / 1048576).toFixed(1) + " МБ";
}

function renderAttachments() {
  const box = Mail.$("compose-attachments");
  if (!Mail.STATE.attach.length) { box.innerHTML = ""; box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = Mail.STATE.attach.map((a, i) =>
    `<span class="attach-chip" data-i="${i}">
       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
       ${Mail.esc(a.name)} <span class="attach-size">${fmtSize(a.size)}</span>
       <button type="button" class="attach-remove" data-i="${i}" aria-label="Убрать">×</button>
     </span>`).join("");
  box.querySelectorAll(".attach-remove").forEach((b) =>
    b.addEventListener("click", () => {
      Mail.STATE.attach.splice(Number(b.dataset.i), 1);
      renderAttachments();
    })
  );
}

Mail.$("btn-attach").addEventListener("click", () => Mail.$("attach-input").click());
Mail.$("attach-input").addEventListener("change", (ev) => {
  const files = [...ev.target.files].slice(0, 5 - Mail.STATE.attach.length);
  const totalB64 = Mail.STATE.attach.reduce((s, a) => s + a.b64.length, 0);
  for (const f of files) {
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = String(reader.result).split(",")[1] || "";
      if (totalB64 + b64.length > 44000) { Mail.showToast("Вложения слишком большие (до ~33 КБ суммарно)"); return; }
      Mail.STATE.attach.push({ name: f.name, size: f.size, mime: f.type || "application/octet-stream", b64 });
      renderAttachments();
    };
    reader.readAsDataURL(f);
  }
  ev.target.value = "";
});

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
    const attachments = Mail.STATE.attach.map((a) => ({ filename: a.name, mime: a.mime, data_base64: a.b64 }));
    const r = await Mail.api("/api/send", {
      method: "POST",
      body: JSON.stringify({ to_npub: to, subject, body, in_reply_to: Mail.$("compose-form").dataset.replyTo || "", owner: Mail.STATE.owner || "", attachments }),
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
  // цитата оригинала в тело ответа
  const bodyLines = (m.body || "").split("\n").map((l) => "> " + l).join("\n");
  const quote = bodyLines ? "\n\n" + bodyLines + "\n" : "";
  Mail.openComposer("Ответ", to || "", subject, m.isOutbox ? "" : m.message_id, quote);
};
