"""Конфигурация Nostr Mail: загрузка config.json, константы.

Модуль не имеет зависимостей от FastAPI/моста — импортируется где угодно.
"""
from __future__ import annotations

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE, "config.json")

with open(CONFIG_PATH) as f:
    CFG = json.load(f)

NSEC = CFG["nsec_hex"]
PUBKEY = CFG["pubkey_hex"]
NPUB = CFG["npub"]
MAIL_ADDR = CFG["mail_address"]
DOMAIN = CFG["mail_domain"]
DB = CFG["db"]
RELAYS = CFG["relays"]
LIGHTNING = CFG.get("lightning", "")
AUTH_PASSWORD = CFG.get("auth_password", "cryter-mail")
SESSIONS_FILE = os.path.join(BASE, ".sessions.json")
SESSIONS_TTL = 86400 * 7  # 7 дней

STATIC_DIR = os.path.join(BASE, "static")
