import { useEffect, useState } from "react";
import { getMemoryList } from "../lib/api";
import type { MemoryItem } from "../lib/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Memories() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getMemoryList()
      .then(setMemories)
      .catch(() => setError("记忆读取失败，稍后再试"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-[720px] mx-auto px-md py-xl">
      <h1 className="text-xl font-han text-ink mb-lg">记忆</h1>

      {loading && <p className="text-text-muted text-sm">我在想...</p>}

      {!loading && error && <p className="text-danger text-sm">{error}</p>}

      {!loading && !error && memories.length === 0 && (
        <p className="text-text-muted">还没有记忆。聊几句，我就开始记了。</p>
      )}

      {!loading && !error && memories.length > 0 && (
        <ul className="flex flex-col gap-xs">
          {memories.map((mem) => (
            <li key={mem.id} className="border border-border-soft rounded-lg px-md py-sm">
              <p className="text-text leading-relaxed">{mem.memory}</p>
              <p className="text-text-subtle text-xs mt-2xs">{formatDate(mem.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
