import { useEffect, useRef, useState } from "react";
import { listNotes, createNote, updateNote, deleteNote, type Note } from "../lib/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD} 天前`;
  return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export default function QuickNotes({ isOpen, onClose }: Props) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [error, setError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 打开时加载
  useEffect(() => {
    if (!isOpen) return;
    listNotes()
      .then(setNotes)
      .catch(() => setError("加载失败"));
    // 自动聚焦输入框
    setTimeout(() => textareaRef.current?.focus(), 50);
  }, [isOpen]);

  // ESC 关闭
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  async function handleSave() {
    const text = input.trim();
    if (!text) return;
    setSaving(true);
    setError("");
    try {
      const note = await createNote(text);
      setNotes((prev) => {
        // 去重：相同 ID 移到顶部，不重复添加
        const filtered = prev.filter((n) => n.id !== note.id);
        return [note, ...filtered];
      });
      setInput("");
    } catch {
      setError("保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleEditSave(id: string) {
    const text = editText.trim();
    if (!text) return;
    try {
      const updated = await updateNote(id, text);
      setNotes((prev) => prev.map((n) => (n.id === id ? updated : n)));
      setEditingId(null);
    } catch {
      setError("编辑失败");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteNote(id);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    } catch {
      setError("删除失败");
    }
  }

  return (
    /* 背景遮罩 */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-[2px]"
      onClick={onClose}
    >
      {/* 纸张主体 — 阻止冒泡 */}
      <div
        className="relative flex flex-col w-[480px] max-w-[90vw] max-h-[80vh] bg-surface rounded-2xl shadow-2xl overflow-hidden flex-shrink-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-border-soft">
          <h2 className="text-base font-medium text-text">随记</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-text-subtle hover:text-text hover:bg-surface-elevated transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 输入区 */}
        <div className="px-6 pt-4 pb-3 border-b border-border-soft">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                void handleSave();
              }
            }}
            placeholder="有什么想让 Lumen 知道的？"
            rows={3}
            className="w-full resize-none text-sm text-text placeholder-gray-400 outline-none leading-relaxed"
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-text-subtle">⌘↵ 保存</span>
            <button
              onClick={handleSave}
              disabled={saving || !input.trim()}
              className="px-3 py-1 rounded-md text-xs font-medium bg-ink text-bg hover:bg-ink-deep disabled:opacity-40 transition-colors"
            >
              {saving ? "保存中…" : "保存"}
            </button>
          </div>
        </div>

        {/* 错误 */}
        {error && (
          <div className="mx-6 mt-2 px-3 py-2 text-xs text-danger bg-danger/10 rounded-lg">
            {error}
          </div>
        )}

        {/* 记录列表 */}
        <div className="flex-1 overflow-y-auto px-6 py-3 space-y-3">
          {notes.length === 0 && (
            <p className="text-sm text-text-subtle text-center py-8">还没有记录</p>
          )}
          {notes.map((note) => (
            <div key={note.id} className="group">
              {editingId === note.id ? (
                /* 编辑态 */
                <div>
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        void handleEditSave(note.id);
                      }
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    autoFocus
                    rows={3}
                    className="w-full resize-none text-sm text-text outline-none border border-border rounded-lg px-3 py-2 leading-relaxed"
                  />
                  <div className="flex gap-2 mt-1">
                    <button
                      onClick={() => void handleEditSave(note.id)}
                      className="text-xs px-2 py-1 rounded bg-ink text-bg hover:bg-ink-deep"
                    >
                      保存
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="text-xs px-2 py-1 rounded text-text-muted hover:bg-surface-elevated"
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                /* 展示态 */
                <div className="flex gap-2">
                  <div className="flex-1">
                    <p className="text-sm text-text leading-relaxed whitespace-pre-wrap">
                      {note.content}
                    </p>
                    <p className="text-xs text-text-subtle mt-1">
                      {formatTime(note.updated_at ?? note.created_at)}
                      {note.updated_at && note.updated_at !== note.created_at && " · 已编辑"}
                    </p>
                  </div>
                  {/* hover 操作 */}
                  <div className="flex-shrink-0 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => { setEditingId(note.id); setEditText(note.content); }}
                      className="p-1 rounded text-text-subtle hover:text-text hover:bg-surface-elevated"
                      title="编辑"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => void handleDelete(note.id)}
                      className="p-1 rounded text-text-subtle hover:text-danger hover:bg-danger/10"
                      title="删除"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
