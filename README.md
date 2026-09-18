# Fitora

**Gym discovery, booking, membership & digital entry-pass platform for the Kakinada region, Andhra Pradesh.**

A B2B-SaaS-style marketplace: gym owners list their gyms, members discover and join them through an AI chatbot, and the admin controls the whole platform — money, dues, approvals — from one dashboard.

Three portals, one backend, one shared database:

| Portal | Who | What they do |
|---|---|---|
| **User** | Gym members | Sign up (email OTP), ask the chatbot for a gym, compare, join, pay by UPI, get a digital entry pass + diet chart |
| **Gym Owner** | Gym partners | List their gym, set pricing/plans, add coaches & equipment (with real photos), see members & dues, get paid monthly |
| **Admin** | Platform operator | Approve/suspend gyms, block/delete users, manage all money & payouts, resolve dues & complaints, add gyms manually |

---

## Table of contents

- [Architecture](#architecture)
- [Tech stack & why](#tech-stack--why)
- [The RAG chatbot, in detail](#the-rag-chatbot-in-detail)
- [The gym dataset](#the-gym-dataset)
- [Database schema](#database-schema)
- [Money flow](#money-flow)
- [Dues / overdue engine](#dues--overdue-engine)
- [Security](#security)
- [Project layout](#project-layout)
- [Running it locally](#running-it-locally)
- [Environment variables](#environment-variables)
- [Demo logins](#demo-logins)
- [API reference (by portal)](#api-reference-by-portal)
- [Known limitations / what's mocked](#known-limitations--whats-mocked)

---

## Architecture

```
┌─────────────────┐         ┌──────────────────────────────────────┐
│   Next.js 14     │  HTTP   │              FastAPI                  │
│   (frontend)     │────────▶│              (backend)                │
│   Port 3000       │  /api/v1 proxy rewrite                          │
└─────────────────┘         │  ┌────────────┐  ┌──────────────────┐ │
                             │  │ SQLAlchemy  │  │   RAG pipeline    │ │
                             │  │  ORM → DB   │  │  (retrieval +     │ │
                             │  └─────┬──────┘  │   generation)     │ │
                             │        │          └────────┬─────────┘ │
                             └────────┼───────────────────┼───────────┘
                                      │                    │
                              ┌───────▼───────┐    ┌───────▼────────┐
                              │  SQLite/       │    │   ChromaDB       │
                              │  PostgreSQL    │    │  (vector store)  │
                              │  (all rows)    │    └───────┬────────┘
                              └────────────────┘            │
                                                     ┌───────▼────────┐
                                                     │  Ollama (local)  │
                                                     │  qwen2.5:3b LLM  │
                                                     └─────────────────┘
```

The frontend never talks to the database or the LLM directly — everything goes through the FastAPI backend at `/api/v1/*`. Next.js's `rewrites()` config (`frontend/next.config.js`) transparently proxies `/api/*` and `/uploads/*` to the backend so the browser only ever sees one origin.

---

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 14** (App Router) + React 18 + TypeScript | File-based routing suits three separate portals cleanly; SSR-capable if needed later |
| Styling | **Tailwind CSS 3** + custom dark theme | Fast iteration, consistent design tokens, no CSS-in-JS runtime cost |
| Animation | **Framer Motion** | Declarative page/element transitions, respects `prefers-reduced-motion` |
| Backend | **FastAPI** (Python 3.10) | Async-first, automatic OpenAPI docs (`/docs`), Pydantic validation matches the RAG/ML ecosystem being Python-native |
| Database | **SQLite** (dev) → **PostgreSQL** (prod, swap via `DATABASE_URL`) | SQLite needs zero setup for local dev; the ORM layer (SQLAlchemy) makes the swap a one-line config change |
| ORM | **SQLAlchemy 2.0** | Mature, typed, prevents SQL injection by construction (no raw string queries anywhere in this codebase) |
| Auth | **JWT** (PyJWT) + **bcrypt** (passlib) | Stateless tokens scale without a session store; bcrypt is the industry-standard slow hash for passwords |
| Vector DB | **ChromaDB** (persistent, local) | Free, embeds directly in the Python process, no separate server to run |
| Embeddings | **sentence-transformers** `all-MiniLM-L6-v2` | 384-dim, CPU-fast, free, good enough quality for a domain this narrow (gyms, not general knowledge) |
| LLM | **Ollama** running **qwen2.5:3b** locally | Zero API cost, fully offline-capable, 3B params is enough for "read these 6 gym records and recommend 3" — this is retrieval-grounded generation, not open-ended reasoning |
| QR codes | **qrcode** + **Pillow** | Generates the entry-pass QR client-ready as a `data:image/png` URI, no external service |
| Email | **smtplib** (stdlib) + Gmail SMTP | No third-party email API needed for OTP volume this small |
| PDF (future) | **reportlab** | Installed for entry-pass/diet-chart PDF export, not yet wired to an endpoint |

**Nothing here is a paid API dependency.** The whole stack — RAG, LLM, database, email — runs for free on a single machine. The only paid step in the real product would eventually be a production payment gateway (Razorpay) and hosting.

---

## The RAG chatbot, in detail

This is the centerpiece of the user portal: type a request in plain English or Telugu-English ("1500 lopu AC gym kavali"), get grounded gym recommendations — never a hallucinated gym, price, or phone number.

### Why hybrid retrieval, not pure vector search

A pure embedding search cannot reliably honour a hard constraint like "under ₹1500" — embeddings blur numbers together (₹1400 and ₹1600 look almost identical to a vector model). So the pipeline is **hybrid**:

```
User query
    │
    ▼
1. parse_query()          Regex/keyword extraction of HARD constraints:
   (query_parser.py)      budget, AC, coach-included, gym type, facilities,
                           equipment, rating, distance, locality, goal, sort
    │
    ▼
2. Chroma `where` filter   Pre-filter: only gyms that satisfy every hard
   (vector_store.py)       constraint survive to the next stage
    │
    ▼
3. Semantic ranking        The surviving gyms are ranked by embedding
   (ChromaDB cosine sim)   similarity to the query's *meaning*
    │
    ▼
4. Post-filters            Facility/equipment requirements the vector
   (retriever.py)          metadata can't express (e.g. "has a swimming pool")
    │
    ▼
5. Graceful relaxation     If nothing matches, constraints are dropped one
                           at a time (least important first) until there's
                           an answer — always with a note about what relaxed
    │
    ▼
6. Re-rank                 Blend semantic score with rating / price / distance,
                           weighted by the user's apparent intent (cheapest?
                           best-rated? nearest?)
    │
    ▼
7. LLM generation           Ollama (qwen2.5:3b) writes a 3-6 line answer from
   (chatbot.py)             ONLY the ranked gym facts — a strict system prompt
                            forbids inventing gyms, prices or phone numbers.
                            If Ollama is unreachable, a deterministic template
                            answer is used instead — the chatbot never hard-fails.
```

### What the parser understands

`app/rag/query_parser.py` extracts, from free text:

- **Budget**: "under 1500", "below 2000", "1000 lopu", "between 1000 and 2000"
- **AC / Non-AC**: "AC gym", "non-ac", "ac leni"
- **Coach**: "coach included", "personal trainer", "trainer kalipi"
- **Gym type**: "ladies only", "men only"
- **Facilities**: parking, shower, locker, yoga, zumba, swimming pool, steam bath
- **Equipment**: "smith machine", "leg press", "cable crossover", treadmill/cardio
- **Rating**: "4+ rating", "top rated"
- **Distance/locality**: "near me", "within 10 km", known town names (Kakinada, Rajahmundry, Pithapuram, etc.)
- **Fitness goal**: weight loss, muscle gain, strength, general fitness
- **Sort intent**: "cheapest", "best rated", "nearest"

This is genuinely bilingual-aware — it was built and tested against Telugu-English ("Tenglish") phrasing, not just English.

### Document format fed to the vector store

Each gym is turned into a dense natural-language paragraph (`app/rag/document_builder.py`) that restates its facts in *several phrasings* — "Rs.1200 per month", "1200 rupees monthly", "budget friendly under 1500" — so semantic search matches however a real user happens to type. Hard numeric facts also go into Chroma's metadata (as `int`/`float`/`bool`) so they can be **filtered exactly**, never fuzzily.

### Keeping the index in sync

Every time a gym owner saves their profile, or the admin edits/creates/suspends a gym, the single changed gym is re-embedded and upserted into ChromaDB immediately (`GymVectorStore.index_one()`) — there's no batch job or delay. A gym added by the admin for a village with no partner account yet becomes chatbot-discoverable within the same request.

---

## The gym dataset

**260+ gyms across a 100 km radius of Kakinada, Andhra Pradesh** — built to be as real as free data sources allow:

1. **Real gyms from OpenStreetMap** (Overpass API, no key needed): actual gym names, exact GPS coordinates, and tags for ~18 gyms that exist in OSM's India coverage.
2. **Real localities from OpenStreetMap**: 3,401 actual towns/villages/suburbs within 100 km of Kakinada, each with real GPS coordinates and place-type (city/town/village/suburb) — this is the geographic backbone every other gym is anchored to.
3. **Realistically generated enrichment** for the remaining ~245 gyms, because *pricing, equipment inventories, and coach rosters are not public data anywhere* — these are synthesized using market-researched Indian tier-2/3 city gym economics (₹600–₹3,450/month, four pricing tiers, realistic coach-fee-included-vs-separate ratios) and placed at real coordinates jittered within the real locality they belong to.

**Important — be honest about what this means**: only the ~18 gyms sourced from
OpenStreetMap are *real, existing gyms* you could search for and find on a map.
The other ~245 are placeholder listings with invented names, generated to fill
out the catalogue for a region where the overwhelming majority of small
independent gyms simply have no public online presence (no website, no map
listing, no published pricing) — that data can only realistically be collected
by physically visiting every gym, which was out of scope here. Every gym record
carries a `data_source` field (`openstreetmap` vs `fitora_regional_survey`) so
this distinction is never hidden: the API exposes it as `is_real_listing`, the
gym card shows a "Real listing" badge only for the genuine ones, and the gym
detail page states plainly which kind you're looking at.

Scripts, in run order:

```
data/scripts/01_fetch_osm_gyms.py       # pulls real gyms from Overpass API
data/scripts/02_fetch_localities.py     # pulls real towns/villages from Overpass API
data/scripts/03_build_gym_dataset.py    # merges + enriches → data/processed/gyms.json
```

Each gym record carries: name, tier, full address + exact lat/lon + distance from Kakinada, contact info, timings, complete pricing (monthly fee, registration fee, coach-included-or-separate with the exact extra amount, a 4-tier plan ladder with bulk discounts), AC status, supplements availability, a facilities list, a categorized equipment inventory (name, quantity, condition — never a generic stock photo), a coach roster (name, gender, years of experience, specialisations, certifications), rating, review count, and member count.

---

## Database schema

23 tables (`app/db/models.py`), grouped by portal:

**User side**: `User`, `OTPToken`
**Gym owner side**: `GymOwner`, `Gym`, `GymPlan`, `Coach`, `Equipment`
**Membership & money**: `Membership`, `Payment`, `Payout`
**Pass / diet / reviews**: `EntryPass`, `DietPlan`, `Review`
**Admin side**: `Admin`, `Complaint`, `AuditLog`

Key design decisions:

- **Money always flows through the platform.** A `Payment` row always belongs to the platform first; `platform_commission` and `gym_share` are computed server-side at payment time. A gym owner's share only reaches them via a `Payout` row the admin explicitly creates and releases — there is no code path where a gym is paid directly.
- **The entry pass QR is HMAC-signed** (`sign_pass_payload`/`verify_pass_payload` in `core/security.py`), so a screenshot of someone else's pass can't be edited into a valid one, and the gate-scan endpoint re-derives validity dates from the live `Membership`/`EntryPass` rows rather than trusting the signed payload's copies of those fields (defense-in-depth in case the signing secret is ever rotated late).
- **Dues have a state machine**: `active → due → overdue`, each transition gated by `next_due_date` + a configurable grace period (`Membership.grace_days`, default 7 days). See [Dues engine](#dues--overdue-engine) below.

---

## Money flow

Per the original spec: **members never pay a gym directly.**

```
Member                    Platform (Fitora)                Gym Owner
  │                              │                              │
  │  1. Pays via UPI (mock/      │                              │
  │     Razorpay) for the        │                              │
  │     full membership amount   │                              │
  │─────────────────────────────▶│                              │
  │                              │                              │
  │                        2. Payment row created:              │
  │                           amount = platform_commission       │
  │                                  + gym_share                 │
  │                           (commission % set per-gym,         │
  │                            default 10%)                      │
  │                              │                              │
  │                              │  3. Admin reviews pending     │
  │                              │     payouts for the month,    │
  │                              │     creates + releases a      │
  │                              │     Payout row                │
  │                              │─────────────────────────────▶│
  │                              │                              │  4. Gym owner receives
  │                              │                              │     net_payable to their
  │                              │                              │     registered bank/UPI
```

The gym owner's dashboard shows their lifetime share, what's already paid out, and what's awaiting payout — but the owner **cannot trigger a payout themselves**; only the admin can (`app/api/admin.py` `create_payout`/`release_payout`).

### Payment gateway abstraction

`app/services/payment_service.py` defines a `PaymentGateway` interface with two implementations:

- **`MockUPIGateway`** (default, `PAYMENT_GATEWAY=mock`): generates a *real, scannable* UPI deep-link and QR code so the checkout UI looks and behaves like production, then simulates a bank response. No real money moves. Client-confirmed (there's no real bank to call back to).
- **`RazorpayGateway`** (`PAYMENT_GATEWAY=razorpay`): a real integration, but **payment activation happens exclusively via a server-to-server webhook** (`POST /api/v1/webhooks/razorpay`), verified against `RAZORPAY_WEBHOOK_SECRET` — a secret only Razorpay's servers and this backend know. The client-invoked `/pay/{ref}` endpoint checks the checkout-time signature (so the UI can show "confirming with the bank...") but never itself flips a Razorpay payment to `success`. This is deliberate: a client-driven confirmation path is fine for a mock gateway with nothing at stake, but a real gateway must never let the browser be the thing that decides "this payment succeeded."

---

## Dues / overdue engine

Exactly per the spec (Session 3): when a member's renewal date passes, the flow is:

```
active ──(due date passes)──▶ due ──(grace period expires)──▶ overdue
                                │                                  │
                          warning email sent                 appears in the
                          (once per cycle)                   Dues list on BOTH
                                                               admin AND gym owner
                                                               portals
```

Who can do what — enforced at the API level, not just the UI:

- **Gym owner**: can only **view** the dues list for their own gym and **raise a complaint** to the admin about a defaulting member. They cannot extend a grace period or remove a member (verified: `owner.py` `dues()` returns `can_remove_member: false` in its `permissions` block, and there is no owner-facing endpoint that mutates a `Membership`'s status).
- **Admin**: can view dues across *every* gym, extend a member's grace period (`POST /admin/dues/{id}/extend-grace`), or remove a defaulting member outright (`POST /admin/dues/{id}/remove-member`, which also deactivates their entry pass immediately).

`app/services/dues_service.py` runs the whole lifecycle: `evaluate()` classifies one membership's state from `next_due_date` + `grace_days`, `run_daily_sweep()` re-classifies every live membership and sends at most one warning email per cycle (idempotent — safe to re-run), and `gym_payment_summary()` produces the "who paid, who didn't, how many total" snapshot both the admin and the owner see.

---

## Security

A security review was run against the full backend (see conversation history for the complete findings list). Everything below is already fixed in this codebase:

- **No hardcoded secrets.** `JWT_SECRET` and `PASS_QR_SECRET` have no default value; the app **refuses to start** with `ENV=production` unless both are set to a random 32+ character string. In dev, a fresh random secret is generated per process start instead of falling back to a placeholder.
- **Rate limiting** on all three login endpoints, OTP issuance/resend, and the entry-pass gate-scan endpoint (`app/core/ratelimit.py` — in-process sliding window, tuned per endpoint).
- **The shared image-upload endpoint requires authentication** (any of the three portals) plus a 40-uploads/day quota per account — it was previously open to anyone.
- **`scripts/seed_db.py` refuses to run** against `ENV=production`, since it creates publicly-documented demo credentials.
- **CORS drops its dev-only origins** (`localhost:3000`) automatically once `ENV=production`.
- **A gym owner cannot file a complaint against a user who isn't actually a member of their gym** — closes a minor IDOR where the owner portal took the target user ID on trust.
- **The entry-pass gate scan re-derives validity dates and coach status from the live database**, not from the signed QR payload's own copies of those fields — so even a compromised signing secret can't be used to extend a previously-issued pass's validity by re-signing a tampered copy.
- Password hashing is bcrypt (12 rounds); OTP comparison uses constant-time `hmac.compare_digest`; every DB query goes through the SQLAlchemy ORM (no raw SQL, no injection surface); file uploads always use a server-generated filename (no path traversal via a crafted original filename).

**What's still explicitly deferred** (not vulnerabilities in the current mock setup, but required before a real Razorpay/production go-live): rotating the seeded demo account passwords, and moving the in-process rate limiter to Redis if this is ever deployed with more than one worker process.

---

## Project layout

```
gym_ws/
├── README.md                    ← you are here
├── .gitignore
├── data/
│   ├── scripts/                 ← dataset build pipeline (see above)
│   ├── raw/                     ← OSM API responses, cached
│   └── processed/gyms.json      ← the final 260+ gym dataset
├── backend/
│   ├── .env                     ← secrets (never committed)
│   ├── requirements.txt
│   ├── fitora.db                ← SQLite database file
│   ├── chroma_db/                ← ChromaDB persistent vector store
│   ├── uploads/                  ← user/gym photo uploads
│   ├── scripts/
│   │   ├── seed_db.py            ← populates the DB from gyms.json
│   │   ├── build_index.py        ← builds/rebuilds the RAG vector index
│   │   └── e2e_test.py           ← 78-case end-to-end test suite, all 3 portals
│   └── app/
│       ├── main.py               ← FastAPI app, CORS, router mounting
│       ├── core/
│       │   ├── config.py         ← env-driven settings, production secret guard
│       │   ├── security.py       ← JWT, bcrypt, OTP, QR-pass signing
│       │   └── ratelimit.py      ← in-process rate limiter
│       ├── db/
│       │   ├── models.py         ← all 23 SQLAlchemy models
│       │   └── session.py        ← engine/session setup
│       ├── api/                  ← one router per concern
│       │   ├── auth.py           ← signup/OTP/login, all 3 portals
│       │   ├── gyms.py           ← public discovery, search, compare
│       │   ├── chat.py           ← the RAG chatbot endpoint
│       │   ├── membership.py     ← join/pay/pass/diet/scan/webhook
│       │   ├── profile.py        ← user profile, reviews, uploads
│       │   ├── owner.py          ← gym owner portal
│       │   ├── admin.py          ← admin portal
│       │   └── deps.py           ← auth dependency injection per role
│       ├── rag/
│       │   ├── document_builder.py  ← gym → embeddable text + metadata
│       │   ├── query_parser.py      ← NL query → hard constraints
│       │   ├── vector_store.py      ← ChromaDB wrapper
│       │   ├── retriever.py         ← hybrid retrieval + re-ranking
│       │   └── chatbot.py           ← Ollama-backed answer generation
│       └── services/
│           ├── email_service.py     ← SMTP + branded HTML emails
│           ├── payment_service.py   ← gateway abstraction, mock + Razorpay
│           ├── pass_service.py      ← QR generation/verification
│           ├── dues_service.py      ← overdue lifecycle
│           └── diet_service.py      ← BMR/TDEE + Indian meal-plan generator
└── frontend/
    ├── next.config.js            ← proxies /api/* to the backend
    ├── tailwind.config.ts        ← the dark theme design tokens
    ├── lib/
    │   ├── api.ts                 ← typed API client for all 3 portals
    │   └── utils.ts                ← formatting, geolocation helper
    ├── components/
    │   ├── ui.tsx                  ← Button/Input/Modal/Chip/etc primitives
    │   ├── AppShell.tsx             ← shared nav shell per portal
    │   └── GymCard.tsx              ← the gym listing card
    └── app/
        ├── page.tsx                 ← landing page
        ├── signup/, login/           ← user auth (OTP flow)
        ├── chat/                     ← the chatbot screen
        ├── gyms/, gyms/[code]/       ← browse + gym detail
        ├── join/[code]/              ← join form → payment → success
        ├── pass/[code]/              ← entry pass card + diet chart
        ├── memberships/, profile/
        ├── owner/                    ← gym owner portal (10 pages)
        └── admin/                    ← admin portal (7 pages)
```

---

## Running it locally

### Prerequisites

- Python 3.10+
- Node.js 18+ / npm
- [Ollama](https://ollama.com) installed, with a model pulled: `ollama pull qwen2.5:3b`

### 1. Backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Create backend/.env (see Environment variables section below)

# Seed the database from the gym dataset (creates 1 admin, 260+ gym owners,
# 260+ gyms, 40 demo users with memberships/payments/passes)
./venv/bin/python -m scripts.seed_db --reset

# Build the RAG vector index (first run downloads the embedding model, ~90MB)
./venv/bin/python -m scripts.build_index --test

# Start the API
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for interactive API docs, or `http://127.0.0.1:8000/health` for a status check.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://127.0.0.1:3000`.

### 3. Ollama (for the chatbot)

Make sure Ollama's server is running (`ollama serve`, or it starts automatically on most installs) and the model is pulled:

```bash
ollama pull qwen2.5:3b
```

If Ollama is unreachable, the chatbot falls back to a deterministic template answer built from the same retrieved facts — it never hard-fails, just loses the natural-language polish.

### Running the test suite

```bash
cd backend
./venv/bin/python -m scripts.e2e_test --log <path to uvicorn's stdout log>
```

This exercises all three portals end-to-end: signup → OTP → login → chat → join → pay → entry pass → diet chart → QR scan → owner dashboard → admin dues/payouts/gym-creation → access control. 78 assertions.

---

## Environment variables

All in `backend/.env` (never committed — see `.gitignore`):

```bash
# ---- SMTP (Gmail) ----
SMTP_ENABLED=true                          # false = OTPs print to the console instead
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASSWORD=<16-char Gmail App Password>  # myaccount.google.com/apppasswords
SMTP_FROM_NAME=Fitora
SMTP_FROM_EMAIL=youremail@gmail.com

# ---- JWT / security ----
JWT_SECRET=<random 32+ char string>         # python -c "import secrets; print(secrets.token_urlsafe(48))"
PASS_QR_SECRET=<random 32+ char string>     # same command, different value

# ---- payments ----
PAYMENT_GATEWAY=mock                        # mock | razorpay
PLATFORM_UPI_ID=fitora@upi
RAZORPAY_KEY_ID=                            # only if PAYMENT_GATEWAY=razorpay
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=                    # from Razorpay dashboard → Webhooks

# ---- database ----
# DATABASE_URL=postgresql://user:password@localhost:5432/fitora   # omit for SQLite dev
```

`ENV=production` (unset = development) additionally requires `JWT_SECRET`/`PASS_QR_SECRET` to be present and strong, or the app refuses to start.

---

## Demo logins

Created by `scripts/seed_db.py` — **these are publicly documented in this file, so rotate or delete them before any real deployment**:

| Portal | Email | Password |
|---|---|---|
| Admin | `admin@fitora.in` | `admin123` |
| Gym owner (any gym) | `<gym-slug>@fitora-partner.in` — printed by the seed script | `partner123` |
| Demo user (any of 40) | `<name>.<name><n>@example.com` — printed by the seed script | `user123` |

The seed script prints one example of each at the end of its run.

---

## API reference (by portal)

Full interactive docs at `/docs` once the backend is running. Grouped summary:

**Auth** (`/api/v1/auth/*`): `signup`, `verify-otp`, `resend-otp`, `login`, `me` (user) · `owner/signup`, `owner/verify-otp`, `owner/login` · `admin/login`

**Discovery** (`/api/v1/gyms/*`): `GET /gyms` (search/filter/sort), `GET /gyms/filters`, `GET /gyms/{code}` (pin-to-pin detail), `GET /gyms/compare/side-by-side`

**Chatbot** (`/api/v1/chat/*`): `POST /chat`, `POST /chat/stream` (SSE), `GET /chat/suggestions`, `GET /chat/health`

**Membership** (`/api/v1/*`): `GET /join/{code}/prefill`, `POST /join/{code}`, `POST /pay/{ref}`, `POST /webhooks/razorpay`, `GET /pass/{code}`, `GET /diet/{code}`, `GET /my/memberships`, `POST /scan` (gate device, unauthenticated but rate-limited)

**Profile** (`/api/v1/*`): `PUT /profile`, `POST /profile/photo`, `POST /uploads/image`, `POST /reviews`

**Gym owner** (`/api/v1/owner/*`): `dashboard`, `gym` (GET/PUT), `bank`, `plans`, `coaches`, `equipment`, `members`, `dues` (read-only), `reviews`, `earnings`, `complaints`

**Admin** (`/api/v1/admin/*`): `dashboard`, `users` (list/detail/block/unblock/delete), `gyms` (list/create-manually/update/approve/suspend), `dues` (list-all/extend-grace/remove-member/run-sweep), `payments`, `payouts` (pending/create/release), `complaints` (list/act-on), `audit-logs`, `rag/reindex`, `rag/status`

---

## Known limitations / what's mocked

- **Payments** default to a mock UPI gateway (generates a real, scannable QR — no real money moves). A Razorpay implementation exists with proper webhook-based confirmation; flip `PAYMENT_GATEWAY=razorpay` and supply the three Razorpay env vars to go live.
- **Gym/equipment photos** are placeholders (rendered as a neutral icon, deliberately never a fake stock photo) until a gym owner actually uploads one through `/owner/equipment` or `/owner/coaches`.
- **Database** is SQLite by default. Swap `DATABASE_URL` to a PostgreSQL connection string for concurrent-write production use — the ORM layer needs no other changes.
- **Rate limiting** is in-process memory, fine for a single server; move to Redis if ever deployed with multiple worker processes.
- **PDF export** (reportlab is installed) is not yet wired to an endpoint — the entry pass and diet chart are currently web-view only.
