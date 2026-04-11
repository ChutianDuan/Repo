export interface Citation {
  citation_id?: number;
  doc_id: number;
  chunk_id: number;
  chunk_index: number;
  score: number;
  snippet: string;
  created_at?: string;
}