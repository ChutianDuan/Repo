from typing import Optional

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    ok: bool
    code: Optional[int] = None
    message: Optional[str] = None


class HealthData(BaseModel):
    ok: bool
    mysql: DependencyHealth
    redis: DependencyHealth
