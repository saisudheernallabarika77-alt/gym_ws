#!/bin/bash
# Fitora - stop both servers.
# Usage: ./stop.sh

for port in 8000 3000; do
  pid=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "[*] Stopping process on port $port (pid $pid)"
    kill -9 $pid 2>/dev/null || true
  else
    echo "[*] Nothing running on port $port"
  fi
done
echo "[+] Done."
