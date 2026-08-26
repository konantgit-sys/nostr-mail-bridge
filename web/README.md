# Nostr Mail — веб-клиент (исходники)

Веб-интерфейс поверх моста kind:1301 (NIP-44 + NIP-59).
FastAPI + vanilla JS (модульная структура, без зависимостей фронта).

## Структура (модули)
```
app.py              — точка входа: uvicorn app:app
mailapp/
  __init__.py       — create_app(): роутеры, статика, Cache-Control middleware
  config.py         — конфиг (config.json), константы
  auth.py           — авторизация: токен-сессии, login/logout
  db.py             — SQLite: WAL, индексы, helpers
  bridge.py         — синглтон моста (фоновый поток, NO_BRIDGE=1 для тестов)
  routers/mail.py   — API: status/mails/send/outbox/NIP-05
static/
  index.html
  css/style.css     — дизайн по design-rules (easing, <300ms, reduced-motion)
  js/core.js        — namespace Mail, хелперы (DOM, время, toast)
  js/api.js         — транспорт, views, авто-обновление 30с
  js/inbox.js       — список писем, поиск, вкладки
  js/detail.js      — письмо, прочитано/нет, удаление
  js/composer.js    — композер, валидация, отправка
  js/main.js        — события, старт
tests/test_api.py   — 19 тестов (авторизация, CRUD, валидация, NIP-05)
```

## Запуск
```bash
cp config.example.json config.json   # вписать nsec_hex и пароль
./start.sh                           # uvicorn app:app --port 8123
```

## Тесты
```bash
NO_BRIDGE=1 PYTHONPATH=../src:../deps python3 -m pytest web/tests/ -v
```

## API
- POST /api/login, POST /api/logout — сессии (cookie, persistent, 7 дней)
- GET  /api/status — адрес/npub/lightning/relays
- GET  /api/mails, GET /api/mails/{id} — входящие (ключи: from/to, is_read: bool)
- POST /api/mails/{id}/read — прочитано/нет
- DELETE /api/mails/{id} — удалить
- POST /api/send — отправить (gift wrap → релеи)
- GET  /api/outbox — исходящие
- GET  /.well-known/nostr.json — NIP-05 discovery (`_smtp`)

## Важные решения (проверено на проде 2026-08-26)
- Ответы авторизации: 200 + {ok:false,error:"auth"} вместо 401 —
  внешний прокси *.v2.site конвертирует 401 в 502 (ломало фронт).
- GZip НЕ используется: прокси сам сжимает, двойное сжатие обрезает поток.
- WAL + индексы (received_at, is_read) — мост пишет, веб читает без блокировок.

## Версии
- v3 (2026-08-26): модульная структура (mailapp/ + js/*), оптимизация
  (WAL, индексы, Cache-Control), фикс авторизации через прокси,
  фикс алиасов полей (from/to) найденный полным контуром.
- v2 (2026-08-26): реальная авторизация (токен-сессии), CRUD, поиск,
  авто-обновление, дизайн по design-rules.
