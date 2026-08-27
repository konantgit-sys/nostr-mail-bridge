# Nostr Mail Bridge — децентрализованная почта для наших агентов

Мост «Nostr ⇄ почта»: почтовые адреса вида `npub…@cryter-mail.v2.site`,
письма = события kind:1301 на релеях, шифрование NIP-44, метаданные скрыты NIP-59 (gift wrap).

Протокол: https://nostrmail.org (NostrMail / kind 1301 / Nmail-клиент)

## Статус

- ✅ **Фаза 0 — NIP-44 (10/10 векторов) + NIP-59 gift wrap + kind 1301 (RFC 2822)**
- ✅ **Фаза 1 — демон mail_bridge.py** (подписка 1059/1301, расшифровка, SQLite inbox, Telegram-уведомления, квота 500, вложения)
- ✅ **Фаза 2 — веб-inbox** (авторизация, CRUD, поиск, outbox, мульти-ящик, E2E-контур)
- ⏳ Фаза 3 — адреса агентам + «раструбить» + вкладка на дашборде
- ⏳ Фаза 4 (опц.) — SMTP-мост для legacy email

## Структура

```
src/mailbridge/
  nip44.py       — NIP-44 v2 (готово, проверено векторами)
  giftwrap.py    — NIP-59 (следующий шаг)
  rfc2822.py     — парсинг писем (Фаза 1)
  relay.py       — подписка на релеи (Фаза 1)
  bridge.py      — демон (Фаза 1)
  store.py       — SQLite inbox (Фаза 1)
tests/           — pytest, векторы из docs/nip44.vectors.json
docs/            — спеки NIP-44/NIP-59 + векторы
scripts/         — mail_ctl.sh (start/stop/status)
data/            — SQLite, ключи (gitignored)
```

## Тесты

```bash
python3 tests/test_nip44.py          # быстрый прогон
python3 -m pytest tests/ -q          # через pytest
```

## Ключевые решения

- Лимит письма **64KB** (как официальные клиенты: maxPlaintextSize 0xffff) —
  extended 6-байтовый префикс в спеке есть, но Nmail/nostr-tools его не принимают
- ECDH unhashed через `tweak_mul` (пакет secp256k1 не умеет unhashed ecdh)
- X-only pubkey парсится lift-x (0x02/0x03)
