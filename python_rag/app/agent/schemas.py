from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentRunStatus(object):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentStepStatus(object):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AgentToolCallStatus(object):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AgentRunCreate(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=128)
    agent_version: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=128)
    status: str = Field(AgentRunStatus.RUNNING, max_length=32)
    session_id: Optional[int] = Field(default=None, gt=0)
    user_message_id: Optional[int] = Field(default=None, gt=0)
    input: Optional[Any] = None
    output: Optional[Any] = None
    meta: Optional[Any] = None
    prompt_tokens: Optional[int] = Field(default=None, ge=0)
    completion_tokens: Optional[int] = Field(default=None, ge=0)
    total_tokens: Optional[int] = Field(default=None, ge=0)
    cost_usd: Optional[float] = Field(default=None, ge=0)
    error_message: Optional[str] = None


class AgentRunRead(AgentRunCreate):
    id: int
    total_steps: int = 0
    total_tool_calls: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentStepCreate(BaseModel):
    run_id: int = Field(..., gt=0)
    step_index: int = Field(..., ge=0)
    step_type: str = Field("decision", min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=128)
    status: str = Field(AgentStepStatus.RUNNING, max_length=32)
    model: Optional[str] = Field(default=None, max_length=128)
    input: Optional[Any] = None
    reasoning_summary: Optional[str] = None
    decision: Optional[str] = None
    output: Optional[Any] = None
    prompt_tokens: Optional[int] = Field(default=None, ge=0)
    completion_tokens: Optional[int] = Field(default=None, ge=0)
    total_tokens: Optional[int] = Field(default=None, ge=0)
    latency_ms: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = None


class AgentStepRead(AgentStepCreate):
    id: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentToolCallCreate(BaseModel):
    run_id: int = Field(..., gt=0)
    step_id: int = Field(..., gt=0)
    tool_name: str = Field(..., min_length=1, max_length=128)
    tool_call_id: Optional[str] = Field(default=None, max_length=128)
    status: str = Field(AgentToolCallStatus.RUNNING, max_length=32)
    arguments: Optional[Any] = None
    result: Optional[Any] = None
    result_preview: Optional[str] = None
    latency_ms: Optional[int] = Field(default=None, ge=0)
    error_message: Optional[str] = None


class AgentToolCallRead(AgentToolCallCreate):
    id: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentChatRequest(BaseModel):
    session_id: int = Field(..., gt=0)
    message: str = Field(..., min_length=1)
    stream: bool = False
    trace_id: Optional[str] = Field(default=None, max_length=128)

