import re
from typing import Any, Dict, List, Optional, Tuple

from python_rag.app.core.config import RETRIEVAL_RERANK_TOP_K

from python_rag.app.agent.tools.base import (
    BaseTool,
    tool_error_result,
    tool_success_result,
)
from python_rag.app.agent.tools.registry import ToolRegistry, default_registry


KNOWLEDGE_SEARCH_TOOL_NAME = "knowledge_search"
DEFAULT_KNOWLEDGE_SEARCH_TOP_K = RETRIEVAL_RERANK_TOP_K
DEFAULT_CONTENT_MAX_CHARS = 800
DEFAULT_MAX_REWRITE_QUERIES = 4

_QUERY_SPLIT_RE = re.compile(r"[\s,，。！？!?；;：:、/\\|()（）\[\]【】{}<>《》]+")
_QUERY_SPACE_RE = re.compile(r"\s+")
_CJK_FILLER_RE = re.compile(
    r"(这个|那个|一下|请问|帮我|帮忙|如何|怎么|怎样|哪些|什么|是否|可以|能不能|"
    r"项目|系统|文档|资料|问题|困难问题|进行|实现|支持|关于)"
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "does",
    "for",
    "how",
    "is",
    "it",
    "of",
    "or",
    "the",
    "to",
    "what",
    "with",
}
_DOMAIN_EXPANSIONS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (
        ("网页", "网址", "链接", "url", "web", "html"),
        "网页 URL HTML 内容提取 解析 web document ingest",
    ),
    (
        ("embedding", "嵌入", "向量", "vector"),
        "embedding 向量 vector index LanceDB",
    ),
    (
        ("检索", "召回", "搜索", "retrieval", "recall", "search"),
        "retrieval recall search knowledge_search rerank",
    ),
    (
        ("上传", "导入", "文档上传", "upload"),
        "文档上传 upload document ingest storage",
    ),
    (
        ("解析", "提取", "抽取", "parse", "extract"),
        "解析 提取 parse extract chunk",
    ),
    (
        ("改写", "rewrite", "query"),
        "query rewrite expansion multi query recall",
    ),
    (
        ("agent", "智能体", "工具调用", "tool"),
        "agent orchestrator tool_call knowledge_search trace",
    ),
)


def get_document_by_id(doc_id):
    from python_rag.app.modules.documents.repo import get_document_by_id as repo_get_document_by_id

    return repo_get_document_by_id(doc_id)


def search_in_documents(**kwargs):
    from python_rag.app.retrieval.hybrid_service import (
        search_in_documents as retrieval_search_in_documents,
    )

    return retrieval_search_in_documents(**kwargs)


def _truncate_content(content: Any, max_chars: int = DEFAULT_CONTENT_MAX_CHARS) -> str:
    text = str(content or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def _safe_score(value: Any) -> float:
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return 0.0


def _normalize_top_k(value: Any) -> int:
    if value is None or value == "":
        return DEFAULT_KNOWLEDGE_SEARCH_TOP_K
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        return DEFAULT_KNOWLEDGE_SEARCH_TOP_K
    return min(20, max(1, top_k))


def _normalize_query_text(query: str) -> str:
    return _QUERY_SPACE_RE.sub(" ", str(query or "").strip())


def _append_unique(values: List[str], value: str) -> None:
    normalized = _normalize_query_text(value)
    if normalized and normalized not in values:
        values.append(normalized)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _build_keyword_query(query: str) -> str:
    normalized = _normalize_query_text(query)
    if not normalized:
        return ""

    simplified = _CJK_FILLER_RE.sub(" ", normalized)
    tokens: List[str] = []
    seen = set()
    for token in _QUERY_SPLIT_RE.split(simplified):
        token = token.strip("._-").strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in _STOPWORDS:
            continue
        if len(lowered) <= 1 and not _contains_cjk(token):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        tokens.append(token)
        if len(tokens) >= 12:
            break

    return " ".join(tokens).strip()


def build_rewritten_queries(
    query: str,
    max_queries: int = DEFAULT_MAX_REWRITE_QUERIES,
) -> List[str]:
    normalized = _normalize_query_text(query)
    if not normalized:
        return []

    max_queries = max(1, int(max_queries or DEFAULT_MAX_REWRITE_QUERIES))
    queries: List[str] = []
    _append_unique(queries, normalized)

    keyword_query = _build_keyword_query(normalized)
    if keyword_query and keyword_query != normalized:
        _append_unique(queries, keyword_query)

    lowered_query = normalized.lower()
    base_query = keyword_query or normalized
    for triggers, expansion in _DOMAIN_EXPANSIONS:
        if len(queries) >= max_queries:
            break
        if any(trigger.lower() in lowered_query for trigger in triggers):
            _append_unique(queries, "{0} {1}".format(base_query, expansion))

    return queries[:max_queries]


def _hit_key(hit: Dict[str, Any]) -> Tuple[str, Any]:
    chunk_id = hit.get("chunk_id")
    if chunk_id is not None:
        return ("chunk_id", chunk_id)

    doc_id = hit.get("doc_id")
    chunk_index = hit.get("chunk_index")
    if doc_id is not None and chunk_index is not None:
        return ("doc_chunk", "{0}:{1}".format(doc_id, chunk_index))

    content = str(hit.get("content") or hit.get("snippet") or "")
    return ("content", content[:300])


def _hit_rank_score(hit: Dict[str, Any]) -> float:
    return max(
        _safe_score(hit.get("rerank_score")),
        _safe_score(hit.get("score")),
        _safe_score(hit.get("lancedb_score")),
    )


def _merge_route_hits(route_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    for route_hit in route_hits:
        route_index = int(route_hit.get("_route_index") or 0)
        route_query = str(route_hit.get("_route_query") or "")
        hit = dict(route_hit)
        key = _hit_key(hit)
        score = _hit_rank_score(hit)
        existing = merged.get(key)

        if existing is None:
            hit["matched_queries"] = [route_query] if route_query else []
            hit["retrieval_routes"] = [route_index]
            hit["route_score"] = score
            hit["_best_route_index"] = route_index
            merged[key] = hit
            continue

        matched_queries = existing.setdefault("matched_queries", [])
        if route_query and route_query not in matched_queries:
            matched_queries.append(route_query)

        retrieval_routes = existing.setdefault("retrieval_routes", [])
        if route_index not in retrieval_routes:
            retrieval_routes.append(route_index)

        if score > float(existing.get("route_score") or 0):
            hit["matched_queries"] = matched_queries
            hit["retrieval_routes"] = retrieval_routes
            hit["route_score"] = score
            hit["_best_route_index"] = route_index
            merged[key] = hit

    return sorted(
        merged.values(),
        key=lambda item: (
            -float(item.get("route_score") or 0),
            int(item.get("_best_route_index") or 0),
        ),
    )


def _build_retrieval_detail(search_result: Dict[str, Any]) -> Dict[str, Any]:
    metrics = search_result.get("metrics") or {}
    rerank = metrics.get("rerank") or {}
    return {
        "provider": metrics.get("recall_provider"),
        "dense_top_k": metrics.get("candidate_top_k"),
        "rerank_top_k": metrics.get("final_top_k"),
        "candidate_count": metrics.get("candidate_count"),
        "lancedb_candidate_count": metrics.get("lancedb_candidate_count"),
        "mysql_hydrated_candidate_count": metrics.get("mysql_hydrated_candidate_count"),
        "vector_search_latency_ms": metrics.get("lancedb_ms"),
        "rerank_latency_ms": metrics.get("rerank_ms"),
        "retrieval_latency_ms": metrics.get("retrieval_ms"),
        "rerank_used": rerank.get("used"),
        "rerank_model": rerank.get("model"),
        "rerank_provider": rerank.get("provider"),
    }


def _build_multi_route_retrieval_detail(
    *,
    queries: List[str],
    route_results: List[Dict[str, Any]],
    route_errors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    primary_result = route_results[0]["result"] if route_results else {}
    detail = _build_retrieval_detail(primary_result)
    detail["query_rewrite"] = {
        "enabled": len(queries) > 1,
        "queries": queries,
        "route_count": len(queries),
        "successful_route_count": len(route_results),
        "failed_route_count": len(route_errors),
        "errors": route_errors,
    }
    detail["route_metrics"] = [
        {
            "query": item["query"],
            "route_index": item["route_index"],
            "hit_count": len((item.get("result") or {}).get("hits") or []),
            "metrics": (item.get("result") or {}).get("metrics") or {},
        }
        for item in route_results
    ]
    return detail


def _is_nonrecoverable_search_error(error_message: str) -> bool:
    lowered = str(error_message or "").lower()
    return any(
        marker in lowered
        for marker in (
            "no ready document index",
            "document index not found",
            "document index embedding mismatch",
            "re-ingest the document",
        )
    )


class KnowledgeSearchTool(BaseTool):
    name = KNOWLEDGE_SEARCH_TOOL_NAME
    description = "Search the ready knowledge base and return the most relevant chunks."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "User question or rewritten retrieval query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of chunks to return.",
                "default": DEFAULT_KNOWLEDGE_SEARCH_TOP_K,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    timeout_ms = 30000
    permission_level = "readonly"

    def __init__(
        self,
        max_content_chars: int = DEFAULT_CONTENT_MAX_CHARS,
        **kwargs,
    ):
        self.max_content_chars = max_content_chars
        super().__init__(**kwargs)

    def _get_title(self, doc_id: Optional[int], title_cache: Dict[int, str]) -> str:
        if doc_id is None:
            return ""
        if doc_id in title_cache:
            return title_cache[doc_id]

        title = ""
        try:
            document = get_document_by_id(doc_id)
            title = (document or {}).get("filename") or ""
        except Exception:
            title = ""

        title_cache[doc_id] = title
        return title

    def _format_hit(self, hit: Dict[str, Any], title_cache: Dict[int, str]) -> Dict[str, Any]:
        doc_id = hit.get("doc_id")
        try:
            document_id = int(doc_id) if doc_id is not None else None
        except (TypeError, ValueError):
            document_id = None

        return {
            "chunk_id": hit.get("chunk_id"),
            "chunk_index": hit.get("chunk_index"),
            "doc_id": document_id,
            "document_id": document_id,
            "title": self._get_title(document_id, title_cache),
            "content": _truncate_content(
                hit.get("content") or hit.get("snippet") or "",
                self.max_content_chars,
            ),
            "snippet": hit.get("snippet") or "",
            "score": _safe_score(hit.get("score")),
            "lancedb_score": _safe_score(hit.get("lancedb_score")),
            "rerank_score": _safe_score(hit.get("rerank_score")),
            "route_score": _safe_score(hit.get("route_score")),
            "lancedb_rank": hit.get("lancedb_rank"),
            "original_rank": hit.get("original_rank"),
            "matched_queries": hit.get("matched_queries") or [],
            "retrieval_routes": hit.get("retrieval_routes") or [],
        }

    async def run(self, arguments: dict) -> dict:
        arguments = arguments or {}
        query = str(arguments.get("query") or "").strip()
        top_k = _normalize_top_k(arguments.get("top_k"))

        if not query:
            return tool_error_result(
                "query is required",
                {
                    "results": [],
                    "total": 0,
                },
            )

        try:
            queries = build_rewritten_queries(query)
            route_hits: List[Dict[str, Any]] = []
            route_results: List[Dict[str, Any]] = []
            route_errors: List[Dict[str, Any]] = []

            for route_index, route_query in enumerate(queries):
                try:
                    search_result = search_in_documents(
                        query=route_query,
                        top_k=top_k,
                        track_metric=route_index == 0,
                    )
                except Exception as exc:
                    error_message = str(exc)
                    route_errors.append(
                        {
                            "query": route_query,
                            "route_index": route_index,
                            "error": error_message,
                        }
                    )
                    if route_index == 0 and _is_nonrecoverable_search_error(error_message):
                        break
                    continue

                route_results.append(
                    {
                        "query": route_query,
                        "route_index": route_index,
                        "result": search_result,
                    }
                )
                for hit in search_result.get("hits") or []:
                    if not isinstance(hit, dict):
                        continue
                    route_hit = dict(hit)
                    route_hit["_route_index"] = route_index
                    route_hit["_route_query"] = route_query
                    route_hits.append(route_hit)

            if not route_results and route_errors:
                first_error = route_errors[0]["error"]
                return tool_error_result(
                    first_error,
                    {
                        "results": [],
                        "total": 0,
                    },
                )

            hits = _merge_route_hits(route_hits)
            title_cache: Dict[int, str] = {}
            results = [
                self._format_hit(hit, title_cache)
                for hit in hits[:top_k]
            ]
            return tool_success_result(
                {
                    "results": results,
                    "total": len(results),
                    "retrieval": _build_multi_route_retrieval_detail(
                        queries=queries,
                        route_results=route_results,
                        route_errors=route_errors,
                    ),
                }
            )
        except Exception as exc:
            return tool_error_result(
                str(exc),
                {
                    "results": [],
                    "total": 0,
                },
            )


def register_knowledge_tools(registry: ToolRegistry = default_registry) -> ToolRegistry:
    registry.register(KnowledgeSearchTool(), overwrite=True)
    return registry


register_knowledge_tools()


__all__ = [
    "DEFAULT_CONTENT_MAX_CHARS",
    "DEFAULT_KNOWLEDGE_SEARCH_TOP_K",
    "DEFAULT_MAX_REWRITE_QUERIES",
    "KNOWLEDGE_SEARCH_TOOL_NAME",
    "KnowledgeSearchTool",
    "build_rewritten_queries",
    "register_knowledge_tools",
]
