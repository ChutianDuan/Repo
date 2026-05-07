import { requestJson } from "./apiClient";
import type { DocumentDetail, DocumentListItem, DocumentListResponse, UploadDocumentResponse } from "../types/document";

export function uploadDocument(
  baseUrl: string,
  userId: number,
  file: File,
): Promise<UploadDocumentResponse> {
  const formData = new FormData();
  formData.append("user_id", String(userId));
  formData.append("file", file);

  return requestJson<UploadDocumentResponse>(baseUrl, "/v1/documents", {
    method: "POST",
    body: formData,
  });
}

export function getDocumentDetail(baseUrl: string, docId: number): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(baseUrl, `/v1/documents/${docId}`);
}

export async function listDocuments(
  baseUrl: string,
  limit = 200,
): Promise<DocumentListItem[]> {
  const data = await requestJson<DocumentListResponse>(
    baseUrl,
    `/v1/documents?limit=${limit}`,
  );
  return data.items;
}
