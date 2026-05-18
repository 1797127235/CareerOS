import { cachedUserId, http } from "./core";

export interface Note {
  id: string;
  content: string;
  created_at: string;
  updated_at: string | null;
}

export async function listNotes(): Promise<Note[]> {
  return http<Note[]>(`/api/notes?user_id=${cachedUserId}`);
}

export async function createNote(content: string): Promise<Note> {
  return http<Note>(`/api/notes?user_id=${cachedUserId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function updateNote(id: string, content: string): Promise<Note> {
  return http<Note>(`/api/notes/${id}?user_id=${cachedUserId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function deleteNote(id: string): Promise<void> {
  await http<void>(`/api/notes/${id}?user_id=${cachedUserId}`, {
    method: "DELETE",
  });
}
