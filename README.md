## Zeitgeist → RSA Agent (Web + Backend)

Production-style agent that:
- collects recent content from **Reddit**, **X**, and **YouTube transcripts**
- clusters into **pain points** + **highlights** with **evidence links/snippets**
- drafts **Google Responsive Search Ads (RSA)** with **hard char limits**
- runs a **QA/policy pass** (duplicates, risky claims, optional trademark list)
- gates **Google Ads push** behind explicit user approval and **dry-run validation**

### Architecture
- **Web UI**: Next.js + TypeScript + Tailwind (`web/`)
- **Backend**: FastAPI (`backend/`)
- **Jobs**: Celery + Redis (`backend/app/worker/`)
- **DB**: Postgres (SQLAlchemy + Alembic)
- **LLM**: OpenAI-compatible client (optional; falls back to heuristics if unset)

### Quickstart (Docker)

- **1) Configure env**
  - Copy `.env.example` → `.env` and fill what you have.
  - Missing collector credentials are fine (the platform is marked “skipped”).

- **2) Start services**

```bash
docker compose up -d --build
```

- **3) Open the UI**
  - `http://localhost:3000`

### Local dev (no Docker)

- **Backend**

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/zeitgeist"
uvicorn app.main:app --reload --port 8000
```

- **Worker**

```bash
cd backend
. .venv/bin/activate
celery -A app.worker.celery_app.celery_app worker -l info
```

- **Web**

```bash
cd web
npm install
export NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"
npm run dev
```

### Core endpoints (FastAPI)
- `POST /api/runs` → create run + enqueue pipeline
- `GET /api/runs/{id}` → run + doc counts + errors
- `GET /api/runs/{id}/results` → clusters + RSA drafts + QA report
- `POST /api/runs/{id}/dry-run` → local+remote validate (remote skipped if creds missing)
- `POST /api/runs/{id}/push` → push live (blocked unless run is `awaiting_approval`)
- `GET /api/runs/{id}/stream` → SSE progress

### Tests (backend)

```bash
cd backend
. .venv/bin/activate
pytest -q
```

