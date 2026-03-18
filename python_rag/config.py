from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(os.path.join(ENV_PATH))

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "ai_app")
MYSQL_USER = os.getenv("MYSQL_USER", "ai_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ai_password")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# App Configuration
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_DEBUG = os.getenv("APP_DEBUG", "true").lower() == "true"
APP_NAME = os.getenv("APP_NAME", "AI Project API")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

# log_dir
LOG_DIR = BASE_DIR/"logs"
LOG_DIR.mkdir(exist_ok=True)
