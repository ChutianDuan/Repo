CREATE DATABASE IF NOT EXISTS ai_app
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE ai_app;

CREATE TABLE IF NOT EXISTS user_account (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    filename VARCHAR(512) NOT NULL,
    mime VARCHAR(128) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    storage_path VARCHAR(1024) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'UPLOADED',
    error_message TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_documents_user_sha256 (user_id, sha256),
    INDEX idx_documents_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS doc_chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id BIGINT NOT NULL,
    chunk_index INT NOT NULL,
    text LONGTEXT NOT NULL,
    tokens_est INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_doc_chunks_doc_chunk_index (doc_id, chunk_index),
    INDEX idx_doc_chunks_doc (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    celery_task_id VARCHAR(128) NOT NULL,
    type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id BIGINT NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    progress INT NOT NULL DEFAULT 0,
    meta_json JSON NULL,
    error TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_tasks_celery_task_id (celery_task_id),
    INDEX idx_tasks_entity (entity_type, entity_id),
    INDEX idx_tasks_state_updated (state, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS document_indexes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id BIGINT NOT NULL UNIQUE,
    index_type VARCHAR(64) NOT NULL DEFAULT 'faiss_flat_ip',
    embedding_model VARCHAR(128) NOT NULL,
    dimension INT NOT NULL,
    index_path VARCHAR(512) NOT NULL,
    mapping_path VARCHAR(512) NOT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'READY',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_document_indexes_doc
        FOREIGN KEY (doc_id) REFERENCES documents(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;



CREATE TABLE IF NOT EXISTS sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT 'New Session',
    summary TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sessions_user_updated (user_id, updated_at),
    CONSTRAINT fk_sessions_user
        FOREIGN KEY (user_id) REFERENCES user_account(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;




CREATE TABLE IF NOT EXISTS messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT NOT NULL,
    role VARCHAR(32) NOT NULL,
    content LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_messages_session_created (session_id, created_at),
    CONSTRAINT fk_messages_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE messages
ADD COLUMN meta_json JSON NULL AFTER status;

CREATE TABLE IF NOT EXISTS citations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    message_id BIGINT NOT NULL,
    doc_id BIGINT NOT NULL,
    chunk_id BIGINT NOT NULL,
    chunk_index INT NOT NULL,
    score DOUBLE NOT NULL DEFAULT 0,
    snippet TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_citations_message (message_id),
    INDEX idx_citations_doc_chunk (doc_id, chunk_id),
    CONSTRAINT fk_citations_message
        FOREIGN KEY (message_id) REFERENCES messages(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;