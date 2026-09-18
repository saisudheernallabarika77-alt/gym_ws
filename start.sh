#!/bin/bash
# Fitora - one command to start everything (backend + frontend).
# Usage: ./start.sh
#
# Binds both servers to 0.0.0.0 so teammates on the same WiFi/LAN can open
# the app too, via this machine's IP (printed below once both are up).

set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "  Starting Fitora"
echo "=================================================="

# ---- stop anything already running on these ports ----
for port in 8000 3000; do
  pid=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "[*] Freeing port $port (killing pid $pid)"
    kill -9 $pid 2>/dev/null || true
    sleep 1
  fi
done

# ---- backend ----
echo "[*] Starting backend on 0.0.0.0:8000 ..."
cd backend
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/fitora-backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# ---- frontend ----
echo "[*] Starting frontend on 0.0.0.0:3000 ..."
cd frontend
npx next dev -H 0.0.0.0 -p 3000 > /tmp/fitora-frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# ---- wait for both to come up ----
echo "[*] Waiting for both servers..."
until curl -s -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1; do sleep 1; done
until curl -s -m 2 http://127.0.0.1:3000 >/dev/null 2>&1; do sleep 1; done

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "=================================================="
echo "  Fitora is running"
echo "=================================================="
echo "  On this machine : http://127.0.0.1:3000"
echo "  On your network  : http://${LAN_IP}:3000   (share with teammates on same WiFi)"
echo ""
echo "  Backend logs  : tail -f /tmp/fitora-backend.log"
echo "  Frontend logs : tail -f /tmp/fitora-frontend.log"
echo ""
echo "  To stop        : ./stop.sh"
echo "=================================================="

# Keep the script attached so Ctrl+C stops both
trap "echo; echo '[*] Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
