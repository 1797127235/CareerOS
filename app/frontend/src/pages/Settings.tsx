import { useEffect, useRef, useState } from "react";
import { getConfig, updateConfig } from "../lib/api";

export default function Settings() {
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const savedTimer = useRef<number | null>(null);

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setHasKey(cfg.has_api_key);
      })
      .catch(() => setError("配置加载失败，请刷新重试"))
      .finally(() => setLoading(false));

    return () => {
      if (savedTimer.current) {
        window.clearTimeout(savedTimer.current);
      }
    };
  }, []);

  const handleSave = async () => {
    const key = apiKey.trim();
    if (!key || saving) return;
    setSaving(true);
    setError("");
    try {
      await updateConfig({ dashscope_api_key: key });
      setHasKey(true);
      setSaved(true);
      setApiKey("");
      savedTimer.current = window.setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("保存失败，请检查网络或稍后重试");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <div className="w-full max-w-[32rem] mx-auto px-md py-xl">
      <h1 className="text-xl font-han text-ink mb-md">设置</h1>

      {error && (
        <div className="mb-md px-sm py-xs bg-red/10 text-red text-sm rounded">
          {error}
        </div>
      )}

      <div className="space-y-lg">
        {/* API Key 卡片 */}
        <div className="border border-border rounded-lg p-lg bg-surface-elevated">
          <div className="flex items-center justify-between mb-sm">
            <h2 className="text-base font-medium text-text">DashScope API Key</h2>
            {hasKey ? (
              <div className="flex items-center gap-xs text-sm text-green">
                <span className="w-2 h-2 rounded-full bg-green" />
                已配置
              </div>
            ) : (
              <div className="flex items-center gap-xs text-sm text-warning">
                <span className="w-2 h-2 rounded-full bg-warning" />
                未配置
              </div>
            )}
          </div>

          {!hasKey && (
            <p className="text-sm text-text-muted mb-sm">
              CareerOS 使用阿里云 DashScope 提供 AI 能力。
              <a
                href="https://dashscope.aliyun.com/"
                target="_blank"
                rel="noreferrer"
                className="text-ink ml-xs"
              >
                免费获取 →
              </a>
            </p>
          )}

          <div className="flex gap-sm">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={hasKey ? "输入新 Key 以更换" : "sk-..."}
              className="flex-1 px-sm py-xs border border-border rounded text-sm bg-surface"
            />
            <button
              onClick={handleSave}
              disabled={!apiKey.trim() || saving}
              className="px-md py-xs bg-ink text-surface rounded text-sm disabled:opacity-40"
            >
              {saving ? "保存中..." : saved ? "已保存" : "保存"}
            </button>
          </div>
        </div>

        {/* 数据存储卡片 */}
        <div className="border border-border rounded-lg p-lg bg-surface-elevated">
          <h2 className="text-base font-medium text-text mb-sm">数据存储</h2>
          <div className="bg-surface rounded p-sm font-mono text-sm text-text-muted mb-sm">
            <div>~/.careeros/</div>
            <div className="pl-sm">├── career_os.db</div>
            <div className="pl-sm">├── chroma_db/</div>
            <div className="pl-sm">└── config.json</div>
          </div>
          <p className="text-xs text-text-muted">
            所有对话、画像、岗位数据均存储在此目录。备份或迁移只需复制整个 ~/.careeros 文件夹。
          </p>
        </div>
      </div>
    </div>
  );
}
