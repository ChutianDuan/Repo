from ..constants import SUCCESS
from ..logger import logger


def rag_query_service(query: str):
    q = query.strip().lower()

    if "redis" in q:
        answer = "Redis 是一个基于内存的高性能键值数据库，常用于缓存、会话存储、分布式锁、消息队列等场景。"
        sources = ["mock_doc_redis_intro", "mock_doc_cache_basics"]
    elif "mysql" in q:
        answer = "MySQL 是一个关系型数据库管理系统，适合存储结构化数据，支持 SQL 查询、事务和索引。"
        sources = ["mock_doc_mysql_intro"]
    elif "rag" in q:
        answer = "RAG 是检索增强生成，通过先检索相关资料，再让大模型基于检索结果生成回答，以降低幻觉并增强可追溯性。"
        sources = ["mock_doc_rag_overview"]
    else:
        answer = f"这是一个 mock RAG 响应，你的问题是：{query}"
        sources = ["mock_doc_default"]

    logger.info("RAG mock query success: query=%s", query)

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
    }