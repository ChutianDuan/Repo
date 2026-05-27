-- Agent observability tables.
-- agent_runs records one complete Agent execution.
-- agent_steps records the ordered decisions made during a run.
-- agent_tool_calls records concrete tool invocations made by a step.

CREATE TABLE IF NOT EXISTS agent_runs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(128) NULL,
    agent_name VARCHAR(128) NOT NULL,
    agent_version VARCHAR(64) NULL,
    model VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'RUNNING',
    session_id BIGINT NULL,
    user_message_id BIGINT NULL,
    input_json JSON NULL,
    output_json JSON NULL,
    meta_json JSON NULL,
    total_steps INT NOT NULL DEFAULT 0,
    total_tool_calls INT NOT NULL DEFAULT 0,
    prompt_tokens INT NULL,
    completion_tokens INT NULL,
    total_tokens INT NULL,
    cost_usd DECIMAL(16, 8) NULL,
    error_message TEXT NULL,
    started_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_runs_trace (trace_id),
    INDEX idx_agent_runs_status_created (status, created_at),
    INDEX idx_agent_runs_agent_started (agent_name, started_at),
    INDEX idx_agent_runs_session_created (session_id, created_at),
    INDEX idx_agent_runs_message (user_message_id),
    CONSTRAINT fk_agent_runs_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_agent_runs_user_message
        FOREIGN KEY (user_message_id) REFERENCES messages(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_steps (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id BIGINT NOT NULL,
    step_index INT NOT NULL,
    step_type VARCHAR(64) NOT NULL DEFAULT 'decision',
    name VARCHAR(128) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'RUNNING',
    model VARCHAR(128) NULL,
    input_json JSON NULL,
    reasoning_summary TEXT NULL,
    decision TEXT NULL,
    output_json JSON NULL,
    prompt_tokens INT NULL,
    completion_tokens INT NULL,
    total_tokens INT NULL,
    latency_ms INT NULL,
    error_message TEXT NULL,
    started_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_agent_steps_run_step (run_id, step_index),
    UNIQUE KEY uk_agent_steps_run_id (run_id, id),
    INDEX idx_agent_steps_run_created (run_id, created_at),
    INDEX idx_agent_steps_status_created (status, created_at),
    CONSTRAINT fk_agent_steps_run
        FOREIGN KEY (run_id) REFERENCES agent_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    run_id BIGINT NOT NULL,
    step_id BIGINT NOT NULL,
    tool_call_id VARCHAR(128) NULL,
    tool_name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'RUNNING',
    arguments_json JSON NULL,
    result_json JSON NULL,
    result_preview TEXT NULL,
    latency_ms INT NULL,
    error_message TEXT NULL,
    started_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_tool_calls_run_created (run_id, created_at),
    INDEX idx_agent_tool_calls_step_created (step_id, created_at),
    INDEX idx_agent_tool_calls_tool_created (tool_name, created_at),
    INDEX idx_agent_tool_calls_status_created (status, created_at),
    CONSTRAINT fk_agent_tool_calls_step
        FOREIGN KEY (run_id, step_id) REFERENCES agent_steps(run_id, id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
