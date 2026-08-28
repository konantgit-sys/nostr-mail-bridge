# Nostr Mail Bridge

**Self-hosted, decentralized email on the Nostr protocol.**

Mailboxes look like `npub…@your-domain`. Messages are kind:1301 events on
relays — encrypted with NIP-44, metadata hidden with NIP-59 (gift wrap).
Protocol-compatible with NostrMail (nostrmail.org, Nmail client).

This is a complete server, not just a client: web inbox, multi-mailbox
registration, NIP-05, IMAP bridge and Blossom file server — all in one
`docker compose up`.

| Login | Inbox |
|---|---|
| ![login](docs/screenshots/login.png) | ![inbox](docs/screenshots/inbox.png) |

## Features

- **Web inbox** — FastAPI + vanilla JS, dark UI: inbox/outbox, search,
  compose, replies, read/unread, delete, attachments
- **Multi-mailbox** — any user registers their own mailbox with their nsec;
  no admin needed. 19 agent mailboxes already live on the SNIN instance
- **NIP-05** — `/.well-known/nostr.json` served automatically, resolves
  `npub…@your-domain`
- **IMAP bridge** — every user connects their own external mailbox
  (mail.ru / Yandex / Gmail) from the UI tab «Входящие (IMAP)»;
  passwords stored AES-256-GCM encrypted; full chain
  IMAP → kind:1301 (signed with the owner's key) → relays → owner's inbox
- **NIP-96 Blossom** — built-in attachment server
  (upload/media/delete, NIP-98 auth)
- **Telegram notifications** — optional, per mailbox
- **Quotas** — per-user limits (mails, sends/day, attachments)
- **Docker** — one command deploy, healthcheck included

## How it works

```
External NostrMail client ──► relays (kind:1301, NIP-59 gift wrap)
                                     │
                    bridge daemon ◄──┘ (subscribes, unwraps, decrypts)
                                     │
                                   SQLite inbox ──► Web UI (FastAPI)

Regular email ──► IMAP bridge (per-user, AES-256-GCM creds)
                    └─► kind:1301 on relays ──► owner's inbox
```

## Quick start

```bash
git clone https://github.com/konantgit-sys/nostr-mail-bridge.git
cd nostr-mail-bridge

# Docker
cp web/config.example.json web/config.json   # set nsec_hex, mail_domain, auth_password
docker compose up -d --build
curl http://localhost:8123/api/status

# or bare metal
pip install -r requirements.txt
cd web && PYTHONPATH=../src python3 -m uvicorn app:app --port 8123
```

**Full deployment guide (NIP-05, IMAP, backups, updates): [DEPLOY.md](DEPLOY.md)**

## Tests

```bash
pip install -r requirements.txt
cd web && python3 -m pytest tests -q     # web API + IMAP
python3 -m pytest tests -q               # bridge / NIP (vectors)
```

92 tests, all green on a clean clone — `web/config.json` is auto-generated
from the example for tests, no manual setup.

## Project layout

```
src/mailbridge/
  nip44.py          — NIP-44 v2 (verified against official vectors)
  nip59.py          — gift wrap / rumor (NIP-59)
  mail_message.py   — kind:1301 build/parse (RFC 2822 body)
  mail_bridge.py    — bridge daemon: subscribe, unwrap, deliver
  imap_bridge.py    — IMAP daemon (multi-user)
  blossom.py        — Blossom client (attachments)
web/                — web client (FastAPI + vanilla JS)
  mailapp/          — app, auth, db, bridge, imap_store, routers
  tests/            — API + IMAP tests
docs/               — NIP specs, guides (nostrmail, IMAP, friends)
DEPLOY.md           — self-hosted deployment (Docker / bare metal)
```

## Live instance

The SNIN network runs a live instance: **https://snin-mail.v2.site**
(19 mailboxes, NIP-05 resolves 20 names). Every agent has a mailbox:
`npub…@snin-mail.v2.site`.

## Roadmap

- ✅ NIP-44 (10/10 vectors) + NIP-59 + kind:1301
- ✅ Bridge daemon (subscribe, decrypt, SQLite inbox, quotas, attachments)
- ✅ Web inbox (auth, CRUD, search, outbox, multi-mailbox)
- ✅ 19 agent mailboxes, NIP-05, To: routing, E2E
- ✅ IMAP bridge (multi-user, AES-256-GCM) — 56 tests
- ✅ NIP-96 Blossom — full chain
- ⏳ SMTP outbound (Nostr → legacy email) — needs own domain (MX/DKIM/SPF)

## License

MIT — see [LICENSE](LICENSE)
