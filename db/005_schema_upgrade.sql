-- =========================================================
-- 0. 用户长期记忆字段
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_account
            ADD COLUMN memory_summary TEXT NULL
            AFTER username',
        'SELECT ''skip: user_account.memory_summary exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_account'
      AND COLUMN_NAME = 'memory_summary'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 1. 用户记忆已处理消息水位线
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_account
            ADD COLUMN memory_message_id BIGINT NULL
            AFTER memory_summary',
        'SELECT ''skip: user_account.memory_message_id exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_account'
      AND COLUMN_NAME = 'memory_message_id'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 2. 用户记忆更新时间
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_account
            ADD COLUMN memory_updated_at TIMESTAMP NULL
            AFTER memory_message_id',
        'SELECT ''skip: user_account.memory_updated_at exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_account'
      AND COLUMN_NAME = 'memory_updated_at'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 3. 用户记忆水位线索引
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_account ADD INDEX idx_user_account_memory_message (memory_message_id)',
        'SELECT ''skip: idx_user_account_memory_message exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_account'
      AND INDEX_NAME = 'idx_user_account_memory_message'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;
