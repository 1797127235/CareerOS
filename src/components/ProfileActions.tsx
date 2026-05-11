export function EditButton({ onClick, editing }: { onClick: () => void; editing?: boolean }) {
  return (
    <button
      onClick={onClick}
      className="text-xs text-ink hover:text-ink-deep transition-colors px-sm py-1 rounded-md hover:bg-ink/10"
    >
      {editing ? '取消' : '编辑'}
    </button>
  )
}

export function SaveButton({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="text-xs bg-ink text-bg px-sm py-1 rounded-md hover:bg-ink-deep disabled:opacity-50 transition-colors"
    >
      {loading ? '保存中…' : '保存'}
    </button>
  )
}
