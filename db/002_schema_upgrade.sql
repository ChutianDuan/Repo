-- =========================================================
-- 0. 补 documents.updated_at
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE documents
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
            AFTER created_at',
        'SELECT ''skip: documents.updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'documents'
      AND COLUMN_NAME = 'updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 1. 补 tasks.updated_at
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE tasks
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
            AFTER created_at',
        'SELECT ''skip: tasks.updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'tasks'
      AND COLUMN_NAME = 'updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 2. 补 document_indexes.updated_at
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE document_indexes
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
            AFTER created_at',
        'SELECT ''skip: document_indexes.updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'document_indexes'
      AND COLUMN_NAME = 'updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 3. 补 sessions.updated_at
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE sessions
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
            AFTER created_at',
        'SELECT ''skip: sessions.updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sessions'
      AND COLUMN_NAME = 'updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 4. 补 messages.updated_at
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE messages
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
            AFTER created_at',
        'SELECT ''skip: messages.updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'messages'
      AND COLUMN_NAME = 'updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 5. tasks(state, updated_at) 索引
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE tasks ADD INDEX idx_tasks_state_updated (state, updated_at)',
        'SELECT ''skip: idx_tasks_state_updated exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'tasks'
      AND INDEX_NAME = 'idx_tasks_state_updated'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 6. sessions(user_id, updated_at) 索引
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE sessions ADD INDEX idx_sessions_user_updated (user_id, updated_at)',
        'SELECT ''skip: idx_sessions_user_updated exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'sessions'
      AND INDEX_NAME = 'idx_sessions_user_updated'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;
