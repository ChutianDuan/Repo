# python_rag/core/errors.py

class AppError(Exception):
    def __init__(self, code, message, http_status=400, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


class InvalidRequestError(AppError):
    pass


class SessionNotFoundError(AppError):
    pass


class MessageNotFoundError(AppError):
    pass


class DocumentNotFoundError(AppError):
    pass


class IndexNotFoundError(AppError):
    pass


class LLMTimeoutError(AppError):
    pass


class LLMServiceError(AppError):
    pass


class RetrievalServiceError(AppError):
    pass