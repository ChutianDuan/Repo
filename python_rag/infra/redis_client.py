import redis
from python_rag.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
def get_redis_client():
    kwargs = {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": REDIS_DB,
        "decode_responses": True,
    }
    if REDIS_PASSWORD:
        kwargs["password"] = REDIS_PASSWORD
    return redis.Redis(**kwargs)