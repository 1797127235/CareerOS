import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";

export default function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    const win = getCurrentWindow();
    win.isMaximized().then(setIsMaximized);

    const unlisten = win.listen("tauri://resize", async () => {
      setIsMaximized(await win.isMaximized());
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const minimize = () => getCurrentWindow().minimize();
  const toggleMaximize = () => getCurrentWindow().toggleMaximize();
  const close = () => getCurrentWindow().close();

  return (
    <div className="flex items-center justify-between h-8 bg-bg border-b border-border-soft select-none flex-shrink-0">
      {/* 左侧 — 可拖拽区域 */}
      <div className="flex items-center gap-2 px-3 flex-1 h-full" style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}>
        <svg className="w-3.5 h-3.5 text-ink" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
          <circle cx="12" cy="12" r="10" />
        </svg>
        <span className="text-xs text-text-muted font-medium">Lumen</span>
      </div>

      {/* 右侧 — 窗口控制按钮 */}
      <div className="flex items-center">
        <button
          onClick={minimize}
          className="w-10 h-8 flex items-center justify-center text-text-subtle hover:bg-surface-elevated hover:text-text transition-colors"
          title="最小化"
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
          </svg>
        </button>
        <button
          onClick={toggleMaximize}
          className="w-10 h-8 flex items-center justify-center text-text-subtle hover:bg-surface-elevated hover:text-text transition-colors"
          title={isMaximized ? "还原" : "最大化"}
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          {isMaximized ? (
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 8v8H8V8h8z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 16V8H4v12h12v-4H8z" />
            </svg>
          ) : (
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
              <rect x="4" y="4" width="16" height="16" rx="1" />
            </svg>
          )}
        </button>
        <button
          onClick={close}
          className="w-10 h-8 flex items-center justify-center text-text-subtle hover:bg-danger hover:text-bg transition-colors"
          title="关闭"
          style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
