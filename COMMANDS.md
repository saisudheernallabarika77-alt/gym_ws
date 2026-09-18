# Fitora — Command Reference

Every command needed to set up, run, test, and troubleshoot this project, in one place.
All backend commands assume you're in `backend/` with the virtualenv at `backend/venv/`.
All frontend commands assume you're in `frontend/`.

---

## Table of contents

- [First-time setup](#first-time-setup)
- [Daily use — starting the app](#daily-use--starting-the-app)
- [Database](#database)
- [RAG / chatbot index](#rag--chatbot-index)
- [Testing](#testing)
- [Ollama (the local LLM)](#ollama-the-local-llm)
- [Checking things are healthy](#checking-things-are-healthy)
- [Stopping servers](#stopping-servers)
- [Security](#security)
- [Dataset rebuild (rarely needed)](#dataset-rebuild-rarely-needed)
- [Troubleshooting](#troubleshooting)

---

## First-time setup

```bash
# ---- Backend ----
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Create backend/.env - copy this template and fill in real values
cat > .env << 'EOF'
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASSWORD=your16charapppassword
SMTP_FROM_NAME=Fitora
SMTP_FROM_EMAIL=youremail@gmail.com

JWT_SECRET=changeme
PASS_QR_SECRET=changeme

PAYMENT_GATEWAY=mock
PLATFORM_UPI_ID=fitora@upi
EOF

# Generate strong random secrets and drop them into .env
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))"
python3 -c "import secrets; print('PASS_QR_SECRET=' + secrets.token_urlsafe(48))"
# ^ paste each output over the "changeme" placeholders in .env

# Seed the database (260+ gyms, 40 demo users, 1 admin)
./venv/bin/python -m scripts.seed_db --reset

# Build the RAG vector index (first run downloads the embedding model, ~90MB)
./venv/bin/python -m scripts.build_index

# ---- Frontend ----
cd ../frontend
npm install
```

### Gmail App Password (for real OTP emails)

1. Enable 2-Step Verification: https://myaccount.google.com/security
2. Create an App Password: https://myaccount.google.com/apppasswords
3. Paste the 16-character password (no spaces) into `SMTP_PASSWORD` in `.env`

### Ollama (required for the chatbot's natural-language answers)

```bash
# Install: https://ollama.com
ollama pull qwen2.5:1.5b     # the model this project uses by default
ollama serve                  # if it isn't already running as a service
```

---

## Daily use — starting the app

Open two terminals.

**Terminal 1 — backend:**
```bash
cd backend
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
API: http://127.0.0.1:8000 · Interactive docs: http://127.0.0.1:8000/docs

**Terminal 2 — frontend:**
```bash
cd frontend
npm run dev
```
App: http://127.0.0.1:3000

That's it — open http://127.0.0.1:3000 in a browser.

### Run the backend in the background (single terminal)

```bash
cd backend
nohup ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > server.log 2>&1 &
tail -f server.log        # watch logs
```

To stop it later:
```bash
pkill -f "uvicorn app.main"
```

---

## Database

```bash
cd backend

# Fresh seed - WIPES all data and recreates 260+ gyms, 40 users, 1 admin
./venv/bin/python -m scripts.seed_db --reset

# Seed without wiping (updates existing rows, adds anything missing)
./venv/bin/python -m scripts.seed_db

# Inspect the database directly (SQLite)
sqlite3 fitora.db ".tables"
sqlite3 fitora.db "SELECT COUNT(*) FROM gyms;"
sqlite3 fitora.db "SELECT email FROM admins;"

# Or from Python, for anything more complex:
./venv/bin/python -c "
from app.db.session import SessionLocal
from app.db.models import Gym, User, GymOwner
db = SessionLocal()
print('gyms:', db.query(Gym).count())
print('users:', db.query(User).count())
print('owners:', db.query(GymOwner).count())
db.close()
"
```

**Switching to PostgreSQL** (production): set `DATABASE_URL` in `.env`, e.g.
```
DATABASE_URL=postgresql://user:password@localhost:5432/fitora
```
then re-run the seed command. No code changes needed.

---

## RAG / chatbot index

```bash
cd backend

# Rebuild the vector index from the dataset JSON (used right after seeding)
./venv/bin/python -m scripts.build_index

# Rebuild from the LIVE database instead (use this if you've edited gyms
# through the owner/admin portal and want to force a full re-sync)
./venv/bin/python -m scripts.build_index --from-db

# Rebuild AND run a batch of sample queries to sanity-check retrieval quality
./venv/bin/python -m scripts.build_index --test
```

> Note: normally you never need to run this manually — every gym save/create/suspend
> through the owner or admin portal re-indexes that one gym automatically. Use
> `build_index` only after a fresh seed or if you suspect the index has drifted
> out of sync with the database (check with `GET /api/v1/admin/rag/status`).

---

## Testing

```bash
cd backend

# Full end-to-end suite (78 assertions across all 3 portals) - backend must be running
./venv/bin/python -m scripts.e2e_test --log server.log

# Against a different port/host
./venv/bin/python -m scripts.e2e_test --api http://127.0.0.1:8001 --log server.log

# If SMTP_ENABLED=true on your running server, the test can't read the OTP
# from real email - run a throwaway SMTP-off instance on another port instead:
SMTP_ENABLED=false ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 &
./venv/bin/python -m scripts.e2e_test --api http://127.0.0.1:8001 --log /dev/stdout
```

### Frontend type-check

```bash
cd frontend
npx tsc --noEmit
```

---

## Ollama (the local LLM)

```bash
ollama list                    # see which models are pulled
ollama ps                       # see what's currently loaded / running
ollama pull qwen2.5:1.5b        # the default model (fast, used by this project)
ollama pull qwen2.5:3b          # a larger, slower, slightly better-quality option
ollama serve                    # start the Ollama server manually if needed
```

To use a different model, set it in `backend/app/core/config.py`:
```python
OLLAMA_MODEL: str = "qwen2.5:1.5b"    # change this line
```
then restart the backend.

**If Ollama is down or unreachable**, the chatbot doesn't crash — it falls back to
a deterministic template answer built from the same retrieved gym facts. You'll just
lose the natural-language polish, not the recommendations themselves.

---

## Checking things are healthy

```bash
# Backend alive + how many gyms are indexed
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

# Frontend alive
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000

# Chatbot / RAG specifically
curl -s http://127.0.0.1:8000/api/v1/chat/health | python3 -m json.tool

# Full API docs in the browser
xdg-open http://127.0.0.1:8000/docs   # or just paste the URL
```

Expected healthy response from `/health`:
```json
{
  "status": "ok",
  "database": "connected",
  "rag_indexed_gyms": 260,
  "payment_gateway": "mock",
  "smtp_enabled": true
}
```

---

## Stopping servers

```bash
# Backend
pkill -f "uvicorn app.main"

# Frontend (find and kill the npm/node dev server)
pkill -f "next dev"

# Or, if you started them with & in a terminal, just Ctrl+C in that terminal
```

---

## Security

```bash
# Generate a new random secret (use for JWT_SECRET / PASS_QR_SECRET / RAZORPAY_WEBHOOK_SECRET)
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Rotate a Gmail App Password:
#   1. https://myaccount.google.com/apppasswords -> revoke the old "Fitora" entry
#   2. Create a new one, paste into backend/.env as SMTP_PASSWORD
#   3. Restart the backend

# Confirm rate limiting is active (should start returning 429 after a few tries)
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8000/api/v1/auth/admin/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@fitora.in","password":"wrong"}'
done
```

`ENV=production` in `.env` makes the app refuse to start unless `JWT_SECRET` and
`PASS_QR_SECRET` are both set to a real, strong value — this is intentional and
cannot be bypassed by a weak/missing secret.

---

## Dataset rebuild (rarely needed)

Only needed if you want to regenerate the gym dataset itself (not the RAG index —
that's `build_index` above). Run in order, from the project root:

```bash
cd data/scripts
python3 01_fetch_osm_gyms.py        # pulls real gyms from OpenStreetMap Overpass API
python3 02_fetch_localities.py      # pulls real towns/villages from the same API
python3 03_build_gym_dataset.py     # merges + enriches -> ../processed/gyms.json

# Then re-seed the database and rebuild the index with the new dataset:
cd ../../backend
./venv/bin/python -m scripts.seed_db --reset
./venv/bin/python -m scripts.build_index
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl http://127.0.0.1:8000/health` refused | Backend not running / crashed | Check `server.log`; re-run the uvicorn command |
| Chatbot answers with "gym index is empty" | RAG index never built | `./venv/bin/python -m scripts.build_index` |
| Chatbot very slow (20s+) | Using the larger `qwen2.5:3b` model on CPU | Switch to `qwen2.5:1.5b` in `config.py`, restart backend |
| OTP email never arrives | `SMTP_ENABLED=false`, or wrong App Password | Check `server.log` for `email sent to ...` or the printed console fallback |
| `429 Too Many Requests` while testing | Rate limiter tripped (working as intended) | Wait out the window shown in the response, or restart the backend to reset the in-memory limiter |
| `Refusing to start with ENV=production...` | Weak/missing `JWT_SECRET` or `PASS_QR_SECRET` | Generate real random secrets (see Security section above) |
| Frontend shows blank page / CSS broken | Tailwind syntax error in `globals.css`, or dev server needs restart | Check the `npm run dev` terminal output for a syntax error |
| "This phone number is already registered" on signup | Re-running a test with the same phone number | Use a different phone number, or a fresh test email |
| Admin-added gym doesn't show up in chat immediately | Rare - RAG index drifted | `POST /api/v1/admin/rag/reindex` (as admin), or `--from-db` rebuild |
| `python -m scripts.seed_db` exits immediately with a warning | `ENV=production` is set | This is deliberate - seeding creates public demo credentials. Unset `ENV` or use a separate script with real values for production |
