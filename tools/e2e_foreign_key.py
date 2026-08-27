#!/usr/bin/env python3
"""E2E: письмо от ЧУЖОГО (свежесгенерированного) ключа → мост Крайтера ловит → inbox."""
import json
import sys
import time

sys.path.insert(0, "/home/agent/data/projects/nostr-mail-bridge/src")
sys.path.insert(0, "/home/agent/data/projects/nostr-mail-bridge/deps")

import secp256k1  # noqa: E402
from mailbridge.nip59 import create_rumor, wrap, pubkey_from_privkey  # noqa: E402
from mailbridge.mail_message import build_mail, MAIL_KIND  # noqa: E402

RECIPIENT_PUBKEY = "8ae7965af1b61347bb9900b91cfa9487e4da2400bdb063521ad0850706ff5f96"
RECIPIENT_NPUB = "npub13tnevkh3kcf50wueqzu3e755sljd5fqqhkcxx5s66zzswphlt7tqe87x6n"
RELAYS = ["wss://nos.lol", "wss://offchain.pub", "wss://relay.primal.net"]

# 1) чужой ключ — свежий, никогда не использовался
sk = secp256k1.PrivateKey()
foreign_priv = sk.serialize()
foreign_pub = pubkey_from_privkey(foreign_priv)
print(f"Чужой ключ: priv={foreign_priv[:12]}… pub={foreign_pub[:16]}…")

# 2) письмо
mail_text = build_mail(
    from_addr=f"Случайный гость <npub{foreign_pub[:12]}@snin-mail.v2.site>",
    to_addr=f"{RECIPIENT_NPUB}@snin-mail.v2.site",
    subject="E2E письмо от чужого ключа",
    body="Это письмо подписано СВЕЖЕСГЕНЕРИРОВАННЫМ ключом, которого нет ни в одном ящике. Проверка: мост Крайтера должен его расшифровать и положить в inbox. Отправлено в {ts}.",
)

# 3) rumor kind:1301 + gift wrap на Крайтера
rumor = create_rumor(foreign_pub, MAIL_KIND, mail_text, [["p", RECIPIENT_PUBKEY]])
gw = wrap(rumor, foreign_priv, RECIPIENT_PUBKEY)
print(f"Gift wrap id={gw['id'][:16]}… kind={gw['kind']} (ожидаем 1059)")

# 4) публикация
import websocket  # noqa: E402
payload = json.dumps(["EVENT", gw], separators=(",", ":"))
accepted = []
for url in RELAYS:
    try:
        ws = websocket.create_connection(url, timeout=12)
        ws.send(payload)
        deadline = time.time() + 6
        ok = False
        while time.time() < deadline:
            try:
                arr = json.loads(ws.recv())
                if isinstance(arr, list) and arr and arr[0] == "OK":
                    ok = bool(arr[2])
                    break
            except Exception:
                break
        ws.close()
        accepted.append(url) if ok else None
        print(f"  {url}: {'OK' if ok else 'ОТКАЗ'}")
    except Exception as e:
        print(f"  {url}: ОШИБКА {e}")

print(f"Приняли {len(accepted)}/{len(RELAYS)}")
print(f"RESULT_PUBKEY={foreign_pub}")
