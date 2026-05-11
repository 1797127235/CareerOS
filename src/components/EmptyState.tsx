export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="text-center py-xl">
      <p className="text-text-muted text-sm">{message}</p>
      {hint && <p className="text-text-subtle text-xs mt-xs">{hint}</p>}
    </div>
  )
}
