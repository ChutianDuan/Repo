USE ai_app;

-- =========================================================
-- 0. 给 messages 补 meta_json 字段（如果还没有）
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE messages ADD COLUMN meta_json JSON NULL AFTER status',
        'SELECT ''skip: messages.meta_json exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'messages'
      AND COLUMN_NAME = 'meta_json'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 1. 给 documents.user_id 补索引（如果还没有）
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE documents ADD INDEX idx_documents_user (user_id)',
        'SELECT ''skip: idx_documents_user exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'documents'
      AND INDEX_NAME = 'idx_documents_user'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 2. documents.user_id -> user_account.id
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE documents
            ADD CONSTRAINT fk_documents_user
            FOREIGN KEY (user_id) REFERENCES user_account(id)
            ON DELETE CASCADE',
        'SELECT ''skip: fk_documents_user exists'''
    )
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'documents'
      AND CONSTRAINT_NAME = 'fk_documents_user'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 3. doc_chunks.doc_id -> documents.id
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE doc_chunks
            ADD CONSTRAINT fk_doc_chunks_doc
            FOREIGN KEY (doc_id) REFERENCES documents(id)
            ON DELETE CASCADE',
        'SELECT ''skip: fk_doc_chunks_doc exists'''
    )
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'doc_chunks'
      AND CONSTRAINT_NAME = 'fk_doc_chunks_doc'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 4. citations.doc_id -> documents.id
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE citations
            ADD CONSTRAINT fk_citations_doc
            FOREIGN KEY (doc_id) REFERENCES documents(id)
            ON DELETE CASCADE',
        'SELECT ''skip: fk_citations_doc exists'''
    )
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'citations'
      AND CONSTRAINT_NAME = 'fk_citations_doc'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;


-- =========================================================
-- 5. citations.chunk_id -> doc_chunks.id
-- =========================================================
SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE citations
            ADD CONSTRAINT fk_citations_chunk
            FOREIGN KEY (chunk_id) REFERENCES doc_chunks(id)
            ON DELETE CASCADE',
        'SELECT ''skip: fk_citations_chunk exists'''
    )
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'citations'
      AND CONSTRAINT_NAME = 'fk_citations_chunk'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;