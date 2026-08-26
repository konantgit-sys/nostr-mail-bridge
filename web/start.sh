#!/bin/bash
cd /home/agent/data/sites/cryter-mail
PYTHONPATH=/home/agent/data/projects/nostr-mail-bridge/src:/home/agent/data/projects/nostr-mail-bridge/deps nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8123 > backend.log 2>&1 &
