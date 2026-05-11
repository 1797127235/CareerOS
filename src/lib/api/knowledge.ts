import { cachedUserId } from "./core";

export interface KnowledgeFile {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  status: "pending" | "processing" | "ready" | "failed";
  chunk_count: number;
  preview: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface KnowledgeFileStatus {
  id: string;
  status: string;
  chunk_count: number;
  preview: string | null;
  error_message: string | null;
}

export async function uploadKnowledgeFile(
  file: File,
): Promise<{ id: string; filename: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", cachedUserId);
  const res = await fetch("/api/knowledge/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "上传失败" }));
    throw new Error(err.detail || "上传失败");
  }
  return res.json();
}

export async function getKnowledgeFiles(
  userId?: string,
): Promise<{ files: KnowledgeFile[]; total: number }> {
  const uid = userId || cachedUserId;
  const res = await fetch(`/api/knowledge/list?user_id=${encodeURIComponent(uid)}`);
  return res.json();
}

export async function getKnowledgeFileStatus(
  fileId: string,
  userId?: string,
): Promise<KnowledgeFileStatus> {
  const uid = userId || cachedUserId;
  const res = await fetch(
    `/api/knowledge/${encodeURIComponent(fileId)}/status?user_id=${encodeURIComponent(uid)}`,
  );
  return res.json();
}

export async function deleteKnowledgeFile(
  fileId: string,
  userId?: string,
): Promise<void> {
  const uid = userId || cachedUserId;
  await fetch(
    `/api/knowledge/${encodeURIComponent(fileId)}?user_id=${encodeURIComponent(uid)}`,
    { method: "DELETE" },
  );
}
