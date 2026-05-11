import { cachedUserId, http } from "./core";

export type MemoryStats = {
  status: string; // "ready" | "no_api_key" | "error" | "not_initialized"
  count: number;
};

export type MemoryItem = {
  id: string;
  memory: string;
  created_at: string | null;
  categories: string[];
};

export function getMemoryContent(): Promise<{ content: string }> {
  return http<{ content: string }>(
    `/api/memory/me?user_id=${encodeURIComponent(cachedUserId)}`,
  );
}

export function resetMemory(): Promise<{ deleted: number }> {
  return http<{ deleted: number }>(
    `/api/memory/reset?user_id=${encodeURIComponent(cachedUserId)}`,
    { method: "POST" },
  );
}

export function getMemoryStats(): Promise<MemoryStats> {
  return http<MemoryStats>(
    `/api/memory/stats?user_id=${encodeURIComponent(cachedUserId)}`,
  );
}

export function getMemoryList(): Promise<MemoryItem[]> {
  return http<MemoryItem[]>(
    `/api/memory/list?user_id=${encodeURIComponent(cachedUserId)}`,
  );
}

export function deleteMemory(id: string): Promise<{ deleted: string }> {
  return http<{ deleted: string }>(
    `/api/memory/${encodeURIComponent(id)}?user_id=${encodeURIComponent(cachedUserId)}`,
    { method: "DELETE" },
  );
}

// ── Resume Upload ──

export type ResumeUploadResult = {
  ok: boolean;
  events: number;
  profile: Record<string, unknown>;
  skills: Record<string, unknown>[];
  experiences: Record<string, unknown>[];
};

export async function uploadResume(file: File): Promise<ResumeUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", cachedUserId);
  const res = await fetch("/api/memory/upload-resume", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "上传失败" }));
    throw new Error(err.detail || "上传失败");
  }
  return res.json();
}

// ── Structured Profile ──

export type StructuredProfile = {
  profile: Record<string, unknown>;
  skills: Array<{
    name: string;
    level: string;
    context?: string | null;
    source?: string | null;
  }>;
  experiences: Array<{
    title: string;
    description: string;
    period?: string | null;
    tech_stack?: string | null;
    role?: string | null;
    source?: string | null;
  }>;
  goals: Record<string, string>;
  preferences: Record<string, string>;
  status: Record<string, string>;
  decisions: Array<Record<string, unknown>>;
};

export function getStructuredProfile(): Promise<StructuredProfile> {
  return http<StructuredProfile>(
    `/api/memory/profile-structured?user_id=${encodeURIComponent(cachedUserId)}`,
  );
}

export type ProfileUpdatePayload = {
  profile?: Record<string, unknown>;
  skills?: Array<Record<string, unknown>>;
  experiences?: Array<Record<string, unknown>>;
};

export async function updateStructuredProfile(
  payload: ProfileUpdatePayload,
): Promise<{ updated: number; message: string }> {
  return http<{ updated: number; message: string }>(
    `/api/memory/profile-update?user_id=${encodeURIComponent(cachedUserId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

// ── AI Understanding ──

export type AboutYouResponse = {
  about_you: string;
  updated_at: string;
  patterns: Array<{
    insight: string;
    category: string;
    evidence_count: number;
    first_seen: string;
    updated_at: string;
  }>;
  now_status: Record<string, string>;
  journey: Array<{
    id: string;
    type: string;
    content: string;
    date: string | null;
  }>;
};

export function getAIUnderstanding(): Promise<AboutYouResponse> {
  return http<AboutYouResponse>(
    `/api/memory/understanding?user_id=${encodeURIComponent(cachedUserId)}`,
  );
}

export function refreshAIUnderstanding(): Promise<{ message: string; chars: number }> {
  return http<{ message: string; chars: number }>(
    `/api/memory/understanding/refresh?user_id=${encodeURIComponent(cachedUserId)}`,
    { method: "POST" },
  );
}

export function correctAIUnderstanding(text: string): Promise<{ message: string; chars: number }> {
  return http<{ message: string; chars: number }>(
    `/api/memory/understanding/correct?user_id=${encodeURIComponent(cachedUserId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    },
  );
}
