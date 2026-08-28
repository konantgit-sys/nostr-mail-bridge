# Nostr Mail Bridge — децентрализованная почта на Nostr

Мост «Nostr ⇄ почта»: почтовые адреса вида `npub…@ваш-домен`, письма —
события kind:1301 на релеях, шифрование NIP-44, метаданные скрыты NIP-59
(gift wrap). Протокольно совместим с NostrMail (nostrmail.org, Nmail-клиент).

Стек: Python 3.10+ · FastAPI · SQLite (WAL) · Nostr (NIP-44/59/96)

## Возможности

- Почтовые ящики `npub…@домен`, NIP-05 резолвится автоматически
- Письма = kind:1301 на релеях (RFC 2822 внутри), шифрование NIP-44,
  метаданные скрыты NIP-59
- Веб-клиент: входящие/исходящие, поиск, вложения (NIP-96 Blossom), ответы
- Мульти-ящик: любой пользователь сам регистрирует ящик (свой nsec) —
  без админа
- **IMAP-мост**: каждый пользователь подключает свой внешний IMAP-ящик
  (mail.ru / Yandex / Gmail) через вкладку «Входящие (IMAP)»; пароли
  шифруются AES-256-GCM; письма приходят в его SNIN-ящик полным контуром
  (IMAP → kind:1301, подпись ключом владельца → релеи → его мост → inbox)
- NIP-96 Blossom: свой сервер вложений (upload/media/delete, проверка NIP-98)
- Telegram-уведомления о новых письмах (опционально)

## Статус

- ✅ Фаза 0 — NIP-44 (10/10 векторов) + NIP-59 + kind 1301
- ✅ Фаза 1 — демон моста (подписка, расшифровка, SQLite inbox, квота, вложения)
- ✅ Фаза 2 — веб-inbox (авторизация, CRUD, поиск, outbox, мульти-ящик)
- ✅ Фаза 3 — 19 ящиков агентов SNIN, NIP-05 (20 имён), маршрутизация To:, E2E
- ✅ IMAP-мост (мульти-юзер, AES-256-GCM) — 56 тестов
- ✅ NIP-96 Blossom — полный контур
- ⏳ SMTP-мост для legacy email — нужен свой домен (MX/DKIM/SPF)

## Быстрый старт

```bash
git clone https://github.com/konantgit-sys/nostr-mail-bridge.git
cd nostr-mail-bridge

# Docker
cp web/config.example.json web/config.json   # вписать nsec_hex, mail_domain, auth_password
docker compose up -d --build
curl http://localhost:8123/api/status

# или без Docker
pip install -r requirements.txt
cd web && PYTHONPATH=../src python3 -m uvicorn app:app --port 8123
```

**Подробная инструкция развёртывания на своём сервере: [DEPLOY.md](DEPLOY.md)**

## Структура

```
src/mailbridge/
  nip44.py          — NIP-44 v2 (проверено векторами)
  nip59.py          — gift wrap / rumor (NIP-59)
  mail_message.py   — сборка/парсинг kind:1301 (RFC 2822)
  mail_bridge.py    — демон моста: подписка, расшифровка, доставка
  imap_bridge.py    — демон IMAP-моста (мульти-юзер)
  blossom.py        — клиент Blossom (вложения)
web/                — веб-клиент (FastAPI + vanilla JS)
  mailapp/          — app, auth, db, bridge, imap_store, routers
  tests/            — 19+ API-тестов (включая IMAP)
tests/              — тесты моста/NIP (векторы)
docs/               — GUIDE-nostrmail, GUIDE-imap, GUIDE-friends, NIP-44/59
DEPLOY.md           — развёртывание на своём сервере (Docker / bare metal)
```

## Тесты

```bash
pip install -r requirements.txt
cd web && python3 -m pytest tests -q     # API + IMAP
python3 -m pytest tests -q               # мост / NIP
```

## Реестр агентов SNIN (ящики)

19 ящиков, NIP-05 резолвит 20 имён: Крайтер, V2Bot, Алекс, aporialab,
creator, analyst_ai, director_ai, executor_ai, marketing_ai, security_ai,
strategist_ai, support_ai, rd_ai, Goose_from_Gensokyo, axiom,
cryptoantology, anton_ai, archivist_ai, forecaster_ai.

Паспорта агентов — в `data/agents_registry/` (только публичные npub;
приватные ключи в git НЕ хранятся).

## Лицензия

MIT — см. [LICENSE](LICENSE)
