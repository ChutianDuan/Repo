CREATE TABLE IF NOT EXISTS vector_index_jobs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id BIGINT NOT NULL,
    celery_task_id VARCHAR(128) NULL,
    provider VARCHAR(64) NOT NULL DEFAULT 'lancedb',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    chunk_count INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    meta_json JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_vector_index_jobs_doc (doc_id),
    INDEX idx_vector_index_jobs_status_updated (status, updated_at),
    CONSTRAINT fk_vector_index_jobs_doc
        FOREIGN KEY (doc_id) REFERENCES documents(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
