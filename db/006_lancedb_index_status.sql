-- =========================================================
-- LanceDB indexing status fields
-- =========================================================

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE documents
            ADD COLUMN index_status VARCHAR(32) NOT NULL DEFAULT ''not_indexed''
            AFTER status',
        'SELECT ''skip: documents.index_status exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'documents'
      AND COLUMN_NAME = 'index_status'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE documents ADD INDEX idx_documents_index_status_created (index_status, created_at)',
        'SELECT ''skip: idx_documents_index_status_created exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'documents'
      AND INDEX_NAME = 'idx_documents_index_status_created'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE doc_chunks
            ADD COLUMN embedding_status VARCHAR(32) NOT NULL DEFAULT ''pending''
            AFTER tokens_est',
        'SELECT ''skip: doc_chunks.embedding_status exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'doc_chunks'
      AND COLUMN_NAME = 'embedding_status'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE doc_chunks
            ADD COLUMN vector_index_status VARCHAR(32) NOT NULL DEFAULT ''pending''
            AFTER embedding_status',
        'SELECT ''skip: doc_chunks.vector_index_status exists'''
    )
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'doc_chunks'
      AND COLUMN_NAME = 'vector_index_status'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE doc_chunks ADD INDEX idx_doc_chunks_embedding_status (embedding_status)',
        'SELECT ''skip: idx_doc_chunks_embedding_status exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'doc_chunks'
      AND INDEX_NAME = 'idx_doc_chunks_embedding_status'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE doc_chunks ADD INDEX idx_doc_chunks_vector_index_status (vector_index_status)',
        'SELECT ''skip: idx_doc_chunks_vector_index_status exists'''
    )
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'doc_chunks'
      AND INDEX_NAME = 'idx_doc_chunks_vector_index_status'
);
PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

UPDATE documents d
INNER JOIN document_indexes di ON di.doc_id = d.id
SET d.index_status = 'indexed'
WHERE d.index_status IN ('not_indexed', 'pending')
  AND d.status IN ('READY', 'ready', 'indexed')
  AND di.status IN ('READY', 'indexed');
UPDATE doc_chunks c
INNER JOIN documents d ON d.id = c.doc_id
SET c.embedding_status = 'embedded',
    c.vector_index_status = 'indexed'
WHERE d.index_status = 'indexed'
  AND c.embedding_status = 'pending'
  AND c.vector_index_status = 'pending';
