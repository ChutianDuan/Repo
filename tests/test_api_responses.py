from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from python_rag.app.core.exception_handlers import (
    http_exception_handler,
    request_validation_error_handler,
)


class _RequestBody(BaseModel):
    count: int = Field(..., gt=0)


def _build_client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.post("/items")
    def create_item(body: _RequestBody):
        return body

    return TestClient(app)


def test_validation_errors_use_api_envelope():
    response = _build_client().post("/items", json={"count": 0})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == 4000
    assert payload["message"] == "request validation failed"
    assert payload["data"]["errors"]


def test_http_errors_use_api_envelope():
    response = _build_client().get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "code": 4000,
        "message": "Not Found",
        "data": None,
    }
