-- =========================================================
-- 0. request_metrics 表
-- =========================================================
CREATE TABLE IF NOT EXISTS request_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    request_type VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL DEFAULT 'internal',
    status VARCHAR(32) NOT NULL DEFAULT 'success',
    session_id BIGINT NULL,
    doc_id BIGINT NULL,
    user_message_id BIGINT NULL,
    celery_task_id VARCHAR(128) NULL,
    top_k INT NULL,
    ttft_ms INT NULL,
    e2e_latency_ms INT NULL,
    ready_latency_ms INT NULL,
    retrieval_ms INT NULL,
    prompt_tokens INT NULL,
    completion_tokens INT NULL,
    embedding_tokens INT NULL,
    cost_usd DECIMAL(16, 8) NULL,
    citation_count INT NULL,
    no_context TINYINT(1) NOT NULL DEFAULT 0,
    timed_out TINYINT(1) NOT NULL DEFAULT 0,
    context_mode VARCHAR(32) NULL,
    answer_source VARCHAR(32) NULL,
    error_message TEXT NULL,
    extra_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_request_metrics_type_created (request_type, created_at),
    INDEX idx_request_metrics_status_created (status, created_at),
    INDEX idx_request_metrics_doc_created (doc_id, created_at),
    INDEX idx_request_metrics_session_created (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
