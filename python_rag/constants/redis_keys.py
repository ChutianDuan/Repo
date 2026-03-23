# python_rag/constants/redis_keys.py

def task_cache_key(task_id):
    return "task:cache:{0}".format(task_id)


def doc_lock_key(doc_id):
    return "lock:doc:{0}".format(doc_id)