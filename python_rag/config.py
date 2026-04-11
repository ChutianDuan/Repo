import os

from dotenv import load_dotenv


load_dotenv()
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ai_app")
MYSQL_USER = os.getenv("MYSQL_USER", "ai_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ai_password")

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

STORAGE_ROOT = os.getenv("STORAGE_ROOT", "./data")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./data/uploads")

REDIS_URL = "redis://{host}:{port}/{db}".format(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
)

if REDIS_PASSWORD:
    REDIS_URL = "redis://:{password}@{host}:{port}/{db}".format(
        password=REDIS_PASSWORD,
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
    )

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

CHAT_MAX_CHUNK_CHARS = int(os.getenv("CHAT_MAX_CHUNK_CHARS", "1000"))
CHAT_TOP_K = int(os.getenv("CHAT_TOP_K", "5"))
CHAT_MIN_RETRIEVAL_SCORE = float(os.getenv("CHAT_MIN_RETRIEVAL_SCORE", "0.0"))
STREAM_DELTA_CHARS = int(os.getenv("STREAM_DELTA_CHARS", "20"))
STREAM_MOCK_DELAY_MS = int(os.getenv("STREAM_MOCK_DELAY_MS", "30"))

LLM_ENABLE = os.getenv("LLM_ENABLE", "true").lower() in ("1", "true", "yes", "on")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai_compatible")

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://open.bigmodel.cn/api/paas/v4",
).rstrip("/")

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()

LLM_MODEL = os.getenv("LLM_MODEL", "glm-4.7-flash")

LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
CHAT_ENABLE_MOCK_FALLBACK = os.getenv(
    "CHAT_ENABLE_MOCK_FALLBACK",
    "true",
).lower() in ("1", "true", "yes", "on")
