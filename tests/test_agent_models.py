import json

from python_rag.app.agent import models as agent_models


class FakeCursor:
    def __init__(self):
        self.lastrowid = 42
        self.executions = []
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        self.executions.append((sql, params))


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def test_create_agent_run_writes_insert_payload(monkeypatch):
    cursor = FakeCursor()
    conn = FakeConnection(cursor)
    monkeypatch.setattr(agent_models, "get_mysql_connection", lambda: conn)

    run_id = agent_models.create_agent_run(
        agent_name="rag-agent",
        trace_id="trace-1",
        model="glm-test",
        input_data={"question": "hello"},
        meta={"source": "unit-test"},
    )

    assert run_id == 42
    assert "INSERT INTO agent_runs" in cursor.sql
    assert cursor.params[0] == "trace-1"
    assert cursor.params[1] == "rag-agent"
    assert cursor.params[3] == "glm-test"
    assert json.loads(cursor.params[7]) == {"question": "hello"}
    assert json.loads(cursor.params[9]) == {"source": "unit-test"}
    assert conn.closed

def test_create_agent_step_increments_run_step_count(monkeypatch):
    cursor = FakeCursor()
    conn = FakeConnection(cursor)
    monkeypatch.setattr(agent_models, "get_mysql_connection", lambda: conn)

    step_id = agent_models.create_agent_step(
        run_id=7,
        step_index=0,
        decision="call retrieval",
    )

    assert step_id == 42
    assert "INSERT INTO agent_steps" in cursor.executions[0][0]
    assert "SET total_steps=total_steps + 1" in cursor.executions[1][0]
    assert cursor.executions[1][1] == (7,)


def test_create_agent_tool_call_increments_run_tool_call_count(monkeypatch):
    cursor = FakeCursor()
    conn = FakeConnection(cursor)
    monkeypatch.setattr(agent_models, "get_mysql_connection", lambda: conn)

    tool_call_id = agent_models.create_agent_tool_call(
        run_id=7,
        step_id=42,
        tool_name="retrieval.search",
        arguments={"query": "hello"},
    )

    assert tool_call_id == 42
    assert "INSERT INTO agent_tool_calls" in cursor.executions[0][0]
    assert "SET total_tool_calls=total_tool_calls + 1" in cursor.executions[1][0]
    assert cursor.executions[1][1] == (7,)
