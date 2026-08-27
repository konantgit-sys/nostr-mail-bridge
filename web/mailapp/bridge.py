"""Мосты (MailBridge): ОДИН общий подписчик на ВСЕ ящики.

Архитектура v2 (2026-08-27):
- Раньше: по потоку на каждый ящик × релей = 3 ящика × 3 релея = 9 соединений.
- Теперь: мосты создаются для КАЖДОГО владельца (нужны для расшифровки своим
  ключом, квот и уведомлений), но БЕЗ собственных потоков. Подписку ведёт один
  общий SharedSubscriber: поток на релей (3 потока на все ящики), filter #p =
  [все pubkey владельцев]. Событие передаётся каждому мосту — расшифрует тот,
  чей ключ подходит, и сохранит письмо со своим owner.

Все мосты пишут в общую БД (inbox.db), письма помечаются owner (pubkey владельца).
NO_BRIDGE=1 (тесты) — мосты не стартуют, get_bridge() вернёт None.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading

from .config import BASE, CFG, DB, OWNERS, RELAYS, LIMITS

_bridges: dict[str, object] = {}
_subscriber = None
_lock = threading.Lock()


def _build_bridge(o: dict):
    """Создаёт MailBridge для владельца без запуска потоков (только обработка)."""
    from mailbridge.mail_bridge import MailBridge  # local import: тяжёлый
    nsec = _nsec_for(o)
    if not nsec:
        return None
    return MailBridge(
        privkey_hex=nsec,
        relays=RELAYS,
        db_path=DB,
        telegram_token=CFG.get("telegram_token", ""),
        telegram_chat_id=CFG.get("telegram_chat_id", ""),
        owner=o["pubkey_hex"],
        label=o["label"],
        max_inbox=LIMITS["max_mails_per_user"],
    )


class SharedSubscriber:
    """Один общий подписчик на все pubkey владельцев. Поток на релей."""

    def __init__(self, bridges: list, relays: list):
        self.bridges = bridges            # list[MailBridge] (без своих потоков)
        self.relays = relays
        self._stop = threading.Event()
        self._ws_list: list = []
        self._ws_lock = threading.Lock()
        self._subid = "mb-shared-1"

    def _pubkeys(self) -> list:
        return [b.pubkey for b in self.bridges]

    def start(self):
        for url in self.relays:
            threading.Thread(target=self._run_relay, args=(url,), daemon=True).start()
        logging.getLogger("mailbridge").info(
            "общий подписчик: %d владельцев × %d релеев (1 поток на релей)", len(self.bridges), len(self.relays))

    def stop(self):
        self._stop.set()
        for ws in list(self._ws_list):
            try:
                ws.close()
            except Exception:
                pass

    def add_bridge(self, b) -> None:
        """Новый владелец: добавляем в общий список и пере-подписываемся."""
        self.bridges.append(b)
        self._resubscribe()

    def _resubscribe(self):
        """CLOSE старой подписки + REQ с обновлённым #p на каждом живом ws."""
        filter_ = {"kinds": [1059, 1301], "#p": self._pubkeys(), "limit": 100}
        with self._ws_lock:
            for ws in list(self._ws_list):
                try:
                    ws.send(json.dumps(["CLOSE", self._subid]))
                    ws.send(json.dumps(["REQ", self._subid, filter_]))
                except Exception:
                    pass

    def _run_relay(self, url: str):
        import websocket
        while not self._stop.is_set():
            try:
                def on_open(ws):
                    with self._ws_lock:
                        if ws not in self._ws_list:
                            self._ws_list.append(ws)
                    filter_ = {"kinds": [1059, 1301], "#p": self._pubkeys(), "limit": 100}
                    ws.send(json.dumps(["REQ", self._subid, filter_]))

                def on_message(ws, message):
                    try:
                        arr = json.loads(message)
                    except Exception:
                        return
                    if not isinstance(arr, list) or not arr:
                        return
                    if arr[0] == "EVENT":
                        ev = arr[1] if len(arr) == 2 else arr[2]
                        if isinstance(ev, str):
                            try:
                                ev = json.loads(ev)
                            except Exception:
                                return
                        if isinstance(ev, dict):
                            self._dispatch(ev)
                    elif arr[0] == "EOSE":
                        pass  # история загружена, дальше — стрим

                ws = websocket.WebSocketApp(
                    url,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=lambda ws, err: logging.getLogger("mailbridge").debug("%s error: %s", url, err),
                    on_close=lambda ws, *a: self._forget(ws),
                )
                ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logging.getLogger("mailbridge").debug("%s crashed: %s", url, e)
            finally:
                self._forget(ws)
            if not self._stop.is_set():
                logging.getLogger("mailbridge").info("реконнект %s через 5с", url)
                self._stop.wait(5)

    def _forget(self, ws):
        with self._ws_lock:
            try:
                if ws in self._ws_list:
                    self._ws_list.remove(ws)
            except Exception:
                pass

    def _dispatch(self, ev: dict):
        """Передаёт событие каждому мосту: расшифрует тот, чей ключ подходит."""
        for b in list(self.bridges):
            try:
                if b.handle_event(ev):
                    return  # письмо принято — событие больше не нужно
            except Exception as e:
                logging.getLogger("mailbridge").debug("dispatch: %s", e)


def init_bridge():
    """Стартует ОДИН общий подписчик на все ящики. NO_BRIDGE=1 — пропустить (тесты)."""
    global _bridges, _subscriber
    with _lock:
        if _bridges or os.environ.get("NO_BRIDGE") == "1":
            return
        _setup_logging()
        sys.path.insert(0, os.path.join(BASE, "..", "..", "projects", "nostr-mail-bridge", "src"))

        bridges = []
        for o in OWNERS:
            b = _build_bridge(o)
            if b is None:
                continue
            _bridges[o["pubkey_hex"]] = b
            bridges.append(b)

        # старые письма (до мульти-ящика) — первому владельцу
        try:
            import sqlite3
            with sqlite3.connect(DB, timeout=15) as conn:
                conn.execute("UPDATE inbox SET owner=? WHERE owner=''", (OWNERS[0]["pubkey_hex"],))
                conn.commit()
        except Exception:
            pass

        if not bridges:
            return
        _subscriber = SharedSubscriber(bridges, RELAYS)
        _subscriber.start()


def _nsec_for(o: dict) -> str | None:
    """Приватный ключ владельца: из mail_keys (зашифрованное хранилище) → fallback config."""
    try:
        from .auth import get_mail_key
        k = get_mail_key(o["pubkey_hex"])
        if k:
            return k
    except Exception:
        pass
    return o.get("nsec_hex") or None


def add_owner(o: dict) -> bool:
    """Динамическая регистрация владельца: добавляем в общий подписчик.

    Вызывается при регистрации нового ящика (POST /api/register).
    В NO_BRIDGE (тесты) — только регистрация в cfg, без подписки.
    """
    global _bridges, _subscriber
    with _lock:
        from . import config as cfg
        if o["pubkey_hex"] in _bridges:
            return False
        if o["pubkey_hex"] not in cfg.OWNER_INDEX:
            cfg.OWNERS.append(o)
            cfg.OWNER_INDEX[o["pubkey_hex"]] = o
        if os.environ.get("NO_BRIDGE") == "1":
            _bridges[o["pubkey_hex"]] = None
            return True
        b = _build_bridge(o)
        if b is None:
            return False
        _bridges[o["pubkey_hex"]] = b
        if _subscriber is not None:
            _subscriber.add_bridge(b)
        else:
            # подписчик ещё не стартовал (init_bridge ещё не вызывался) — стартуем
            _subscriber = SharedSubscriber([b], RELAYS)
            _subscriber.start()
        return True


def get_bridge(owner: str | None = None):
    """Мост владельца (по умолчанию — первый). None в тестах (NO_BRIDGE)."""
    if not _bridges:
        return None
    if owner and owner in _bridges:
        return _bridges[owner]
    return _bridges[list(_bridges)[0]]


def _setup_logging():
    """Логи моста в веб-режиме: mailbridge → INFO → stdout (backend.log).
    Раньше basicConfig был только в CLI main() — в веб-режиме логи терялись."""
    logger = logging.getLogger("mailbridge")
    if logger.handlers:  # уже настроен
        return
    logger.setLevel(logging.INFO)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(h)
    logger.propagate = False
