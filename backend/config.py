import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "jarvis-secret-key-change-in-production")
    JWT_EXPIRE_DAYS: int = 7

    # Model config
    MODEL_CHAT: str = "llama-3.1-8b-instant"
    MODEL_PLANNER: str = "llama-3.1-8b-instant"
    MODEL_ANALYSIS: str = "llama-3.1-8b-instant"

    # Memory config
    HOT_MEMORY_LIMIT: int = 15
    WARM_SUMMARY_DAYS: int = 7
    COLD_FACTS_LIMIT: int = 10
    MESSAGE_RETENTION_DAYS: int = 30
    IMPORTANCE_THRESHOLD: float = 0.25

    # Performance config
    MAX_TOKENS_CASUAL: int = 500
    MAX_TOKENS_DETAILED: int = 900
    MAX_TOKENS_PLANNER: int = 150
    TEMPERATURE: float = 0.75

    # Safety config
    MAX_INPUT_LENGTH: int = 2000
    MAX_REQUESTS_PER_MINUTE: int = 20

config = Config()
