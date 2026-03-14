# J.A.R.V.I.S v3 — Battini Family AI Assistant

**Just A Rather Very Intelligent System** — A production-deployed private AI companion for the Battini family of Hyderabad.

## Live URL
`https://cloud-jarvis-p6zu.onrender.com`

## What's New in v3
- Hot/warm/cold memory tiers with importance scoring
- APScheduler background jobs (daily compression, RL analysis, birthday alerts)
- 3-agent architecture (Planner → Executor → Evaluator)
- RL feedback loop — JARVIS learns from 👍/👎 over time
- Safety validator — blocks SQL injection and prompt injection
- Global error handler — no more silent crashes
- Performance caching — sub-800ms responses

## Stack
- **Backend:** Python 3.11, FastAPI, asyncpg, Groq LLaMA 3.1 8B
- **Database:** Supabase PostgreSQL (free tier)
- **Frontend:** Vanilla JS ES6, Web Speech API, WebSocket
- **Hosting:** Render.com (free tier)

## Setup

### 1. Deploy to Render
- Push to `jarvis-v3` branch
- Set environment variables:
  ```
  DATABASE_URL=your_supabase_connection_string
  GROQ_API_KEY=your_groq_api_key
  JWT_SECRET=your_secret_key
  ```

### 2. Initialize Database
Run the SQL in `backend/db/migrations/001_init.sql` on your Supabase dashboard.

### 3. Seed Users (Google Colab)
```python
import os
os.environ["DATABASE_URL"] = "your_connection_string"
exec(open("backend/db/seed.py").read())
await seed()
```

### 4. Login
| Username | Password | Role |
|----------|----------|------|
| lucky | lucky@jarvis | Admin |
| krishna | krishna@jarvis | Father |
| sangeetha | sangeetha@jarvis | Mother |
| thapaswini | thapu@jarvis | Sister |
| dhruva | dhruva@jarvis | Brother |
| prajwal | prajwal@jarvis | Brother |

## Run Tests
```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Project Structure
```
jarvis-v3/
├── backend/
│   ├── agents/       # Planner, Evaluator agents
│   ├── api/          # REST + WebSocket endpoints
│   ├── db/           # Connection, migrations, seed
│   ├── jobs/         # APScheduler background jobs
│   ├── middleware/   # Auth guard, rate limiter
│   ├── safety/       # Input/output validator
│   ├── services/     # AI engine, memory, personality
│   └── utils/        # Family, language, text utils
├── config/
│   └── family.json
├── frontend/
│   ├── css/          # 5 CSS files
│   └── js/           # 8 JS modules
└── tests/
    └── test_all.py   # 35+ tests
```
