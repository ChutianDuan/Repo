import { requestEnvelope } from "./apiClient";
import type { DocumentDetail, DocumentListItem, DocumentListResponse, DeletedDocumentResponse, UploadDocumentResponse } from "../types/document";

export function uploadDocument(
  baseUrl: string,
  userId: number,
  file: File,
): Promise<UploadDocumentResponse> {
  const formData = new FormData();
  formData.append("user_id", String(userId));
  formData.append("file", file);

  return requestEnvelope<UploadDocumentResponse>(baseUrl, "/v1/documents", {
    method: "POST",
    body: formData,
  });
}

export function deleteDocument(
  baseUrl: string,
  docId: number,
): Promise<DeletedDocumentResponse> {
  return requestEnvelope<DeletedDocumentResponse>(baseUrl, `/v1/documents/${docId}`, {
    method: "DELETE",
  });
}

export function getDocumentDetail(baseUrl: string, docId: number): Promise<DocumentDetail> {
  return requestEnvelope<DocumentDetail>(baseUrl, `/v1/documents/${docId}`);
}

export async function listDocuments(
  baseUrl: string,
  limit = 200,
): Promise<DocumentListItem[]> {
  const data = await requestEnvelope<DocumentListResponse>(
    baseUrl,
    `/v1/documents?limit=${limit}`,
  );
  return data.items;
}
