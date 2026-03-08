"""
JARVIS — Config & Environment Validation
Loads all environment variables at startup. Fails loudly if required vars are missing.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Required ─────────────────────────────────────────────
GROQ_API_KEY:    str = os.getenv("GROQ_API_KEY", "")
DATABASE_URL:    str = os.getenv("DATABASE_URL", "")
JWT_SECRET:      str = os.getenv("JWT_SECRET", "")

# ── Optional / Defaults ───────────────────────────────────
ENVIRONMENT:     str = os.getenv("ENVIRONMENT", "development")
RENDER_URL:      str = os.getenv("RENDER_EXTERNAL_URL", "")
JWT_EXPIRE_DAYS: int = int(os.getenv("JWT_EXPIRE_DAYS", "7"))
MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "10"))
RATE_LIMIT_WINDOW:  int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))   # seconds

# Model names
MODEL_CHAT:   str = os.getenv("MODEL_CHAT",   "llama-3.3-70b-versatile")
MODEL_FAST:   str = os.getenv("MODEL_FAST",   "llama-3.1-8b-instant")
MODEL_VISION: str = os.getenv("MODEL_VISION", "meta-llama/llama-4-scout-17b-16e-instruct")

IS_PRODUCTION: bool = (ENVIRONMENT == "production")

REQUIRED = {
    "GROQ_API_KEY": GROQ_API_KEY,
    "DATABASE_URL":  DATABASE_URL,
    "JWT_SECRET":    JWT_SECRET,
}

def validate():
    """Call once at startup — exits the process if any required var is missing."""
    missing = [k for k, v in REQUIRED.items() if not v]
    if missing:
        print(f"❌  FATAL: Missing required environment variables: {', '.join(missing)}")
        print("    Please set them in your .env file or Render dashboard.")
        sys.exit(1)
    print(f"✅  Config validated — environment={ENVIRONMENT}, model={MODEL_CHAT}")
