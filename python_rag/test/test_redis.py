from pathlib import Path
import os

import redis
from dotenv import load_dotenv

def main():
    # 加载环境变量
    repo_dir = Path(__file__).resolve().parent.parent.parent
    env_path = repo_dir / '.env'
    load_dotenv(dotenv_path=env_path)

    # 初始化链接
    redis_conn = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True,
    )
    pong = redis_conn.ping()
    redis_conn.set("day2:test:key", "Hello, Redis!")
    value = redis_conn.get("day2:test:key")

    print("Redis connection successful:", pong)
    print("Value from Redis:", value)

if __name__ == "__main__":
    main()

    