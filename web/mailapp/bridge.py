"""Мост (MailBridge): синглтон в отдельном потоке.

Инициализируется в lifespan приложения (см. mailapp/__init__.py).
Роутеры получают инстанс через get_bridge() — при NO_BRIDGE=1 (тесты)
вернёт None, и publish() не выполнится.
"""
from __future__ import annotations

import os
import sys
import threading

from .config import BASE, CFG, DB, NSEC, RELAYS

_bridge = None
_lock = threading.Lock()


def init_bridge():
    """Стартует мост в фоновом потоке. NO_BRIDGE=1 — пропустить (тесты)."""
    global _bridge
    with _lock:
        if _bridge is not None or os.environ.get("NO_BRIDGE") == "1":
            return
        _setup_logging()
        sys.path.insert(0, os.path.join(BASE, "..", "..", "projects", "nostr-mail-bridge", "src"))
        from mailbridge.mail_bridge import MailBridge  # local import: тяжёлый

        b = MailBridge(
            privkey_hex=NSEC,
            relays=RELAYS,
            db_path=DB,
            telegram_token=CFG.get("telegram_token", ""),
            telegram_chat_id=CFG.get("telegram_chat_id", ""),
        )
        _bridge = b
        t = threading.Thread(target=b.start, daemon=True)
        t.start()


def _setup_logging():
    """Логи моста в веб-режиме: mailbridge → INFO → stdout (backend.log).
    Раньше basicConfig был только в CLI main() — в веб-режиме логи терялись."""
    import logging

    logger = logging.getLogger("mailbridge")
    if logger.handlers:  # уже настроен
        return
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(h)
    logger.propagate = False


def get_bridge():
    return _bridge
