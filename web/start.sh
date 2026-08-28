#!/bin/bash
# Универсальный старт веб-клиента: работает из любого клона репо.
# Требуется: pip install -r requirements.txt (или ./deps при оффлайн-установке)
cd "$(dirname "$0")"
if [ -d ../deps ]; then
  PYTHONPATH="$(pwd)/../src:$(pwd)/../deps"
else
  PYTHONPATH="$(pwd)/../src"
fi
export PYTHONPATH
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port "${PORT:-8123}" > backend.log 2>&1 &
echo "Nostr Mail web started on :${PORT:-8123}, log: backend.log"
