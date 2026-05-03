from python_rag.core.error_codes import (
    ERR_DB_ERROR,
    ERR_INTERNAL_ERROR,
    ERR_LLM_TIMEOUT,
    ERR_REDIS_ERROR,
    ERR_RETRIEVAL_TIMEOUT,
    ERR_UPSTREAM_HTTP_ERROR,
)


def default_http_status_for_code(code):
    if code in (ERR_DB_ERROR, ERR_REDIS_ERROR, ERR_INTERNAL_ERROR):
        return 500
    if code == ERR_UPSTREAM_HTTP_ERROR:
        return 502
    if code in (ERR_LLM_TIMEOUT, ERR_RETRIEVAL_TIMEOUT):
        return 504
    return 400


class AppError(Exception):
    def __init__(self, code, message, http_status=None, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status or default_http_status_for_code(code)
        self.data = data


class InvalidRequestError(AppError):
    pass


class SessionNotFoundError(AppError):
    def __init__(self, code, message, http_status=404, data=None):
        super().__init__(code, message, http_status=http_status, data=data)


class MessageNotFoundError(AppError):
    def __init__(self, code, message, http_status=404, data=None):
        super().__init__(code, message, http_status=http_status, data=data)


class DocumentNotFoundError(AppError):
    def __init__(self, code, message, http_status=404, data=None):
        super().__init__(code, message, http_status=http_status, data=data)


class IndexNotFoundError(AppError):
    def __init__(self, code, message, http_status=404, data=None):
        super().__init__(code, message, http_status=http_status, data=data)


class LLMTimeoutError(AppError):
    pass


class LLMServiceError(AppError):
    pass


class RetrievalServiceError(AppError):
    pass
