interface Props {
  onClear: () => void
}

export function Header({ onClear }: Props) {
  return (
    <header className="header">
      <div className="header-brand">
        <span className="header-logo">🏆</span>
        <span className="header-title">Sports Analyst</span>
        <span className="header-subtitle">NFL · NBA</span>
      </div>
      <button className="clear-button" onClick={onClear} title="Clear conversation">
        New Chat
      </button>
    </header>
  )
}
