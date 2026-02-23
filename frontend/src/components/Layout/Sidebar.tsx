import type { Sport } from '../../types/chat'
import { useSportsData } from '../../hooks/useSportsData'

const QUICK_PROMPTS: Record<NonNullable<Sport>, string[]> = {
  nba: [
    'NBA standings today',
    'NBA scores today',
    'NBA league leaders in points',
    'Who are the top shooters this season?',
  ],
  nfl: [
    'NFL standings today',
    'NFL scores today',
    'Top QBs in passing yards',
    'NFL rushing leaders this season',
  ],
}

interface Props {
  sport: Sport
  onSportChange: (sport: Sport) => void
  onPrompt: (text: string) => void
}

export function Sidebar({ sport, onSportChange, onPrompt }: Props) {
  const { scoreboard, isLoading } = useSportsData(sport)

  function toggleSport(selected: NonNullable<Sport>) {
    onSportChange(sport === selected ? null : selected)
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">Sport</div>
        <div className="sport-toggle">
          <button
            className={`sport-btn${sport === 'nba' ? ' sport-btn-active' : ''}`}
            onClick={() => toggleSport('nba')}
          >
            NBA
          </button>
          <button
            className={`sport-btn${sport === 'nfl' ? ' sport-btn-active' : ''}`}
            onClick={() => toggleSport('nfl')}
          >
            NFL
          </button>
        </div>
      </div>

      {sport && (
        <div className="sidebar-section">
          <div className="sidebar-label">Quick prompts</div>
          <ul className="prompt-list">
            {QUICK_PROMPTS[sport].map(p => (
              <li key={p}>
                <button className="prompt-btn" onClick={() => onPrompt(p)}>
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {sport && (
        <div className="sidebar-section">
          <div className="sidebar-label">Today's scores</div>
          {isLoading ? (
            <div className="scoreboard-loading">Loading...</div>
          ) : scoreboard ? (
            <pre className="scoreboard-lines">{scoreboard}</pre>
          ) : (
            <div className="scoreboard-empty">No games found</div>
          )}
        </div>
      )}
    </aside>
  )
}
