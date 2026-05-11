export function Card({
  title,
  icon,
  children,
  action,
  className = '',
}: {
  title: string
  icon?: string
  children: React.ReactNode
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={`border border-border-soft rounded-xl bg-surface overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-md py-sm border-b border-border-soft">
        <div className="flex items-center gap-xs">
          {icon && <span className="text-lg">{icon}</span>}
          <h2 className="text-base font-medium text-text">{title}</h2>
        </div>
        {action}
      </div>
      <div className="p-md">{children}</div>
    </div>
  )
}
