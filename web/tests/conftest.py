"""Conftest: добавляет mailbridge (src) в sys.path — как start.sh.

Нужен всем тестам: mailapp.routers.blossom импортирует mailbridge
на верхнем уровне.
"""
import os
import sys

_MB = "/home/agent/data/projects/nostr-mail-bridge/src"
_DEPS = "/home/agent/data/projects/nostr-mail-bridge/deps"
for _p in (_MB, _DEPS):
    if _p not in sys.path:
        sys.path.insert(0, _p)
