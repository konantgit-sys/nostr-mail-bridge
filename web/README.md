# Nostr Mail — веб-клиент (исходники)

Веб-интерфейс поверх моста kind:1301 (NIP-44 + NIP-59).
FastAPI + vanilla JS, без зависимостей фронта (кроме FastAPI/uvicorn на бэке).

## Запуск
```bash
cp config.example.json config.json   # вписать nsec_hex (приватный ключ) и пароль
./start.sh                           # uvicorn app:app --port 8123
```

## API
- POST /api/login, POST /api/logout — сессии (cookie, persistent)
- GET  /api/status — адрес/npub/lightning/relays
- GET  /api/mails, GET /api/mails/{id} — входящие
- POST /api/mails/{id}/read — прочитано/нет
- DELETE /api/mails/{id} — удалить
- POST /api/send — отправить (gift wrap → релеи)
- GET  /api/outbox — исходящие
- GET  /.well-known/nostr.json — NIP-05 discovery (`_smtp`)

## Тесты
```bash
NO_BRIDGE=1 PYTHONPATH=../src:../deps python3 -m pytest tests/ -v
```
19 API-тестов: авторизация (в т.ч. регрессия «любая cookie больше не пускает»),
CRUD, валидация отправки, NIP-05.

v2 (2026-08-26): реальная авторизация, CRUD, поиск, авто-обновление 30с,
дизайн по emilkowalski/skills (easing, <300ms, :active scale, reduced-motion).
