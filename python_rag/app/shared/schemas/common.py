from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TimestampMixin(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
