# 文档索引查询
from python_rag.infra.mysql import get_mysql_connection

def upsert_document_index(
        doc_id,
        index_type,
        embedding_model,
        dimension,
        index_path,
        mapping_path,
        chunk_count,
        status: str = "READY",
):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_indexes (
                    doc_id, index_type, embedding_model, dimension,
                    index_path, mapping_path, chunk_count, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    index_type=VALUES(index_type),
                    embedding_model=VALUES(embedding_model),
                    dimension=VALUES(dimension),
                    index_path=VALUES(index_path),
                    mapping_path=VALUES(mapping_path),
                    chunk_count=VALUES(chunk_count),
                    status=VALUES(status),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    doc_id,
                    index_type,
                    embedding_model,
                    dimension,
                    index_path,
                    mapping_path,
                    chunk_count,
                    status,
                ),
            )
    finally:        
        conn.close()


def get_document_index_by_doc_id(doc_id):
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT doc_id, index_type, embedding_model, dimension,
                       index_path, mapping_path, chunk_count, status,
                       created_at, updated_at
                FROM document_indexes
                WHERE doc_id=%s
                """,
                (doc_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()