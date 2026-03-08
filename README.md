# J.A.R.V.I.S — Battini Family AI

> **J**ust **A** **R**ather **V**ery **I**ntelligent **S**ystem  
> Private AI assistant for the Battini family, Hyderabad.

---

## Quick Start

### 1. Clone and install
```bash
git clone https://github.com/YOUR_USERNAME/jarvis.git
cd jarvis
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
cp .env.example .env
# Edit .env and fill in GROQ_API_KEY, DATABASE_URL, JWT_SECRET
```

### 3. Seed the database (run ONCE)
```bash
python -m backend.db.seed
```

### 4. Run locally
```bash
uvicorn backend.main:app --reload
# Open http://localhost:8000
```

---

## Deploy to Render (Free Plan)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → New Web Service → connect your repo.
3. Render detects `render.yaml` automatically.
4. Set the 3 secret env vars in Render dashboard:
   - `GROQ_API_KEY`
   - `DATABASE_URL`
   - `JWT_SECRET`
5. Set `RENDER_EXTERNAL_URL` to your Render URL after first deploy.
6. Deploy. Done. ✅

---

## Architecture

```
jarvis/
├── backend/
│   ├── main.py              ← FastAPI app entry point
│   ├── config.py            ← Env var loading + validation
│   ├── api/                 ← Route handlers (thin)
│   │   ├── auth.py          ← /auth/*
│   │   ├── admin.py         ← /admin/* (Lucky only)
│   │   ├── todos.py         ← /todos/*
│   │   ├── notes.py         ← /notes/*
│   │   ├── reminders.py     ← /reminders/*
│   │   ├── birthdays.py     ← /birthdays
│   │   └── websocket.py     ← /ws
│   ├── services/            ← Business logic
│   │   ├── ai_engine.py     ← Prompt builder + Groq streaming
│   │   ├── command_parser.py← Parse todos/reminders/notes
│   │   ├── memory_service.py← Tiered memory CRUD
│   │   ├── personality.py   ← Emotion + personality engine
│   │   ├── live_data.py     ← Weather/news/crypto/etc.
│   │   └── auth_service.py  ← bcrypt + JWT
│   ├── db/
│   │   ├── connection.py    ← asyncpg pool
│   │   ├── migrations/      ← SQL schema files
│   │   └── seed.py          ← Bootstrap family data
│   ├── middleware/
│   │   ├── auth_guard.py    ← require_auth, require_admin
│   │   └── rate_limiter.py  ← Brute-force protection
│   ├── models/              ← Pydantic request/response schemas
│   └── utils/
│       ├── family.py        ← Family data (single source)
│       ├── language.py      ← Telugu/Hindi detection
│       └── text.py          ← Text helpers
├── frontend/                ← Static UI (Phase 6)
├── config/
│   └── family.json          ← Family member definitions
├── tests/                   ← Test suite (Phase 8)
├── .env.example
├── requirements.txt
└── render.yaml
```

---

## Default Login Credentials

| Username     | Password           | Role    |
|--------------|--------------------|---------|
| lucky        | lucky@jarvis       | Admin   |
| krishna      | krishna@jarvis     | Father  |
| sangeetha    | sangeetha@jarvis   | Mother  |
| thapaswini   | thapu@jarvis       | Sister  |
| dhruva       | dhruva@jarvis      | Brother |
| prajwal      | prajwal@jarvis     | Brother |

> ⚠️ **Change all passwords after first login** via Admin Dashboard → Change Password.

---

## Security Notes

- Passwords are hashed with **bcrypt** (cost factor 12)
- Sessions use **JWT** with 7-day expiry
- Admin endpoints require valid admin token (server-side check)
- Login is rate-limited: 10 attempts per 60 seconds per IP
- Never commit `.env` to Git

---

*Built with ❤️ for the Battini family by Lucky.*
